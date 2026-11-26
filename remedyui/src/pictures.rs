//! Documents whose pages are pictures: single images, multi-page TIFF, and CBZ/CBR comics.
//! Sizes and ordering follow what RemedyPDF 1.x showed (MuPDF): a page is its pixels at the
//! file's DPI (96 when it says nothing), turned as its EXIF orientation says; comic pages sort
//! by name, numbers by value, ignoring case. A GIF shows its first frame (1.x showed the last).

use crate::pdf::Error;
use crate::source::{Tiles, white};
use fast_image_resize as fr;
use image::metadata::Orientation;
use image::{DynamicImage, ImageDecoder, ImageReader, RgbaImage};
use remedy_ui::core::{Rect, Size};
use remedy_ui::paint::Image;
use std::io::{Cursor, Read};
use std::sync::{Arc, Mutex, PoisonError};

/// A comic that unpacks to more than this is refused as a decompression bomb.
const MAX_UNPACKED: u64 = 4 << 30;

const PICTURES: [&str; 8] = ["png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff", "webp"];

fn other(e: impl std::fmt::Display) -> Error {
    Error::Other(e.to_string())
}

struct Page {
    data: Arc<[u8]>,
    /// Which image of a multi-page TIFF: its directory's offset.
    directory: Option<u32>,
    size: Size,
}

pub struct Pictures {
    pages: Vec<Page>,
    /// The last few decoded pages: a spread and a neighbour.
    decoded: Mutex<Vec<(usize, Arc<RgbaImage>)>>,
}

impl Pictures {
    pub fn image(bytes: Vec<u8>) -> Result<Pictures, Error> {
        let data: Arc<[u8]> = bytes.into();
        let directories = tiff_directories(&data);
        let pages = if directories.len() > 1 {
            directories
                .into_iter()
                .map(|d| page(data.clone(), Some(d)))
                .collect::<Result<_, _>>()?
        } else {
            vec![page(data, None)?]
        };
        Ok(Pictures {
            pages,
            decoded: Mutex::default(),
        })
    }

    pub fn cbz(bytes: Vec<u8>) -> Result<Pictures, Error> {
        let mut zip = zip::ZipArchive::new(Cursor::new(bytes)).map_err(other)?;
        let mut files = Vec::new();
        let mut unpacked = 0u64;
        for i in 0..zip.len() {
            let entry = zip.by_index(i).map_err(other)?;
            let name = entry.name().to_owned();
            if !is_page(&name) {
                continue;
            }
            let mut data = Vec::new();
            entry
                .take(MAX_UNPACKED - unpacked + 1)
                .read_to_end(&mut data)
                .map_err(other)?;
            unpacked += data.len() as u64;
            if unpacked > MAX_UNPACKED {
                return Err(other("the comic unpacks to more than 4 GB"));
            }
            files.push((name, data));
        }
        Self::comic(files)
    }

    pub fn cbr(bytes: Vec<u8>, password: Option<&str>) -> Result<Pictures, Error> {
        // Many .cbr files are really zip files.
        if bytes.starts_with(b"PK") {
            return Self::cbz(bytes);
        }
        let password = password.map(str::as_bytes);
        let mut options = rars::ArchiveReadOptions::default();
        options.password = password;
        let rar_error = |e: rars::Error| match e.kind() {
            rars::ErrorKind::PasswordRequired | rars::ErrorKind::BadPassword => Error::Password,
            _ => other(e),
        };
        let archive =
            rars::ArchiveReader::read_owned_with_options(bytes, options).map_err(rar_error)?;
        let wanted: Vec<(usize, String)> = archive
            .member_refs()
            .enumerate()
            .filter(|(_, m)| !m.is_directory())
            .map(|(i, m)| {
                (
                    i,
                    String::from_utf8_lossy(m.name_bytes()).replace('\\', "/"),
                )
            })
            .filter(|(_, name)| is_page(name))
            .collect();
        let indices: Vec<usize> = wanted.iter().map(|(i, _)| *i).collect();
        // One pass: a solid archive is decoded once, not once per page.
        let contents = archive
            .read_members_at(&indices, password)
            .map_err(rar_error)?;
        let files = wanted
            .into_iter()
            .zip(contents)
            .filter_map(|((_, name), data)| Some((name, data?)))
            .collect();
        Self::comic(files)
    }

    fn comic(mut files: Vec<(String, Vec<u8>)>) -> Result<Pictures, Error> {
        files.sort_by(|a, b| natural(&a.0, &b.0));
        // A damaged page is left out; the rest of the comic still reads.
        let pages: Vec<Page> = files
            .into_iter()
            .filter_map(|(_, d)| page(d.into(), None).ok())
            .collect();
        if pages.is_empty() {
            return Err(Error::Empty);
        }
        Ok(Pictures {
            pages,
            decoded: Mutex::default(),
        })
    }

    /// A page's size in the file's own pixels.
    pub fn pixel_size(&self, index: usize) -> Option<(u32, u32)> {
        let image = self.pixels(index).ok()?;
        Some((image.width(), image.height()))
    }

    fn pixels(&self, index: usize) -> Result<Arc<RgbaImage>, Error> {
        let mut cache = self.decoded.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some((_, image)) = cache.iter().find(|(i, _)| *i == index) {
            return Ok(image.clone());
        }
        let page = self.pages.get(index).ok_or_else(|| other("no such page"))?;
        let data = at_directory(&page.data, page.directory);
        let mut decoder = decoder(&data)?;
        let orientation = decoder.orientation().unwrap_or(Orientation::NoTransforms);
        let mut image = DynamicImage::from_decoder(decoder).map_err(other)?;
        image.apply_orientation(orientation);
        let mut image = image.into_rgba8();
        // On white paper, so what is drawn is opaque.
        for p in image.pixels_mut() {
            let a = u32::from(p.0[3]);
            for c in &mut p.0[..3] {
                *c = ((u32::from(*c) * a + 255 * (255 - a) + 127) / 255) as u8;
            }
            p.0[3] = 255;
        }
        let image = Arc::new(image);
        if cache.len() >= 3 {
            cache.remove(0);
        }
        cache.push((index, image.clone()));
        Ok(image)
    }
}

impl Tiles for Pictures {
    fn sizes(&self) -> Vec<Size> {
        self.pages.iter().map(|p| p.size).collect()
    }

    fn size(&self, page: usize) -> Option<Size> {
        self.pages.get(page).map(|p| p.size)
    }

    fn count(&self) -> usize {
        self.pages.len()
    }

    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error> {
        let source = self.pixels(page)?;
        let size = self.size(page).ok_or_else(|| other("no such page"))?;
        let mut out = white(width, height);
        // The part of the tile that is on the page, in tile pixels.
        let on = |tile: u32, start: f32, length: f32| -> (u32, u32) {
            let from = (-start * scale).max(0.0).floor() as u32;
            let to = (((length - start) * scale).round().max(0.0) as u32).min(tile);
            (from.min(to), to)
        };
        let (x0, x1) = on(width, region.min.x, size.width);
        let (y0, y1) = on(height, region.min.y, size.height);
        if x1 > x0 && y1 > y0 {
            // Source pixels per tile pixel.
            let kx = f64::from(source.width()) / f64::from(size.width * scale);
            let ky = f64::from(source.height()) / f64::from(size.height * scale);
            let left = ((f64::from(region.min.x * scale) + f64::from(x0)) * kx).max(0.0);
            let top = ((f64::from(region.min.y * scale) + f64::from(y0)) * ky).max(0.0);
            let crop_w = (f64::from(x1 - x0) * kx).min(f64::from(source.width()) - left);
            let crop_h = (f64::from(y1 - y0) * ky).min(f64::from(source.height()) - top);
            let from = fr::images::ImageRef::new(
                source.width(),
                source.height(),
                source.as_raw(),
                fr::PixelType::U8x4,
            )
            .map_err(other)?;
            let mut part = fr::images::Image::new(x1 - x0, y1 - y0, fr::PixelType::U8x4);
            let options = fr::ResizeOptions::new()
                .crop(left, top, crop_w, crop_h)
                .use_alpha(false);
            fr::Resizer::new()
                .resize(&from, &mut part, &options)
                .map_err(other)?;
            let row = ((x1 - x0) * 4) as usize;
            for (n, line) in part.buffer().chunks_exact(row).enumerate() {
                let at = (((y0 as usize + n) * width as usize) + x0 as usize) * 4;
                out[at..at + row].copy_from_slice(line);
            }
        }
        Ok(Image::new(width, height, Arc::from(out)))
    }
}

crate::source::page_source!(Pictures);

fn is_page(name: &str) -> bool {
    let base = name.rsplit('/').next().unwrap_or(name);
    // macOS resource forks are named like pictures but are not.
    if name.starts_with("__MACOSX/") || base.starts_with("._") {
        return false;
    }
    base.rsplit_once('.')
        .is_some_and(|(_, e)| PICTURES.iter().any(|p| e.eq_ignore_ascii_case(p)))
}

/// Compares names with runs of digits by value ("p2" before "p10"), ignoring case.
fn natural(a: &str, b: &str) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    let (a, b) = (a.to_uppercase(), b.to_uppercase());
    let (mut a, mut b) = (a.as_bytes(), b.as_bytes());
    loop {
        match (a.first(), b.first()) {
            (Some(x), Some(y)) if x.is_ascii_digit() && y.is_ascii_digit() => {
                let digits = |s: &[u8]| s.iter().take_while(|c| c.is_ascii_digit()).count();
                let (na, nb) = (digits(a), digits(b));
                let trim = |s: &'_ [u8]| s.iter().position(|c| *c != b'0').unwrap_or(s.len());
                let (va, vb) = (&a[trim(&a[..na])..na], &b[trim(&b[..nb])..nb]);
                let order = va.len().cmp(&vb.len()).then_with(|| va.cmp(vb));
                if order != Ordering::Equal {
                    return order;
                }
                (a, b) = (&a[na..], &b[nb..]);
            }
            (Some(x), Some(y)) => {
                if x != y {
                    return x.cmp(y);
                }
                (a, b) = (&a[1..], &b[1..]);
            }
            (x, y) => return x.cmp(&y),
        }
    }
}

fn decoder(data: &[u8]) -> Result<impl ImageDecoder + '_, Error> {
    ImageReader::new(Cursor::new(data))
        .with_guessed_format()
        .map_err(other)?
        .into_decoder()
        .map_err(other)
}

fn page(data: Arc<[u8]>, directory: Option<u32>) -> Result<Page, Error> {
    let view = at_directory(&data, directory);
    let mut reader = decoder(&view)?;
    let (mut w, mut h) = reader.dimensions();
    let (mut dpi_x, mut dpi_y) = dpi(&view);
    use Orientation::*;
    if matches!(
        reader.orientation().unwrap_or(NoTransforms),
        Rotate90 | Rotate270 | Rotate90FlipH | Rotate270FlipH
    ) {
        std::mem::swap(&mut w, &mut h);
        std::mem::swap(&mut dpi_x, &mut dpi_y);
    }
    drop(reader);
    let size = Size::new(w as f32 * 72.0 / dpi_x, h as f32 * 72.0 / dpi_y);
    Ok(Page {
        data,
        directory,
        size,
    })
}

/// The file as seen with `directory` as a TIFF's first image.
fn at_directory(data: &[u8], directory: Option<u32>) -> std::borrow::Cow<'_, [u8]> {
    match directory {
        Some(offset) if data.len() >= 8 => {
            let mut copy = data.to_vec();
            let bytes = if data[0] == b'I' {
                offset.to_le_bytes()
            } else {
                offset.to_be_bytes()
            };
            copy[4..8].copy_from_slice(&bytes);
            copy.into()
        }
        _ => data.into(),
    }
}

/// Reads numbers out of a TIFF structure (a TIFF file, or the EXIF block of a JPEG).
struct Tiff<'a> {
    data: &'a [u8],
    little: bool,
}

impl<'a> Tiff<'a> {
    fn new(data: &'a [u8]) -> Option<Self> {
        let little = match data.get(..4)? {
            b"II*\0" => true,
            b"MM\0*" => false,
            _ => return None,
        };
        Some(Tiff { data, little })
    }

    fn u16(&self, at: usize) -> Option<u16> {
        let b = self.data.get(at..at.checked_add(2)?)?.try_into().ok()?;
        Some(if self.little {
            u16::from_le_bytes(b)
        } else {
            u16::from_be_bytes(b)
        })
    }

    fn u32(&self, at: usize) -> Option<u32> {
        let b = self.data.get(at..at.checked_add(4)?)?.try_into().ok()?;
        Some(if self.little {
            u32::from_le_bytes(b)
        } else {
            u32::from_be_bytes(b)
        })
    }

    /// X and Y resolution of the first image, in dots per inch.
    fn resolution(&self) -> Option<(f32, f32)> {
        let start = self.u32(4)? as usize;
        let (mut x, mut y, mut unit) = (None, None, 2);
        for n in 0..usize::from(self.u16(start)?) {
            let entry = start + 2 + n * 12;
            let rational = || {
                let at = self.u32(entry + 8)? as usize;
                let (top, bottom) = (self.u32(at)?, self.u32(at + 4)?);
                (bottom != 0).then(|| top as f32 / bottom as f32)
            };
            match self.u16(entry)? {
                282 => x = rational(),
                283 => y = rational(),
                296 => unit = self.u16(entry + 8)?,
                _ => {}
            }
        }
        let per_inch = match unit {
            2 => 1.0,
            3 => 2.54,
            _ => return None,
        };
        Some((x? * per_inch, y? * per_inch))
    }
}

/// The offset of every image in a classic TIFF; empty for anything else.
fn tiff_directories(data: &[u8]) -> Vec<u32> {
    let mut found = Vec::new();
    let Some(tiff) = Tiff::new(data) else {
        return found;
    };
    let mut next = tiff.u32(4).unwrap_or(0);
    // A chain that loops back ends where it repeats.
    while next != 0 && !found.contains(&next) && found.len() < data.len() / 12 {
        let Some(entries) = tiff.u16(next as usize) else {
            break;
        };
        found.push(next);
        next = tiff
            .u32(next as usize + 2 + usize::from(entries) * 12)
            .unwrap_or(0);
    }
    found
}

/// Dots per inch as the file states them, else 96.
fn dpi(data: &[u8]) -> (f32, f32) {
    let be32 = |at: usize| Some(u32::from_be_bytes(data.get(at..at + 4)?.try_into().ok()?));
    let stated = || -> Option<(f32, f32)> {
        if data.starts_with(b"\x89PNG") {
            let mut at = 8;
            while let Some(length) = be32(at) {
                match data.get(at + 4..at + 8)? {
                    b"pHYs" if data.get(at + 16) == Some(&1) => {
                        return Some((
                            be32(at + 8)? as f32 * 0.0254,
                            be32(at + 12)? as f32 * 0.0254,
                        ));
                    }
                    b"IDAT" => break,
                    _ => at = at.checked_add(12 + length as usize)?,
                }
            }
            None
        } else if data.starts_with(&[0xff, 0xd8]) {
            let mut at = 2;
            let mut exif = None;
            while data.get(at) == Some(&0xff) {
                let marker = *data.get(at + 1)?;
                if marker == 0xda {
                    break;
                }
                let length = usize::from(u16::from_be_bytes(
                    data.get(at + 2..at + 4)?.try_into().ok()?,
                ));
                let body = data.get(at + 4..at + 2 + length)?;
                if marker == 0xe0 && body.starts_with(b"JFIF\0") && body.len() >= 12 {
                    let per_inch = match body[7] {
                        1 => Some(1.0),
                        2 => Some(2.54),
                        _ => None,
                    };
                    if let Some(k) = per_inch {
                        let at =
                            |i: usize| f32::from(u16::from_be_bytes([body[i], body[i + 1]])) * k;
                        return Some((at(8), at(10)));
                    }
                } else if marker == 0xe1 && body.starts_with(b"Exif\0\0") {
                    exif = Tiff::new(&body[6..]).and_then(|t| t.resolution());
                }
                at += 2 + length;
            }
            exif
        } else if data.starts_with(b"BM") {
            let le = |at: usize| Some(i32::from_le_bytes(data.get(at..at + 4)?.try_into().ok()?));
            Some((le(38)? as f32 * 0.0254, le(42)? as f32 * 0.0254))
        } else {
            Tiff::new(data)?.resolution()
        }
    };
    match stated() {
        Some((x, y)) if x.round() >= 1.0 && y.round() >= 1.0 => (x.round(), y.round()),
        _ => (96.0, 96.0),
    }
}
