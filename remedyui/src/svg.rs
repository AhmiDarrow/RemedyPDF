//! An SVG file as a one-page document, drawn as vectors at every zoom.

use crate::pdf::Error;
use crate::source::Tiles;
use remedy_ui::core::{Rect, Size};
use remedy_ui::paint::Image;
use resvg::{tiny_skia, usvg};
use std::sync::Arc;

pub struct Svg {
    tree: usvg::Tree,
}

impl Svg {
    /// The parser gets no folder: a document must not read other files.
    pub fn new(bytes: &[u8]) -> Result<Svg, Error> {
        let mut options = usvg::Options::default();
        options.image_href_resolver.resolve_string = Box::new(|_, _| None);
        options.fontdb_mut().load_system_fonts();
        let tree =
            usvg::Tree::from_data(bytes, &options).map_err(|e| Error::Other(e.to_string()))?;
        Ok(Svg { tree })
    }
}

impl Tiles for Svg {
    fn count(&self) -> usize {
        1
    }

    fn size(&self, page: usize) -> Option<Size> {
        let size = self.tree.size();
        (page == 0).then(|| Size::new(size.width(), size.height()))
    }

    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error> {
        if page != 0 {
            return Err(Error::Other("no such page".into()));
        }
        let mut pixmap = tiny_skia::Pixmap::new(width, height)
            .ok_or_else(|| Error::Other("the tile is empty or too large".into()))?;
        pixmap.fill(tiny_skia::Color::WHITE);
        let transform = tiny_skia::Transform::from_row(
            scale,
            0.0,
            0.0,
            scale,
            -region.min.x * scale,
            -region.min.y * scale,
        );
        resvg::render(&self.tree, transform, &mut pixmap.as_mut());
        Ok(Image::new(width, height, Arc::from(pixmap.take())))
    }
}

crate::source::page_source!(Svg);
