//! PDF documents on PDFium. Points everywhere here are the page as displayed: origin top-left,
//! y down, the page's own /Rotate already applied (what `PageSource` and the Python app use).

use crate::secure;
use crate::source::{Pages, Tiles};
use lopdf::Permissions;
use pdfium_render::prelude::*;
use remedy_ui::core::{Rect, Size};
use remedy_ui::pages::{PageText, TextRun};
use remedy_ui::paint::Image;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock, PoisonError};

#[derive(Debug)]
pub enum Error {
    /// Protected, and the password is missing or wrong.
    Password,
    /// No pages.
    Empty,
    Other(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Password => f.write_str("a password is needed, or it is wrong"),
            Error::Empty => f.write_str("the document has no pages"),
            Error::Other(why) => f.write_str(why),
        }
    }
}
impl std::error::Error for Error {}

fn other(e: impl std::fmt::Display) -> Error {
    Error::Other(e.to_string())
}

/// Where PDFium is loaded from. On Windows it ships beside the executable. It is never
/// searched for in the working directory, where a document's folder could plant one.
#[cfg(windows)]
fn library_path() -> Result<PathBuf, String> {
    let mut dir = std::env::current_exe().map_err(|e| e.to_string())?;
    dir.pop();
    let mut path = Pdfium::pdfium_platform_library_name_at_path(&dir);
    if cfg!(debug_assertions) && !path.exists() {
        path = Pdfium::pdfium_platform_library_name_at_path(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/pdfium"
        ));
    }
    Ok(path)
}

/// In the APK, where the system finds the app's own libraries by name.
#[cfg(target_os = "android")]
fn library_path() -> Result<PathBuf, String> {
    Ok(PathBuf::from("libpdfium.so"))
}

/// On Linux the library is part of the program, so that an update replacing the one signed
/// file replaces both. It is written once to the person's cache, under its checksum.
#[cfg(target_os = "linux")]
fn library_path() -> Result<PathBuf, String> {
    use sha2::Digest as _;
    const LIBRARY: &[u8] = include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/pdfium/linux-x64/libpdfium.so"
    ));
    let cache = std::env::var_os("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .filter(|p| p.is_absolute())
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".cache")))
        .ok_or("there is no cache folder (HOME is not set)")?;
    let digest: String = sha2::Sha256::digest(LIBRARY)
        .iter()
        .take(8)
        .map(|b| format!("{b:02x}"))
        .collect();
    let folder = cache.join("remedypdf");
    let path = folder.join(format!("libpdfium-{digest}.so"));
    // A file that is not exactly the library (cut short, or changed) is written again.
    if !std::fs::read(&path).is_ok_and(|found| found == LIBRARY) {
        std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
        crate::secure::write_atomic(&path, LIBRARY).map_err(|e| e.to_string())?;
    }
    Ok(path)
}

fn library() -> Result<&'static Pdfium, Error> {
    static PDFIUM: OnceLock<Result<Pdfium, String>> = OnceLock::new();
    PDFIUM
        .get_or_init(|| {
            Pdfium::bind_to_library(library_path()?)
                .map(Pdfium::new)
                .map_err(|e| format!("PDFium did not load: {e}"))
        })
        .as_ref()
        .map_err(|e| Error::Other(e.clone()))
}

pub struct PdfFile {
    doc: Mutex<PdfDocument<'static>>,
    /// Cached: the UI thread asks while a worker may hold the document.
    sizes: Vec<Size>,
    /// Set when the file was opened with a password; saving protects it again.
    protection: Option<(String, Permissions)>,
}

/// Pixels per point used to convert coordinates through PDFium's integer pixel space.
const PRECISION: f32 = 100.0;

fn px(points: f32) -> Pixels {
    (points * PRECISION).round() as Pixels
}

fn precise(page: &PdfPage) -> PdfRenderConfig {
    PdfRenderConfig::new().set_fixed_size(px(page.width().value), px(page.height().value))
}

/// Displayed point to PDF user space.
fn to_user(page: &PdfPage, x: f32, y: f32) -> Result<(PdfPoints, PdfPoints), Error> {
    page.pixels_to_points(px(x), px(y), &precise(page))
        .map_err(other)
}

/// The page's /Rotate in degrees. Added content is turned by this much so it reads upright.
fn turn(page: &PdfPage) -> f32 {
    page.rotation().map(|r| r.as_degrees()).unwrap_or(0.0)
}

impl PdfFile {
    pub fn open(path: &Path, password: Option<&str>) -> Result<PdfFile, Error> {
        Self::from_bytes(std::fs::read(path).map_err(other)?, password)
    }

    pub fn from_bytes(bytes: Vec<u8>, password: Option<&str>) -> Result<PdfFile, Error> {
        let pdfium = library()?;
        let load = |b: Vec<u8>| pdfium.load_pdf_from_byte_vec(b, None).map_err(other);
        let (doc, protection) = match pdfium.load_pdf_from_byte_vec(bytes.clone(), None) {
            Ok(doc) => {
                if matches!(
                    doc.permissions().security_handler_revision(),
                    Ok(PdfSecurityHandlerRevision::Unprotected)
                ) {
                    (doc, None)
                } else {
                    // Restrictions only, no password to open. Saved unprotected, as 1.x does.
                    (
                        load(secure::unlock(&bytes, "").map_err(other)?.bytes)?,
                        None,
                    )
                }
            }
            Err(PdfiumError::PdfiumLibraryInternalError(PdfiumInternalError::PasswordError)) => {
                let password = password.ok_or(Error::Password)?;
                let unlocked = secure::unlock(&bytes, password).map_err(|e| match e
                    .downcast_ref::<lopdf::Error>()
                {
                    Some(lopdf::Error::InvalidPassword) => Error::Password,
                    _ => other(e),
                })?;
                (
                    load(unlocked.bytes)?,
                    Some((password.to_owned(), unlocked.permissions)),
                )
            }
            Err(e) => return Err(other(e)),
        };
        let sizes: Vec<Size> = doc
            .pages()
            .iter()
            .map(|p| Size::new(p.width().value, p.height().value))
            .collect();
        if sizes.is_empty() {
            return Err(Error::Empty);
        }
        Ok(PdfFile {
            doc: Mutex::new(doc),
            sizes,
            protection,
        })
    }

    fn doc(&self) -> MutexGuard<'_, PdfDocument<'static>> {
        self.doc.lock().unwrap_or_else(PoisonError::into_inner)
    }

    pub fn is_protected(&self) -> bool {
        self.protection.is_some()
    }

    /// Writes Helvetica text whose first baseline starts at (x, y). `color` is RGB.
    pub fn add_text(
        &self,
        page: usize,
        x: f32,
        y: f32,
        text: &str,
        size: f32,
        color: [u8; 3],
    ) -> Result<(), Error> {
        let mut doc = self.doc();
        let font = doc.fonts_mut().helvetica();
        let mut page = doc.pages().get(page as _).map_err(other)?;
        let degrees = turn(&page);
        for (n, line) in text.lines().enumerate().filter(|(_, l)| !l.is_empty()) {
            let (ux, uy) = to_user(&page, x, y + n as f32 * size * 1.2)?;
            let mut object =
                PdfPageTextObject::new(&doc, line, font, PdfPoints::new(size)).map_err(other)?;
            object
                .set_fill_color(PdfColor::new(color[0], color[1], color[2], 255))
                .map_err(other)?;
            object
                .rotate_counter_clockwise_degrees(degrees)
                .map_err(other)?;
            object.translate(ux, uy).map_err(other)?;
            page.objects_mut().add_text_object(object).map_err(other)?;
        }
        Ok(())
    }

    /// Places a picture inside `area`, keeping its proportions, centred.
    pub fn add_image(&self, page: usize, area: Rect, picture: &Path) -> Result<(), Error> {
        let picture = image::open(picture).map_err(other)?;
        let (w, h) = (picture.width() as f32, picture.height() as f32);
        let fit = (area.width() / w).min(area.height() / h);
        if !(fit > 0.0 && fit.is_finite()) {
            return Err(other("the picture or the area is empty"));
        }
        let (w, h) = (w * fit, h * fit);
        let left = area.min.x + (area.width() - w) / 2.0;
        let bottom = area.min.y + (area.height() + h) / 2.0;

        let doc = self.doc();
        let mut page = doc.pages().get(page as _).map_err(other)?;
        let (ux, uy) = to_user(&page, left, bottom)?;
        let degrees = turn(&page);
        // shortcut: JPEGs are stored decoded (same pixels, bigger file); use
        // FPDFImageObj_LoadJpegFile if file size matters.
        let mut object = PdfPageImageObject::new(&doc, &picture).map_err(other)?;
        object.scale(w, h).map_err(other)?;
        object
            .rotate_counter_clockwise_degrees(degrees)
            .map_err(other)?;
        object.translate(ux, uy).map_err(other)?;
        page.objects_mut().add_image_object(object).map_err(other)?;
        Ok(())
    }

    /// Saves, protecting again if the file was opened with a password.
    pub fn save(&self, path: &Path) -> Result<(), Error> {
        let bytes = self.doc().save_to_bytes().map_err(other)?;
        let bytes = match &self.protection {
            Some((password, permissions)) => {
                secure::protect(&bytes, password, *permissions).map_err(other)?
            }
            None => bytes,
        };
        secure::write_atomic(path, &bytes).map_err(other)
    }

    fn page_runs(&self, page: usize) -> Option<PageText> {
        let doc = self.doc();
        let page = doc.pages().get(page as _).ok()?;
        let text = page.text().ok()?;
        let config = precise(&page);
        let place = |r: PdfRect| -> Option<Rect> {
            let a = page.points_to_pixels(r.left(), r.top(), &config).ok()?;
            let b = page.points_to_pixels(r.right(), r.bottom(), &config).ok()?;
            let p = |v: Pixels| v as f32 / PRECISION;
            Some(Rect::new(
                p(a.0.min(b.0)),
                p(a.1.min(b.1)),
                p(a.0.max(b.0)),
                p(a.1.max(b.1)),
            ))
        };
        let runs: Vec<TextRun> = text
            .segments()
            .iter()
            .filter_map(|segment| {
                let mut run = TextRun::new(segment.text(), place(segment.bounds())?);
                if let Ok(chars) = segment.chars() {
                    let boxes: Vec<Rect> = chars
                        .iter()
                        .filter_map(|c| place(c.loose_bounds().ok()?))
                        .collect();
                    if boxes.len() == run.len() {
                        run.chars = boxes;
                    }
                }
                (!run.is_empty()).then_some(run)
            })
            .collect();
        (!runs.is_empty()).then_some(PageText { runs })
    }
}

impl Tiles for PdfFile {
    fn count(&self) -> usize {
        self.sizes.len()
    }

    fn size(&self, page: usize) -> Option<Size> {
        self.sizes.get(page).copied()
    }

    fn runs(&self, page: usize) -> Option<PageText> {
        self.page_runs(page)
    }

    /// The part `region` of a page at `scale` pixels per point, as `width` x `height` pixels.
    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error> {
        let doc = self.doc();
        let page = doc.pages().get(page as _).map_err(other)?;
        let scaled = |v: f32| (v * scale).round() as Pixels;
        // The whole page at this scale, shifted so the tile's corner is the bitmap's corner.
        let config = PdfRenderConfig::new()
            .set_fixed_size(scaled(page.width().value), scaled(page.height().value))
            .set_origin(-scaled(region.min.x), -scaled(region.min.y))
            .set_reverse_byte_order(true);
        let mut bitmap = PdfBitmap::empty(width as Pixels, height as Pixels, PdfBitmapFormat::BGRA)
            .map_err(other)?;
        page.render_into_bitmap_with_config(&mut bitmap, &config)
            .map_err(other)?;
        let pixels = bitmap.as_raw_bytes();
        if pixels.len() != width as usize * height as usize * 4 {
            return Err(other("PDFium returned a bitmap of the wrong size"));
        }
        Ok(Image::new(width, height, Arc::from(pixels)))
    }
}

crate::source::page_source!(PdfFile);

/// Saves any document as a PDF of page pictures at twice its size, as 1.x exports.
pub fn export(pages: &dyn Pages, path: &Path) -> Result<(), Error> {
    let mut doc = library()?.create_new_pdf().map_err(other)?;
    for index in 0..pages.count() {
        let size = pages.size(index).ok_or(Error::Empty)?;
        let (width, height) = (
            (size.width * 2.0).round() as u32,
            (size.height * 2.0).round() as u32,
        );
        let whole = Rect::new(0.0, 0.0, size.width, size.height);
        let tile = pages.render_tile(index, whole, 2.0, width.max(1), height.max(1))?;
        let picture = image::RgbaImage::from_raw(tile.width, tile.height, tile.pixels.to_vec())
            .ok_or_else(|| other("a page was drawn at the wrong size"))?;
        let picture =
            image::DynamicImage::ImageRgb8(image::DynamicImage::ImageRgba8(picture).into_rgb8());
        let mut page = doc
            .pages_mut()
            .create_page_at_end(PdfPagePaperSize::Custom(
                PdfPoints::new(size.width),
                PdfPoints::new(size.height),
            ))
            .map_err(other)?;
        let mut object = PdfPageImageObject::new(&doc, &picture).map_err(other)?;
        object.scale(size.width, size.height).map_err(other)?;
        page.objects_mut().add_image_object(object).map_err(other)?;
    }
    let bytes = doc.save_to_bytes().map_err(other)?;
    secure::write_atomic(path, &bytes).map_err(other)
}
