//! Opens any supported file by its extension.

use crate::pdf::{Error, PdfFile};
use crate::pictures::Pictures;
use crate::reflow::{self, Book};
use crate::source::Pages;
use crate::svg::Svg;
use crate::xps::Xps;
use std::path::Path;
use std::sync::Arc;

pub enum Document {
    /// Can be edited and saved.
    Pdf(Arc<PdfFile>),
    /// Read only; saving exports a PDF.
    Fixed(Arc<dyn Pages>),
}

impl Document {
    pub fn open(path: &Path, password: Option<&str>) -> Result<Document, Error> {
        let extension = path
            .extension()
            .map(|e| e.to_string_lossy().to_ascii_lowercase());
        let read = || std::fs::read(path).map_err(|e| Error::Other(e.to_string()));
        let fixed = |pages: Arc<dyn Pages>| Ok(Document::Fixed(pages));
        match extension.as_deref() {
            Some("pdf") => Ok(Document::Pdf(Arc::new(PdfFile::from_bytes(
                read()?,
                password,
            )?))),
            Some("png" | "jpg" | "jpeg" | "bmp" | "gif" | "tif" | "tiff" | "webp") => {
                fixed(Arc::new(Pictures::image(read()?)?))
            }
            Some("cbz") => fixed(Arc::new(Pictures::cbz(read()?)?)),
            Some("cbr") => fixed(Arc::new(Pictures::cbr(read()?, password)?)),
            Some("svg") => fixed(Arc::new(Svg::new(&read()?)?)),
            Some("txt") => fixed(Arc::new(Book::new(&reflow::markup::text(&read()?))?)),
            Some("html" | "htm" | "xhtml") => {
                fixed(Arc::new(Book::new(&reflow::markup::html(&read()?, path))?))
            }
            Some("epub") => fixed(Arc::new(Book::new(&reflow::markup::epub(read()?)?)?)),
            Some("fb2") => fixed(Arc::new(Book::new(&reflow::markup::fb2(&read()?)?)?)),
            Some("mobi") => fixed(Arc::new(Book::new(&reflow::markup::mobi(&read()?)?)?)),
            Some("xps" | "oxps") => fixed(Arc::new(Xps::new(read()?)?)),
            Some("docx") => fixed(Arc::new(Book::new(&reflow::docx::docx(read()?)?)?)),
            other => Err(Error::Other(format!(
                "{} files are not supported",
                other.unwrap_or("these")
            ))),
        }
    }

    pub fn pages(&self) -> Arc<dyn Pages> {
        match self {
            Document::Pdf(file) => file.clone(),
            Document::Fixed(pages) => pages.clone(),
        }
    }
}
