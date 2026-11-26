//! What every format gives the app: pages that draw in tiles.

use crate::pdf::Error;
use remedy_ui::core::{Rect, Size};
use remedy_ui::pages::{PageSource, PageText};
use remedy_ui::paint::Image;

/// A format's pages. Points are the page as displayed: origin top-left, y down.
pub trait Tiles {
    fn count(&self) -> usize;
    fn size(&self, page: usize) -> Option<Size>;

    fn sizes(&self) -> Vec<Size> {
        (0..self.count()).filter_map(|p| self.size(p)).collect()
    }

    /// The part `region` of a page at `scale` pixels per point, as `width` x `height` pixels.
    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error>;

    fn runs(&self, page: usize) -> Option<PageText> {
        let _ = page;
        None
    }
}

/// Any open document, as the page view and PDF export use it.
pub trait Pages: Tiles + PageSource {}
impl<T: Tiles + PageSource> Pages for T {}

/// A blank white tile.
pub(crate) fn white(width: u32, height: u32) -> Vec<u8> {
    vec![255; width as usize * height as usize * 4]
}

/// RemedyUI's `PageSource` from `Tiles`.
macro_rules! page_source {
    ($type:ty) => {
        impl remedy_ui::pages::PageSource for $type {
            fn page_count(&self) -> usize {
                $crate::source::Tiles::count(self)
            }

            fn page_size(&self, page: usize) -> remedy_ui::core::Size {
                $crate::source::Tiles::size(self, page)
                    .unwrap_or(remedy_ui::core::Size::new(612.0, 792.0))
            }

            fn render(
                &self,
                r: &remedy_ui::pages::RenderRequest,
                cancel: &remedy_ui::pages::Cancel,
            ) -> Result<remedy_ui::paint::Image, remedy_ui::pages::RenderError> {
                if cancel.is_cancelled() {
                    return Err(remedy_ui::pages::RenderError::Cancelled);
                }
                $crate::source::Tiles::render_tile(
                    self, r.page, r.region, r.scale, r.width, r.height,
                )
                .map_err(|e| remedy_ui::pages::RenderError::Failed(e.to_string()))
            }

            fn text(&self, page: usize) -> Option<remedy_ui::pages::PageText> {
                $crate::source::Tiles::runs(self, page)
            }
        }
    };
}
pub(crate) use page_source;
