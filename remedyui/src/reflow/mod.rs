//! Books and text documents. A format's reader turns its file into [`Block`]s; this module
//! lays them into pages with RemedyUI's text engine and draws them with its CPU renderer.
//! Pages are 400 x 600 pt with 11 pt text, as RemedyPDF 1.x (MuPDF) laid them out.

pub mod docx;
pub mod markup;
pub mod mobi;

use crate::pdf::Error;
use crate::source::Tiles;
use remedy_ui::core::{Color, CornerRadii, Point, Rect, Size};
use remedy_ui::pages::{PageText, TextRun};
use remedy_ui::paint::{Affine, Brush, DisplayList, Image, Item, Sampling};
use remedy_ui_engine::paint::GlyphRun;
use remedy_ui_engine::render_cpu::CpuRenderer;
use remedy_ui_text::{
    Align, FontCollection, GlyphRunInfo, LineHeight, ParagraphOptions, RichText, TextEngine,
    TextStyle, TextStylePatch,
};
use std::collections::HashMap;
use std::sync::{Arc, Mutex, PoisonError};

pub const PAGE_WIDTH: f32 = 400.0;
pub const PAGE_HEIGHT: f32 = 600.0;
pub const TEXT_SIZE: f32 = 11.0;
const TOP: f32 = 32.0;
const BOTTOM: f32 = PAGE_HEIGHT - 32.0;

const SERIF: [&str; 5] = [
    "Charis SIL",
    "Noto Serif",
    "Georgia",
    "Times New Roman",
    "serif",
];
const MONO: [&str; 5] = [
    "DejaVu Sans Mono",
    "Cascadia Mono",
    "Droid Sans Mono",
    "Consolas",
    "monospace",
];

fn families(mono: bool) -> Vec<String> {
    let list = if mono { MONO } else { SERIF };
    list.iter().map(|s| (*s).to_owned()).collect()
}

/// A stretch of text in one style.
#[derive(Clone, Debug, PartialEq)]
pub struct Inline {
    pub text: String,
    pub bold: bool,
    pub italic: bool,
    pub mono: bool,
    pub underline: bool,
    pub strike: bool,
    /// Times the block's size (sub and superscripts, `<small>`).
    pub scale: f32,
    pub color: Option<[u8; 3]>,
}

impl Default for Inline {
    fn default() -> Self {
        Inline {
            text: String::new(),
            bold: false,
            italic: false,
            mono: false,
            underline: false,
            strike: false,
            scale: 1.0,
            color: None,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Justify {
    #[default]
    Start,
    Center,
    End,
    Both,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Paragraph {
    pub inlines: Vec<Inline>,
    /// Points.
    pub size: f32,
    pub align: Justify,
    /// Space left of every line, in points.
    pub indent: f32,
    /// Space above and below; neighbours share the larger one.
    pub before: f32,
    pub after: f32,
    /// A list marker, set to the left of the first line.
    pub marker: Option<String>,
    /// Starts no lower than where a line of the following block also fits.
    pub keep_with_next: bool,
}

impl Default for Paragraph {
    fn default() -> Self {
        Paragraph {
            inlines: Vec::new(),
            size: TEXT_SIZE,
            align: Justify::Start,
            indent: 0.0,
            before: 0.0,
            after: 0.0,
            marker: None,
            keep_with_next: false,
        }
    }
}

#[derive(Clone, Debug)]
pub enum Block {
    Text(Paragraph),
    /// An encoded picture, with the width the document asks for, in points.
    Picture {
        data: Arc<[u8]>,
        width: Option<f32>,
        align: Justify,
    },
    /// Rows of cells.
    Table {
        rows: Vec<Vec<Vec<Block>>>,
        borders: bool,
    },
    Rule,
    PageBreak,
}

/// What a reader produces.
pub struct Content {
    pub blocks: Vec<Block>,
    /// Space left and right of the text, in points.
    pub margin: f32,
}

#[derive(Clone)]
enum Op {
    Glyphs(GlyphRunInfo, Point),
    Fill(Rect, Color),
    Picture(Image, Rect),
}

impl Op {
    fn moved(mut self, dx: f32, dy: f32) -> Op {
        let shift = |r: Rect| Rect::new(r.min.x + dx, r.min.y + dy, r.max.x + dx, r.max.y + dy);
        match &mut self {
            Op::Glyphs(_, at) => *at = Point::new(at.x + dx, at.y + dy),
            Op::Fill(rect, _) | Op::Picture(_, rect) => *rect = shift(*rect),
        }
        self
    }
}

#[derive(Default)]
struct Sheet {
    ops: Vec<Op>,
    runs: Vec<TextRun>,
}

/// Where blocks are being placed: the book's pages, or one endless sheet for a table cell.
struct Flow {
    done: Vec<Sheet>,
    sheet: Sheet,
    x: f32,
    width: f32,
    top: f32,
    bottom: f32,
    y: f32,
    /// Space owed below the last block.
    owed: f32,
}

impl Flow {
    fn new(x: f32, width: f32, top: f32, bottom: f32) -> Flow {
        Flow {
            done: Vec::new(),
            sheet: Sheet::default(),
            x,
            width,
            top,
            bottom,
            y: top,
            owed: 0.0,
        }
    }

    fn at_top(&self) -> bool {
        self.sheet.ops.is_empty()
    }

    fn turn(&mut self) {
        if !self.at_top() {
            self.done.push(std::mem::take(&mut self.sheet));
        }
        self.y = self.top;
        self.owed = 0.0;
    }

    /// Moves down for a block's top space, and to a new page if `height` does not fit.
    fn room(&mut self, before: f32, height: f32) {
        if !self.at_top() {
            self.y += self.owed.max(before);
        }
        self.owed = 0.0;
        if self.y + height > self.bottom && !self.at_top() {
            self.turn();
        }
    }
}

struct Layout {
    engine: TextEngine,
    pictures: HashMap<usize, Option<Image>>,
}

fn patch(inline: &Inline, size: f32) -> TextStylePatch {
    let mut patch = TextStylePatch::default();
    patch.families = inline.mono.then(|| families(true));
    patch.weight = inline.bold.then_some(700.0);
    patch.italic = inline.italic.then_some(true);
    patch.underline = inline.underline.then_some(true);
    patch.strikethrough = inline.strike.then_some(true);
    patch.size = (inline.scale != 1.0).then_some(size * inline.scale);
    patch.color = inline.color.map(|[r, g, b]| Color::rgb8(r, g, b));
    patch
}

impl Layout {
    fn shape(
        &mut self,
        inlines: &[Inline],
        size: f32,
        width: f32,
        align: Justify,
    ) -> (String, remedy_ui_text::Paragraph) {
        let mut rich = RichText::new();
        let mut text = String::new();
        for inline in inlines {
            text.push_str(&inline.text);
            rich.push_styled(&inline.text, patch(inline, size));
        }
        let mut style = TextStyle::default();
        // A paragraph that is all monospaced takes its line height from that face.
        style.families = families(!inlines.is_empty() && inlines.iter().all(|i| i.mono));
        style.size = size;
        style.line_height = LineHeight::Relative(1.2);
        let mut options = ParagraphOptions::default()
            .max_width(width.max(size))
            .align(match align {
                Justify::Start => Align::Start,
                Justify::Center => Align::Center,
                Justify::End => Align::End,
                Justify::Both => Align::Justify,
            });
        // Shaped at four times the size so hinting cannot disturb the layout.
        options.scale = 4.0;
        options.snap = false;
        (text, self.engine.layout(&rich, &style, options))
    }

    fn block(&mut self, flow: &mut Flow, block: &Block, next: Option<&Block>) {
        match block {
            Block::Text(p) => self.paragraph(flow, p, next.is_some()),
            Block::Picture { data, width, align } => self.picture(flow, data, *width, *align),
            Block::Table { rows, borders } => self.table(flow, rows, *borders),
            Block::Rule => {
                flow.room(6.0, 1.0);
                let line = Rect::new(flow.x, flow.y, flow.x + flow.width, flow.y + 0.75);
                flow.sheet
                    .ops
                    .push(Op::Fill(line, Color::rgb8(128, 128, 128)));
                flow.y += 0.75;
                flow.owed = 6.0;
            }
            Block::PageBreak => flow.turn(),
        }
    }

    fn paragraph(&mut self, flow: &mut Flow, p: &Paragraph, has_next: bool) {
        let indent = p.indent.min(flow.width / 2.0);
        let (text, shaped) = self.shape(&p.inlines, p.size, flow.width - indent, p.align);
        if text.is_empty() {
            return;
        }
        let lines = shaped.lines();
        let runs = shaped.glyph_runs();
        for (n, line) in lines.iter().enumerate() {
            let height = line.bottom - line.top;
            let extra = if p.keep_with_next && has_next && n == 0 {
                height * 2.5
            } else {
                0.0
            };
            if n == 0 {
                flow.room(p.before, height + extra);
            } else if flow.y + height > flow.bottom {
                flow.turn();
            }
            let origin = Point::new(flow.x + indent, flow.y - line.top);
            if let (0, Some(marker)) = (n, &p.marker) {
                let inline = Inline {
                    text: marker.clone(),
                    ..Inline::default()
                };
                let (_, mark) = self.shape(&[inline], p.size, flow.width, Justify::Start);
                let at = Point::new(origin.x - mark.width() - p.size * 0.5, origin.y);
                // Aligned on the first line's baseline.
                let lift = line.baseline - mark.first_baseline().unwrap_or(line.baseline);
                for run in mark.glyph_runs() {
                    flow.sheet
                        .ops
                        .push(Op::Glyphs(run, Point::new(at.x, at.y + lift)));
                }
            }
            let mine: Vec<&GlyphRunInfo> = runs
                .iter()
                .filter(|r| line.range.contains(&r.range.start))
                .collect();
            for run in &mine {
                flow.sheet.ops.push(Op::Glyphs((*run).clone(), origin));
            }
            if let Some(run) = text_run(&text, line, &mine, origin, flow.y, height) {
                flow.sheet.runs.push(run);
            }
            flow.y += height;
        }
        flow.owed = p.after;
    }

    fn decode(&mut self, data: &Arc<[u8]>) -> Option<Image> {
        self.pictures
            .entry(Arc::as_ptr(data).cast::<u8>() as usize)
            .or_insert_with(|| {
                let mut reader = image::ImageReader::new(std::io::Cursor::new(&data[..]))
                    .with_guessed_format()
                    .ok()?;
                let mut limits = image::Limits::default();
                limits.max_alloc = Some(512 << 20);
                reader.limits(limits);
                let mut pixels = reader.decode().ok()?.into_rgba8();
                for p in pixels.pixels_mut() {
                    let a = u32::from(p.0[3]);
                    for c in &mut p.0[..3] {
                        *c = ((u32::from(*c) * a + 127) / 255) as u8;
                    }
                }
                let (w, h) = pixels.dimensions();
                Some(Image::new(w, h, Arc::from(pixels.into_raw())))
            })
            .clone()
    }

    fn picture(&mut self, flow: &mut Flow, data: &Arc<[u8]>, width: Option<f32>, align: Justify) {
        let Some(image) = self.decode(data) else {
            return;
        };
        let (w, h) = (image.width as f32, image.height as f32);
        if w < 1.0 || h < 1.0 {
            return;
        }
        // 96 pixels to the inch unless the document says how wide.
        let wanted = width.unwrap_or(w * 0.75).min(flow.width);
        let tallest = (BOTTOM - TOP).min(flow.bottom - flow.top);
        let scale = (wanted / w).min(tallest / h);
        let (w, h) = (w * scale, h * scale);
        flow.room(4.0, h);
        let x = flow.x
            + match align {
                Justify::Center => (flow.width - w) / 2.0,
                Justify::End => flow.width - w,
                _ => 0.0,
            };
        flow.sheet
            .ops
            .push(Op::Picture(image, Rect::new(x, flow.y, x + w, flow.y + h)));
        flow.y += h;
        flow.owed = 4.0;
    }

    fn table(&mut self, flow: &mut Flow, rows: &[Vec<Vec<Block>>], borders: bool) {
        let columns = rows.iter().map(Vec::len).max().unwrap_or(0);
        if columns == 0 {
            return;
        }
        // Columns share the width by how much text they hold, none thinner than a share of it.
        let mut weight = vec![1.0f32; columns];
        for row in rows {
            for (i, cell) in row.iter().enumerate() {
                weight[i] = weight[i].max(text_length(cell) as f32);
            }
        }
        let weight: Vec<f32> = weight.iter().map(|w| w.sqrt()).collect();
        let total: f32 = weight.iter().sum();
        let least = flow.width / columns as f32 * 0.4;
        let spare = flow.width - least * columns as f32;
        let widths: Vec<f32> = weight.iter().map(|w| least + spare * w / total).collect();
        const PAD: f32 = 3.0;
        flow.room(6.0, 0.0);
        for row in rows {
            let mut cells = Vec::new();
            let mut height = TEXT_SIZE;
            let mut x = flow.x;
            for (i, width) in widths.iter().enumerate() {
                let mut cell = Flow::new(x + PAD, (width - 2.0 * PAD).max(1.0), 0.0, f32::INFINITY);
                if let Some(blocks) = row.get(i) {
                    self.blocks(&mut cell, blocks);
                }
                height = height.max(cell.y);
                cells.push(cell);
                x += width;
            }
            let height = height + 2.0 * PAD;
            if height > flow.bottom - flow.top {
                // A row taller than a page: its cells follow one another and break normally.
                for cell in row {
                    self.blocks(flow, cell);
                }
                continue;
            }
            flow.room(0.0, height);
            let top = flow.y;
            if borders {
                let gray = Color::rgb8(150, 150, 150);
                let right = flow.x + flow.width;
                for y in [top, top + height] {
                    flow.sheet
                        .ops
                        .push(Op::Fill(Rect::new(flow.x, y, right, y + 0.5), gray));
                }
                let mut x = flow.x;
                for width in widths.iter().chain([&0.0]) {
                    flow.sheet
                        .ops
                        .push(Op::Fill(Rect::new(x, top, x + 0.5, top + height), gray));
                    x += width;
                }
            }
            for cell in cells {
                let down = top + PAD;
                flow.sheet
                    .ops
                    .extend(cell.sheet.ops.into_iter().map(|op| op.moved(0.0, down)));
                for mut run in cell.sheet.runs {
                    run.bounds.min.y += down;
                    run.bounds.max.y += down;
                    for r in &mut run.chars {
                        r.min.y += down;
                        r.max.y += down;
                    }
                    flow.sheet.runs.push(run);
                }
            }
            // An empty row with no borders still takes its place.
            if flow.sheet.ops.is_empty() {
                flow.sheet
                    .ops
                    .push(Op::Fill(Rect::new(flow.x, top, flow.x, top), Color::WHITE));
            }
            flow.y += height;
        }
        flow.owed = 6.0;
    }

    fn blocks(&mut self, flow: &mut Flow, blocks: &[Block]) {
        for (i, block) in blocks.iter().enumerate() {
            self.block(flow, block, blocks.get(i + 1));
        }
    }
}

fn text_length(blocks: &[Block]) -> usize {
    blocks
        .iter()
        .map(|b| match b {
            Block::Text(p) => p.inlines.iter().map(|i| i.text.chars().count()).sum(),
            Block::Table { rows, .. } => rows.iter().flatten().map(|c| text_length(c)).sum(),
            Block::Picture { .. } => 20,
            _ => 0,
        })
        .sum()
}

/// The line as selectable text, with a box for each character.
fn text_run(
    text: &str,
    line: &remedy_ui_text::LineInfo,
    runs: &[&GlyphRunInfo],
    origin: Point,
    top: f32,
    height: f32,
) -> Option<TextRun> {
    let shown = text.get(line.range.clone())?.trim_end();
    if shown.is_empty() {
        return None;
    }
    let mut at = HashMap::new();
    for run in runs {
        for ((glyph, advance), cluster) in run.glyphs.iter().zip(&run.advances).zip(&run.clusters) {
            let span = at.entry(*cluster).or_insert((glyph.x, glyph.x + advance));
            span.0 = span.0.min(glyph.x);
            span.1 = span.1.max(glyph.x + advance);
        }
    }
    let mut end = line.left;
    let chars: Vec<Rect> = shown
        .char_indices()
        .map(|(i, _)| {
            // A character inside a ligature shares the box before it.
            let (a, b) = at
                .get(&(line.range.start + i))
                .copied()
                .unwrap_or((end, end));
            end = b;
            Rect::new(origin.x + a, top, origin.x + b, top + height)
        })
        .collect();
    let left = chars.iter().map(|r| r.min.x).fold(f32::INFINITY, f32::min);
    let right = chars.iter().map(|r| r.max.x).fold(left, f32::max);
    let mut run = TextRun::new(shown, Rect::new(left, top, right, top + height));
    run.chars = chars;
    Some(run)
}

fn drawing(ops: Vec<Op>) -> DisplayList {
    let mut list = DisplayList::new();
    for op in ops {
        match op {
            Op::Fill(rect, color) => list.fill_rect(rect, Brush::Solid(color)),
            Op::Picture(image, rect) => list.push(Item::Image {
                image,
                rect,
                radii: CornerRadii::all(0.0),
                sampling: Sampling::Linear,
            }),
            Op::Glyphs(run, origin) => {
                let color = run.color;
                for bar in [run.underline, run.strikethrough].into_iter().flatten() {
                    list.fill_rect(bar.translate(origin.to_vec2()), Brush::Solid(color));
                }
                list.push(Item::Glyphs(GlyphRun {
                    font: run.font,
                    size: run.size,
                    color,
                    glyphs: run
                        .glyphs
                        .iter()
                        .map(|g| (g.id, Point::new(origin.x + g.x, origin.y + g.y)))
                        .collect(),
                    hinting: remedy_ui_text::Hinting::None,
                    antialias: remedy_ui_text::Antialias::Grayscale,
                }));
            }
        }
    }
    list
}

/// A laid-out book.
pub struct Book {
    pages: Vec<(DisplayList, PageText)>,
    renderer: Mutex<CpuRenderer>,
}

impl Book {
    pub fn new(content: &Content) -> Result<Book, Error> {
        let mut fonts = FontCollection::with_system_fonts();
        // Faces that are always there, for systems with few of their own.
        for face in remedy_ui_fonts::all() {
            if !face.data.is_empty() {
                // A face that fails to load leaves the system's to serve.
                let _ = fonts.add_static(face.data);
            }
        }
        let mut layout = Layout {
            engine: TextEngine::new(fonts),
            pictures: HashMap::new(),
        };
        let mut flow = Flow::new(
            content.margin,
            PAGE_WIDTH - 2.0 * content.margin,
            TOP,
            BOTTOM,
        );
        layout.blocks(&mut flow, &content.blocks);
        flow.turn();
        if flow.done.is_empty() {
            return Err(Error::Empty);
        }
        let pages = flow
            .done
            .into_iter()
            .map(|sheet| (drawing(sheet.ops), PageText { runs: sheet.runs }))
            .collect();
        Ok(Book {
            pages,
            renderer: Mutex::default(),
        })
    }
}

impl Tiles for Book {
    fn count(&self) -> usize {
        self.pages.len()
    }

    fn size(&self, page: usize) -> Option<Size> {
        (page < self.pages.len()).then(|| Size::new(PAGE_WIDTH, PAGE_HEIGHT))
    }

    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error> {
        let (list, _) = self
            .pages
            .get(page)
            .ok_or_else(|| Error::Other("no such page".into()))?;
        let base = Affine([
            scale,
            0.0,
            0.0,
            scale,
            -region.min.x * scale,
            -region.min.y * scale,
        ]);
        let frame = self
            .renderer
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .render_with(list, width, height, base, Color::WHITE)
            .map_err(|e| Error::Other(format!("{e:?}")))?;
        Ok(Image::new(width, height, Arc::from(frame.pixels)))
    }

    fn runs(&self, page: usize) -> Option<PageText> {
        let (_, text) = self.pages.get(page)?;
        (!text.runs.is_empty()).then(|| text.clone())
    }
}

crate::source::page_source!(Book);
