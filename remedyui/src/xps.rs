//! XPS and OpenXPS: fixed pages of paths, glyphs, pictures and gradients in a zip package.
//! As RemedyPDF 1.x (MuPDF): JPEG XR pictures are not drawn, and a canvas's opacity applies to
//! each thing in it rather than to the group.

use crate::pdf::Error;
use crate::reflow::markup::{decode, parse_xml};
use crate::source::Tiles;
use crate::zipped::Package;
use remedy_ui::core::{Rect, Size};
use remedy_ui::pages::{PageText, TextRun};
use remedy_ui::paint::Image;
use resvg::tiny_skia::{
    Color, FillRule, FilterQuality, GradientStop, LineCap, LineJoin, LinearGradient, Mask, Paint,
    Path, PathBuilder, Pattern, Pixmap, PixmapPaint, Point, RadialGradient, Shader, SpreadMode,
    Stroke, StrokeDash, Transform,
};
use roxmltree::Node;
use std::collections::HashMap;
use std::sync::Arc;

/// XPS measures in 96ths of an inch.
const POINTS: f32 = 0.75;
const DEEPEST: usize = 64;

fn other(e: impl std::fmt::Display) -> Error {
    Error::Other(e.to_string())
}

#[derive(Clone)]
enum Fill {
    Solid(Color),
    Linear {
        from: Point,
        to: Point,
        stops: Vec<GradientStop>,
        spread: SpreadMode,
        transform: Transform,
    },
    Radial {
        origin: Point,
        center: Point,
        radius: f32,
        stops: Vec<GradientStop>,
        spread: SpreadMode,
        transform: Transform,
    },
    /// Drawings repeated as a brush: `area` of them (`viewbox`) shown in `viewport`.
    Visual {
        items: Arc<Vec<Item>>,
        viewbox: [f32; 4],
        viewport: [f32; 4],
        transform: Transform,
        tile: Tiling,
        opacity: f32,
    },
    /// `transform` takes picture pixels to the shape's coordinates.
    Picture {
        pixels: Arc<Pixmap>,
        transform: Transform,
        tile: Tiling,
        area: Path,
        opacity: f32,
    },
}

impl Fill {
    fn faded(mut self, by: f32) -> Fill {
        let fade = |c: &mut Color| c.set_alpha((c.alpha() * by).clamp(0.0, 1.0));
        match &mut self {
            Fill::Solid(color) => fade(color),
            // `GradientStop` is opaque: stops are faded where they are read.
            Fill::Linear { .. } | Fill::Radial { .. } => {}
            Fill::Picture { opacity, .. } | Fill::Visual { opacity, .. } => *opacity *= by,
        }
        self
    }
}

#[derive(Clone)]
struct Clip {
    path: Path,
    rule: FillRule,
    transform: Transform,
}

#[derive(Clone)]
struct Draw {
    path: Path,
    rule: FillRule,
    fill: Fill,
    /// Set to stroke the path instead of filling it.
    stroke: Option<Stroke>,
    transform: Transform,
    clips: Arc<Vec<Clip>>,
}

/// One thing on a page.
#[derive(Clone)]
enum Item {
    Draw(Box<Draw>),
    /// Things shown only as far as the brush `mask` is opaque there (an `OpacityMask`).
    Masked {
        mask: Box<Fill>,
        transform: Transform,
        items: Vec<Item>,
    },
}

/// How a brush repeats.
#[derive(Clone, Copy, PartialEq)]
enum Tiling {
    Once,
    Repeat,
    /// Every other tile mirrored across, down, or both.
    Mirror {
        across: bool,
        down: bool,
    },
}

fn tiling(node: Node) -> Tiling {
    match node.attribute("TileMode") {
        Some("Tile") => Tiling::Repeat,
        Some("FlipX") => Tiling::Mirror {
            across: true,
            down: false,
        },
        Some("FlipY") => Tiling::Mirror {
            across: false,
            down: true,
        },
        Some("FlipXY") => Tiling::Mirror {
            across: true,
            down: true,
        },
        _ => Tiling::Once,
    }
}

struct Page {
    size: Size,
    draws: Vec<Item>,
    runs: Vec<TextRun>,
}

pub struct Xps {
    pages: Vec<Page>,
}

// ---- The package ----

/// The folder a part is in, with its trailing slash.
fn folder(part: &str) -> &str {
    &part[..part.rfind('/').map_or(0, |i| i + 1)]
}

/// A reference made from the part `from`, as a name in the zip.
fn resolve(from: &str, reference: &str) -> String {
    let reference = reference.split(['#', '?']).next().unwrap_or("");
    let whole = match reference.strip_prefix('/') {
        Some(absolute) => absolute.to_owned(),
        None => format!("{}{reference}", folder(from)),
    };
    let mut parts = Vec::new();
    for part in whole.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                parts.pop();
            }
            p => parts.push(p),
        }
    }
    parts.join("/")
}

/// A part, which a package may store whole or in numbered pieces.
fn part(package: &mut Package, name: &str) -> Option<Vec<u8>> {
    if let Some(data) = package.read(name) {
        return Some(data);
    }
    let mut whole = Vec::new();
    for n in 0.. {
        if let Some(piece) = package.read(&format!("{name}/[{n}].piece")) {
            whole.extend(piece);
        } else {
            whole.extend(package.read(&format!("{name}/[{n}].last.piece"))?);
            break;
        }
    }
    Some(whole)
}

/// The `Source` or `Target` of every element called `tag` in the part.
fn references(
    package: &mut Package,
    name: &str,
    tag: &str,
) -> Result<Vec<(String, String)>, Error> {
    let data = part(package, name).ok_or_else(|| other(format!("the package has no {name}")))?;
    let text = decode(&data);
    let doc = parse_xml(&text)?;
    Ok(doc
        .descendants()
        .filter(|n| n.tag_name().name() == tag)
        .filter_map(|n| {
            let target = n.attribute("Source").or_else(|| n.attribute("Target"))?;
            Some((
                n.attribute("Type").unwrap_or("").to_owned(),
                resolve(name, target),
            ))
        })
        .collect())
}

// ---- Values ----

fn numbers(text: &str) -> Vec<f32> {
    text.split([',', ' ', '\t', '\n', '\r'])
        .filter(|s| !s.is_empty())
        .map_while(|s| s.parse::<f32>().ok().filter(|v| v.is_finite()))
        .collect()
}

fn matrix(text: &str) -> Option<Transform> {
    match numbers(text)[..] {
        [a, b, c, d, e, f] => Some(Transform::from_row(a, b, c, d, e, f)),
        _ => None,
    }
}

fn point(text: &str) -> Option<Point> {
    match numbers(text)[..] {
        [x, y] => Some(Point::from_xy(x, y)),
        _ => None,
    }
}

fn color(text: &str) -> Option<Color> {
    let text = text.trim();
    if let Some(hex) = text.strip_prefix('#').filter(|h| h.is_ascii()) {
        let byte = |i: usize| u8::from_str_radix(hex.get(i..i + 2)?, 16).ok();
        return match hex.len() {
            6 => Some(Color::from_rgba8(byte(0)?, byte(2)?, byte(4)?, 255)),
            8 => Some(Color::from_rgba8(byte(2)?, byte(4)?, byte(6)?, byte(0)?)),
            _ => None,
        };
    }
    // Linear light: `sc#r,g,b` or `sc#a,r,g,b`.
    let linear = |v: f32| {
        let v = v.clamp(0.0, 1.0);
        if v <= 0.003_130_8 {
            v * 12.92
        } else {
            1.055 * v.powf(1.0 / 2.4) - 0.055
        }
    };
    if let Some(values) = text.strip_prefix("sc#") {
        return match numbers(values)[..] {
            [r, g, b] => Color::from_rgba(linear(r), linear(g), linear(b), 1.0),
            [a, r, g, b] => Color::from_rgba(linear(r), linear(g), linear(b), a.clamp(0.0, 1.0)),
            _ => None,
        };
    }
    // `ContextColor /profile.icc a,c1,c2,..`: without the profile, read CMYK or RGB directly.
    let values = numbers(text.strip_prefix("ContextColor ")?.split_once(' ')?.1);
    let channel = |v: f32| v.clamp(0.0, 1.0);
    match values[..] {
        [a, c, m, y, k] => Color::from_rgba(
            channel((1.0 - c) * (1.0 - k)),
            channel((1.0 - m) * (1.0 - k)),
            channel((1.0 - y) * (1.0 - k)),
            channel(a),
        ),
        [a, r, g, b] => Color::from_rgba(channel(r), channel(g), channel(b), channel(a)),
        _ => None,
    }
}

// ---- Geometry ----

/// An elliptical arc as cubic curves, by the SVG endpoint rules, which XPS shares.
fn arc(
    path: &mut PathBuilder,
    from: Point,
    radius: Point,
    degrees: f32,
    large: bool,
    clockwise: bool,
    to: Point,
) {
    let (mut rx, mut ry) = (radius.x.abs(), radius.y.abs());
    if rx < 1e-6 || ry < 1e-6 || from == to {
        path.line_to(to.x, to.y);
        return;
    }
    let (sin, cos) = degrees.to_radians().sin_cos();
    let (dx, dy) = ((from.x - to.x) / 2.0, (from.y - to.y) / 2.0);
    let (x, y) = (cos * dx + sin * dy, -sin * dx + cos * dy);
    let grow = (x / rx).powi(2) + (y / ry).powi(2);
    if grow > 1.0 {
        rx *= grow.sqrt();
        ry *= grow.sqrt();
    }
    let under = (rx * y).powi(2) + (ry * x).powi(2);
    let mut k = (((rx * ry).powi(2) - under) / under).max(0.0).sqrt();
    if large == clockwise {
        k = -k;
    }
    let (cx, cy) = (k * rx * y / ry, -k * ry * x / rx);
    let center = Point::from_xy(
        cos * cx - sin * cy + (from.x + to.x) / 2.0,
        sin * cx + cos * cy + (from.y + to.y) / 2.0,
    );
    let angle = |x: f32, y: f32| y.atan2(x);
    let start = angle((x - cx) / rx, (y - cy) / ry);
    let mut sweep = angle((-x - cx) / rx, (-y - cy) / ry) - start;
    if clockwise && sweep < 0.0 {
        sweep += std::f32::consts::TAU;
    } else if !clockwise && sweep > 0.0 {
        sweep -= std::f32::consts::TAU;
    }
    let pieces = (sweep.abs() / std::f32::consts::FRAC_PI_2).ceil().max(1.0);
    let step = sweep / pieces;
    let handle = 4.0 / 3.0 * (step / 4.0).tan();
    let on = |u: f32, v: f32| {
        Point::from_xy(
            center.x + cos * rx * u - sin * ry * v,
            center.y + sin * rx * u + cos * ry * v,
        )
    };
    for n in 0..pieces as usize {
        let (a, b) = (start + step * n as f32, start + step * (n + 1) as f32);
        let (sa, ca, sb, cb) = (a.sin(), a.cos(), b.sin(), b.cos());
        let first = on(ca - handle * sa, sa + handle * ca);
        let second = on(cb + handle * sb, sb - handle * cb);
        let end = if n + 1 == pieces as usize {
            to
        } else {
            on(cb, sb)
        };
        path.cubic_to(first.x, first.y, second.x, second.y, end.x, end.y);
    }
}

/// The abbreviated geometry syntax (`F1 M 0,0 L 10,10 z`).
fn geometry(text: &str) -> (Option<Path>, FillRule) {
    let mut path = PathBuilder::new();
    let mut rule = FillRule::EvenOdd;
    let mut chars = text.char_indices().peekable();
    let mut command = ' ';
    let (mut at, mut start) = (Point::zero(), Point::zero());
    // The last cubic's second control point, for `S`.
    let mut smooth: Option<Point> = None;
    let skip = |chars: &mut std::iter::Peekable<std::str::CharIndices>| {
        while chars
            .peek()
            .is_some_and(|(_, c)| c.is_whitespace() || *c == ',')
        {
            chars.next();
        }
    };
    let number = |chars: &mut std::iter::Peekable<std::str::CharIndices>| -> Option<f32> {
        skip(chars);
        let begin = chars.peek()?.0;
        let mut end = begin;
        let (mut dot, mut exponent, mut last) = (false, false, ' ');
        while let Some(&(i, c)) = chars.peek() {
            let part = c.is_ascii_digit()
                || ((c == '+' || c == '-') && (i == begin || last == 'e' || last == 'E'))
                || (c == '.' && !dot && !exponent)
                || ((c == 'e' || c == 'E') && !exponent && i != begin);
            if !part {
                break;
            }
            dot |= c == '.';
            exponent |= c == 'e' || c == 'E';
            last = c;
            end = i + 1;
            chars.next();
        }
        text.get(begin..end)?
            .parse::<f32>()
            .ok()
            .filter(|v| v.is_finite())
    };
    loop {
        skip(&mut chars);
        let Some(&(_, c)) = chars.peek() else { break };
        if c.is_ascii_alphabetic() {
            command = c;
            chars.next();
        }
        let relative = command.is_ascii_lowercase();
        let base = if relative { at } else { Point::zero() };
        macro_rules! next {
            () => {
                match number(&mut chars) {
                    Some(v) => v,
                    None => break,
                }
            };
        }
        macro_rules! pair {
            () => {{
                let x = next!();
                let y = next!();
                Point::from_xy(base.x + x, base.y + y)
            }};
        }
        let mut control = None;
        match command.to_ascii_uppercase() {
            'F' => {
                rule = if next!() == 1.0 {
                    FillRule::Winding
                } else {
                    FillRule::EvenOdd
                }
            }
            'M' => {
                at = pair!();
                start = at;
                path.move_to(at.x, at.y);
                // More pairs after a move are lines.
                command = if relative { 'l' } else { 'L' };
            }
            'L' => {
                at = pair!();
                path.line_to(at.x, at.y);
            }
            'H' => {
                at.x = base.x + next!();
                path.line_to(at.x, at.y);
            }
            'V' => {
                at.y = base.y + next!();
                path.line_to(at.x, at.y);
            }
            'C' => {
                let (a, b, end) = (pair!(), pair!(), pair!());
                path.cubic_to(a.x, a.y, b.x, b.y, end.x, end.y);
                (at, control) = (end, Some(b));
            }
            'S' => {
                let a = smooth.map_or(at, |c| Point::from_xy(2.0 * at.x - c.x, 2.0 * at.y - c.y));
                let (b, end) = (pair!(), pair!());
                path.cubic_to(a.x, a.y, b.x, b.y, end.x, end.y);
                (at, control) = (end, Some(b));
            }
            'Q' => {
                let (a, end) = (pair!(), pair!());
                path.quad_to(a.x, a.y, end.x, end.y);
                at = end;
            }
            'A' => {
                let rx = next!();
                let ry = next!();
                let degrees = next!();
                let large = next!() != 0.0;
                let clockwise = next!() != 0.0;
                let end = pair!();
                arc(
                    &mut path,
                    at,
                    Point::from_xy(rx, ry),
                    degrees,
                    large,
                    clockwise,
                    end,
                );
                at = end;
            }
            'Z' => {
                path.close();
                at = start;
                command = ' ';
            }
            _ => break,
        }
        smooth = control;
    }
    (path.finish(), rule)
}

/// A `PathGeometry` element, rewritten in the abbreviated syntax.
fn figures(node: Node) -> String {
    let mut out = String::new();
    if node.attribute("FillRule") == Some("NonZero") {
        out.push_str("F1 ");
    }
    if let Some(short) = node.attribute("Figures") {
        out.push_str(short);
    }
    for figure in node
        .children()
        .filter(|n| n.tag_name().name() == "PathFigure")
    {
        out.push_str(&format!(
            " M {} ",
            figure.attribute("StartPoint").unwrap_or("0,0")
        ));
        for segment in figure.children().filter(Node::is_element) {
            let points = segment.attribute("Points").unwrap_or("");
            match segment.tag_name().name() {
                "PolyLineSegment" => out.push_str(&format!(" L {points}")),
                "PolyBezierSegment" => out.push_str(&format!(" C {points}")),
                "PolyQuadraticBezierSegment" => out.push_str(&format!(" Q {points}")),
                "ArcSegment" => {
                    let get = |name: &str, or: &'static str| {
                        segment.attribute(name).unwrap_or(or).to_owned()
                    };
                    let flag = |on: bool| u8::from(on);
                    out.push_str(&format!(
                        " A {} {} {} {} {}",
                        get("Size", "0,0"),
                        get("RotationAngle", "0"),
                        flag(segment.attribute("IsLargeArc") == Some("true")),
                        flag(segment.attribute("SweepDirection") == Some("Clockwise")),
                        get("Point", "0,0"),
                    ));
                }
                _ => {}
            }
        }
        if figure.attribute("IsClosed") == Some("true") {
            out.push_str(" Z");
        }
    }
    out
}

// ---- Fonts ----

/// An embedded font. A part ending `.odttf` is scrambled with the GUID that names it.
fn unscramble(name: &str, mut data: Vec<u8>) -> Vec<u8> {
    if !name.to_ascii_lowercase().ends_with(".odttf") {
        return data;
    }
    let stem = name
        .rsplit('/')
        .next()
        .unwrap_or(name)
        .split('.')
        .next()
        .unwrap_or("");
    let digits: Vec<u8> = stem.bytes().filter(u8::is_ascii_hexdigit).collect();
    if digits.len() != 32 || data.len() < 32 {
        return data;
    }
    let value = |c: u8| (c as char).to_digit(16).unwrap_or(0) as u8;
    let key: Vec<u8> = digits
        .chunks(2)
        .map(|p| value(p[0]) << 4 | value(p[1]))
        .collect();
    // The key is the GUID's bytes backwards.
    for (i, byte) in data.iter_mut().take(32).enumerate() {
        *byte ^= key[15 - i % 16];
    }
    data
}

struct Outline<'a> {
    path: &'a mut PathBuilder,
    /// Font units to shape coordinates: origin, scale, and the slant of simulated italics.
    x: f32,
    y: f32,
    scale: f32,
    slant: f32,
}

impl Outline<'_> {
    fn place(&self, x: f32, y: f32) -> (f32, f32) {
        (
            self.x + (x + y * self.slant) * self.scale,
            self.y - y * self.scale,
        )
    }
}

impl ttf_parser::OutlineBuilder for Outline<'_> {
    fn move_to(&mut self, x: f32, y: f32) {
        let (x, y) = self.place(x, y);
        self.path.move_to(x, y);
    }
    fn line_to(&mut self, x: f32, y: f32) {
        let (x, y) = self.place(x, y);
        self.path.line_to(x, y);
    }
    fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
        let (a, b) = (self.place(x1, y1), self.place(x, y));
        self.path.quad_to(a.0, a.1, b.0, b.1);
    }
    fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
        let (a, b, c) = (self.place(x1, y1), self.place(x2, y2), self.place(x, y));
        self.path.cubic_to(a.0, a.1, b.0, b.1, c.0, c.1);
    }
    fn close(&mut self) {
        self.path.close();
    }
}

/// One entry of a `Glyphs` element's `Indices`, with how many characters it stands for.
struct Entry {
    /// (characters, glyphs), where a cluster starts.
    cluster: Option<(usize, usize)>,
    glyph: Option<u16>,
    advance: Option<f32>,
    offset: (f32, f32),
}

fn entries(text: &str) -> Vec<Entry> {
    text.split(';')
        .map(|entry| {
            let (cluster, rest) = match entry
                .trim()
                .strip_prefix('(')
                .and_then(|e| e.split_once(')'))
            {
                Some((inside, rest)) => {
                    let (a, b) = inside.split_once(':').unwrap_or((inside, "1"));
                    (Some((a.parse().unwrap_or(1), b.parse().unwrap_or(1))), rest)
                }
                None => (None, entry.trim()),
            };
            let mut fields = rest.split(',').map(str::trim);
            let glyph = fields.next().and_then(|f| f.parse().ok());
            let mut value = || {
                fields
                    .next()
                    .and_then(|f| f.parse::<f32>().ok())
                    .filter(|v| v.is_finite())
            };
            let advance = value();
            let offset = (value().unwrap_or(0.0), value().unwrap_or(0.0));
            Entry {
                cluster,
                glyph,
                advance,
                offset,
            }
        })
        .collect()
}

// ---- Reading a page ----

#[derive(Clone)]
struct Scope {
    transform: Transform,
    opacity: f32,
    clips: Arc<Vec<Clip>>,
}

struct Reader {
    package: Package,
    fonts: HashMap<String, Option<Arc<Vec<u8>>>>,
    pictures: HashMap<String, Option<(Arc<Pixmap>, f32, f32)>>,
}

/// Keyed resources: the XML of each, and the part it came from (references are relative to it).
type Resources = Vec<HashMap<String, (String, String)>>;

struct PageReader<'a> {
    reader: &'a mut Reader,
    part: String,
    resources: Resources,
    draws: Vec<Item>,
    /// How many visual brushes are being read, one inside another.
    nested: usize,
    runs: Vec<TextRun>,
}

/// The element given for a property, written as `<Path.Fill><SolidColorBrush/></Path.Fill>`.
fn property<'a, 'i>(node: Node<'a, 'i>, name: &str) -> Option<Node<'a, 'i>> {
    node.children()
        .find(|c| {
            c.tag_name()
                .name()
                .split_once('.')
                .is_some_and(|(_, p)| p == name)
        })?
        .children()
        .find(Node::is_element)
}

fn resource_key(value: &str) -> Option<&str> {
    value
        .strip_prefix("{StaticResource ")?
        .strip_suffix('}')
        .map(str::trim)
}

impl PageReader<'_> {
    /// Calls `read` with the element a property holds, whether inline or a shared resource.
    fn element<T>(
        &mut self,
        node: Node,
        name: &str,
        read: impl FnOnce(&mut Self, Node) -> T,
    ) -> Option<T> {
        if let Some(inline) = property(node, name) {
            return Some(read(self, inline));
        }
        let key = resource_key(node.attribute(name)?)?;
        let (xml, from) = self
            .resources
            .iter()
            .rev()
            .find_map(|r| r.get(key))?
            .clone();
        let doc = parse_xml(&xml).ok()?;
        let own = std::mem::replace(&mut self.part, from);
        let out = read(self, doc.root_element());
        self.part = own;
        Some(out)
    }

    fn transform(&mut self, node: Node, name: &str) -> Transform {
        if let Some(t) = node.attribute(name).and_then(matrix) {
            return t;
        }
        self.element(node, name, |_, e| e.attribute("Matrix").and_then(matrix))
            .flatten()
            .unwrap_or_default()
    }

    /// A geometry property: its path, fill rule and own transform applied.
    fn geometry(&mut self, node: Node, name: &str) -> Option<(Path, FillRule)> {
        if let Some(value) = node.attribute(name).filter(|v| resource_key(v).is_none()) {
            let (path, rule) = geometry(value);
            return Some((path?, rule));
        }
        self.element(node, name, |page, e| {
            let (path, rule) = geometry(&figures(e));
            let transform = page.transform(e, "Transform");
            Some((path?.transform(transform)?, rule))
        })?
    }

    fn picture(&mut self, source: &str) -> Option<(Arc<Pixmap>, f32, f32)> {
        // `{ColorConvertedBitmap image profile}` names the picture first.
        let source = match source.strip_prefix("{ColorConvertedBitmap ") {
            Some(rest) => rest.split([' ', '}']).next()?,
            None => source,
        };
        let name = resolve(&self.part, source);
        let reader = &mut *self.reader;
        if let Some(found) = reader.pictures.get(&name) {
            return found.clone();
        }
        let found = part(&mut reader.package, &name).and_then(|data| {
            let pages = crate::pictures::Pictures::image(data).ok()?;
            let size = pages.size(0)?;
            let tile = {
                let pixels = pages.pixel_size(0)?;
                let scale = pixels.0 as f32 / size.width;
                pages
                    .render_tile(
                        0,
                        Rect::new(0.0, 0.0, size.width, size.height),
                        scale,
                        pixels.0,
                        pixels.1,
                    )
                    .ok()?
            };
            let mut pixmap = Pixmap::new(tile.width, tile.height)?;
            pixmap.data_mut().copy_from_slice(&tile.pixels);
            // The picture's size in XPS units, from the resolution it states.
            Some((Arc::new(pixmap), size.width / POINTS, size.height / POINTS))
        });
        reader.pictures.insert(name, found.clone());
        found
    }

    fn stops(node: Node, opacity: f32) -> Vec<GradientStop> {
        let mut stops: Vec<(f32, Color)> = node
            .descendants()
            .filter(|n| n.tag_name().name() == "GradientStop")
            .filter_map(|s| {
                let offset = s.attribute("Offset")?.parse::<f32>().ok()?;
                let mut c = color(s.attribute("Color")?)?;
                c.set_alpha(c.alpha() * opacity);
                Some((offset, c))
            })
            .collect();
        stops.sort_by(|a, b| a.0.total_cmp(&b.0));
        stops
            .into_iter()
            .map(|(o, c)| GradientStop::new(o, c))
            .collect()
    }

    fn brush(&mut self, node: Node, inherited: f32) -> Option<Fill> {
        let opacity = inherited
            * node
                .attribute("Opacity")
                .and_then(|v| v.parse().ok())
                .unwrap_or(1.0f32);
        let spread = match node.attribute("SpreadMethod") {
            Some("Reflect") => SpreadMode::Reflect,
            Some("Repeat") => SpreadMode::Repeat,
            _ => SpreadMode::Pad,
        };
        let transform = self.transform(node, "Transform");
        let at = |name: &str| node.attribute(name).and_then(point);
        match node.tag_name().name() {
            "SolidColorBrush" => Some(Fill::Solid(color(node.attribute("Color")?)?).faded(opacity)),
            "LinearGradientBrush" => Some(Fill::Linear {
                from: at("StartPoint")?,
                to: at("EndPoint")?,
                stops: Self::stops(node, opacity),
                spread,
                transform,
            }),
            "RadialGradientBrush" => {
                let center = at("Center")?;
                let rx: f32 = node.attribute("RadiusX")?.parse().ok()?;
                let ry: f32 = node.attribute("RadiusY")?.parse().ok()?;
                if !(rx > 0.0 && ry > 0.0) {
                    return None;
                }
                // An ellipse is a circle squashed about its centre.
                let squash =
                    Transform::from_row(1.0, 0.0, 0.0, ry / rx, 0.0, center.y * (1.0 - ry / rx));
                let origin = at("GradientOrigin").unwrap_or(center);
                let origin = Point::from_xy(origin.x, center.y + (origin.y - center.y) * rx / ry);
                Some(Fill::Radial {
                    origin,
                    center,
                    radius: rx,
                    stops: Self::stops(node, opacity),
                    spread,
                    transform: squash.post_concat(transform),
                })
            }
            "VisualBrush" => {
                // A brush that draws itself would never end.
                if self.nested >= 4 {
                    return None;
                }
                let [vx, vy, vw, vh] = numbers(node.attribute("Viewbox")?)[..] else {
                    return None;
                };
                let [px, py, pw, ph] = numbers(node.attribute("Viewport")?)[..] else {
                    return None;
                };
                if !(vw > 0.0 && vh > 0.0 && pw > 0.0 && ph > 0.0) {
                    return None;
                }
                let outer = std::mem::take(&mut self.draws);
                self.nested += 1;
                let scope = Scope {
                    transform: Transform::identity(),
                    opacity: 1.0,
                    clips: Arc::default(),
                };
                let read = |page: &mut Self, visual: Node| match visual.tag_name().name() {
                    "Canvas" => {
                        page.read_resources(visual);
                        let inner = page.scope(visual, &scope);
                        page.children(visual, &inner, 0);
                        page.resources.pop();
                    }
                    "Path" => page.path(visual, &scope),
                    "Glyphs" => page.glyphs(visual, &scope),
                    _ => {}
                };
                let found = self.element(node, "Visual", read);
                self.nested -= 1;
                let items = std::mem::replace(&mut self.draws, outer);
                found?;
                Some(Fill::Visual {
                    items: Arc::new(items),
                    viewbox: [vx, vy, vw, vh],
                    viewport: [px, py, pw, ph],
                    transform,
                    tile: tiling(node),
                    opacity,
                })
            }
            "ImageBrush" => {
                let (pixels, width, height) = self.picture(node.attribute("ImageSource")?)?;
                let [vx, vy, vw, vh] = numbers(node.attribute("Viewbox")?)[..] else {
                    return None;
                };
                let [px, py, pw, ph] = numbers(node.attribute("Viewport")?)[..] else {
                    return None;
                };
                if !(vw > 0.0 && vh > 0.0 && pw > 0.0 && ph > 0.0) {
                    return None;
                }
                // Pixels to the picture's own units, its viewbox onto the viewport.
                let place = Transform::from_scale(
                    width / pixels.width() as f32,
                    height / pixels.height() as f32,
                )
                .post_translate(-vx, -vy)
                .post_scale(pw / vw, ph / vh)
                .post_translate(px, py)
                .post_concat(transform);
                let tile = tiling(node);
                let area =
                    PathBuilder::from_rect(resvg::tiny_skia::Rect::from_xywh(px, py, pw, ph)?)
                        .transform(transform)?;
                Some(Fill::Picture {
                    pixels,
                    transform: place,
                    tile,
                    area,
                    opacity,
                })
            }
            _ => None,
        }
    }

    /// A `Fill` or `Stroke` property.
    fn paint(&mut self, node: Node, name: &str, opacity: f32) -> Option<Fill> {
        if let Some(value) = node.attribute(name).filter(|v| resource_key(v).is_none()) {
            return Some(Fill::Solid(color(value)?).faded(opacity));
        }
        self.element(node, name, |page, e| page.brush(e, opacity))?
    }

    /// The scope inside an element: its transform, opacity and clip added.
    fn scope(&mut self, node: Node, outer: &Scope) -> Scope {
        let transform = self
            .transform(node, "RenderTransform")
            .post_concat(outer.transform);
        let own: f32 = node
            .attribute("Opacity")
            .and_then(|v| v.parse().ok())
            .unwrap_or(1.0);
        let mut clips = outer.clips.clone();
        if let Some((path, rule)) = self.geometry(node, "Clip") {
            Arc::make_mut(&mut clips).push(Clip {
                path,
                rule,
                transform,
            });
        }
        Scope {
            transform,
            opacity: outer.opacity * own.clamp(0.0, 1.0),
            clips,
        }
    }

    fn read_resources(&mut self, node: Node) {
        let mut found = HashMap::new();
        for holder in node
            .children()
            .filter(|c| c.tag_name().name().ends_with(".Resources"))
        {
            for dictionary in holder
                .children()
                .filter(|c| c.tag_name().name() == "ResourceDictionary")
            {
                let (xml, from) = match dictionary.attribute("Source") {
                    Some(source) => {
                        let name = resolve(&self.part, source);
                        match part(&mut self.reader.package, &name) {
                            Some(data) => (Some(decode(&data)), name),
                            None => continue,
                        }
                    }
                    None => (None, self.part.clone()),
                };
                let parsed = xml.as_deref().map(parse_xml);
                let root = match &parsed {
                    Some(Ok(doc)) => doc.root_element(),
                    Some(Err(_)) => continue,
                    None => dictionary,
                };
                let source = root.document().input_text();
                for entry in root.children().filter(Node::is_element) {
                    let key = entry.attributes().find(|a| a.name() == "Key");
                    if let Some(key) = key {
                        let namespaces: String = entry
                            .namespaces()
                            .map(|n| match n.name() {
                                Some(prefix) if prefix != "xml" => {
                                    format!(" xmlns:{prefix}=\"{}\"", n.uri())
                                }
                                _ => String::new(),
                            })
                            .collect();
                        let mut text = source[entry.range()].to_owned();
                        // The cut-out element needs the prefixes its document declared.
                        let end = text.find([' ', '/', '>']).unwrap_or(text.len());
                        let missing: String = namespaces
                            .split_inclusive('"')
                            .collect::<Vec<_>>()
                            .chunks(2)
                            .map(<[&str]>::concat)
                            .filter(|n| {
                                !text.contains(n.trim_start().split('=').next().unwrap_or(""))
                            })
                            .collect();
                        text.insert_str(end, &missing);
                        found.insert(key.value().to_owned(), (text, from.clone()));
                    }
                }
            }
        }
        self.resources.push(found);
    }

    fn children(&mut self, node: Node, scope: &Scope, depth: usize) {
        if depth > DEEPEST {
            return;
        }
        for child in node.children().filter(Node::is_element) {
            match child.tag_name().name() {
                "Canvas" => {
                    self.read_resources(child);
                    let inner = self.scope(child, scope);
                    self.masked(child, inner.transform, |page| {
                        page.children(child, &inner, depth + 1)
                    });
                    self.resources.pop();
                }
                "Path" | "Glyphs" => {
                    let transform = self
                        .transform(child, "RenderTransform")
                        .post_concat(scope.transform);
                    self.masked(child, transform, |page| {
                        if child.tag_name().name() == "Path" {
                            page.path(child, scope);
                        } else {
                            page.glyphs(child, scope);
                        }
                    });
                }
                // Markup compatibility: take what a plain reader is meant to.
                "AlternateContent" => {
                    if let Some(fallback) =
                        child.children().find(|c| c.tag_name().name() == "Fallback")
                    {
                        self.children(fallback, scope, depth + 1);
                    }
                }
                _ => {}
            }
        }
    }

    fn draw(&mut self, draw: Draw) {
        self.draws.push(Item::Draw(Box::new(draw)));
    }

    /// Runs `read`, then puts what it drew behind the element's opacity mask, if it has one.
    fn masked(&mut self, node: Node, transform: Transform, read: impl FnOnce(&mut Self)) {
        let first = self.draws.len();
        read(self);
        let name = "OpacityMask";
        let given = node.attribute(name).is_some() || property(node, name).is_some();
        if given
            && self.draws.len() > first
            && let Some(mask) = self.paint(node, name, 1.0)
        {
            let items = self.draws.split_off(first);
            self.draws.push(Item::Masked {
                mask: Box::new(mask),
                transform,
                items,
            });
        }
    }

    fn path(&mut self, node: Node, outer: &Scope) {
        let scope = self.scope(node, outer);
        let Some((path, rule)) = self.geometry(node, "Data") else {
            return;
        };
        if let Some(fill) = self.paint(node, "Fill", scope.opacity) {
            self.draw(Draw {
                path: path.clone(),
                rule,
                fill,
                stroke: None,
                transform: scope.transform,
                clips: scope.clips.clone(),
            });
        }
        if let Some(fill) = self.paint(node, "Stroke", scope.opacity) {
            let number = |name: &str, or: f32| {
                node.attribute(name)
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(or)
            };
            let width: f32 = number("StrokeThickness", 1.0);
            let mut dashes: Vec<f32> = numbers(node.attribute("StrokeDashArray").unwrap_or(""))
                .iter()
                .map(|d| d * width)
                .collect();
            if dashes.len() % 2 == 1 {
                dashes.extend_from_within(..);
            }
            let stroke = Stroke {
                width,
                miter_limit: number("StrokeMiterLimit", 10.0),
                line_cap: match node.attribute("StrokeStartLineCap") {
                    Some("Round") => LineCap::Round,
                    Some("Square") => LineCap::Square,
                    _ => LineCap::Butt,
                },
                line_join: match node.attribute("StrokeLineJoin") {
                    Some("Round") => LineJoin::Round,
                    Some("Bevel") => LineJoin::Bevel,
                    _ => LineJoin::Miter,
                },
                dash: StrokeDash::new(dashes, number("StrokeDashOffset", 0.0) * width),
            };
            self.draw(Draw {
                path,
                rule,
                fill,
                stroke: Some(stroke),
                transform: scope.transform,
                clips: scope.clips,
            });
        }
    }

    fn glyphs(&mut self, node: Node, outer: &Scope) {
        let scope = self.scope(node, outer);
        let number = |name: &str| {
            node.attribute(name)
                .and_then(|v| v.parse::<f32>().ok())
                .filter(|v| v.is_finite())
        };
        let (Some(uri), Some(em)) = (node.attribute("FontUri"), number("FontRenderingEmSize"))
        else {
            return;
        };
        let (face_index, uri) = match uri.split_once('#') {
            Some((uri, face)) => (face.parse().unwrap_or(0), uri),
            None => (0, uri),
        };
        let name = resolve(&self.part, uri);
        let reader = &mut *self.reader;
        let font = reader
            .fonts
            .entry(name.clone())
            .or_insert_with(|| {
                part(&mut reader.package, &name).map(|d| Arc::new(unscramble(&name, d)))
            })
            .clone();
        let Some(data) = font else { return };
        let Ok(face) = ttf_parser::Face::parse(&data, face_index) else {
            return;
        };
        let units = f32::from(face.units_per_em());
        let text = node.attribute("UnicodeString").unwrap_or("");
        let text = text.strip_prefix("{}").unwrap_or(text);
        let list = entries(node.attribute("Indices").unwrap_or(""));
        let simulations = node.attribute("StyleSimulations").unwrap_or("");
        let slant = if simulations.contains("Italic") {
            0.36
        } else {
            0.0
        };
        let backwards = number("BidiLevel").is_some_and(|v| v as u32 % 2 == 1);
        let (Some(mut x), Some(y)) = (number("OriginX"), number("OriginY")) else {
            return;
        };

        let mut path = PathBuilder::new();
        // Each character with the span its glyph covers.
        let mut spans: Vec<(char, f32, f32)> = Vec::new();
        let mut chars = text.chars();
        let mut index = 0;
        loop {
            // A cluster maps some characters (counted as UTF-16 units) to some glyphs.
            let (units_wanted, glyph_count) =
                list.get(index).and_then(|e| e.cluster).unwrap_or((1, 1));
            let mut cluster = Vec::new();
            let mut taken = 0;
            while !text.is_empty() && taken < units_wanted {
                let Some(c) = chars.next() else { break };
                taken += c.len_utf16();
                cluster.push(c);
            }
            if cluster.is_empty() && index >= list.len() {
                break;
            }
            let before = x;
            for n in 0..glyph_count.clamp(1, 256) {
                let entry = list.get(index);
                index += 1;
                let glyph = entry
                    .and_then(|e| e.glyph)
                    .map(ttf_parser::GlyphId)
                    .or_else(|| face.glyph_index(*cluster.get(n).or(cluster.first())?));
                let glyph = glyph.unwrap_or(ttf_parser::GlyphId(0));
                let natural = f32::from(face.glyph_hor_advance(glyph).unwrap_or(0)) / units * em;
                let advance = entry
                    .and_then(|e| e.advance)
                    .map_or(natural, |a| a / 100.0 * em);
                let (u, v) = entry.map_or((0.0, 0.0), |e| e.offset);
                let shift = u / 100.0 * em;
                let origin = if backwards {
                    x - natural - shift
                } else {
                    x + shift
                };
                let mut outline = Outline {
                    path: &mut path,
                    x: origin,
                    y: y - v / 100.0 * em,
                    scale: em / units,
                    slant,
                };
                face.outline_glyph(glyph, &mut outline);
                x += if backwards { -advance } else { advance };
            }
            let step = (x - before) / cluster.len().max(1) as f32;
            for (n, c) in cluster.into_iter().enumerate() {
                let a = before + step * n as f32;
                spans.push((c, a.min(a + step), a.max(a + step)));
            }
        }

        // The text, placed on the page in points.
        let shown: String = spans.iter().map(|s| s.0).collect();
        if !shown.trim().is_empty() {
            let ascent = f32::from(face.ascender()) / units * em;
            let descent = f32::from(face.descender()) / units * em;
            let page = scope.transform.post_scale(POINTS, POINTS);
            let place = |a: f32, b: f32| {
                let mut corners = [
                    Point::from_xy(a, y - ascent),
                    Point::from_xy(b, y - ascent),
                    Point::from_xy(a, y - descent),
                    Point::from_xy(b, y - descent),
                ];
                page.map_points(&mut corners);
                corners.iter().fold(
                    Rect::new(
                        f32::INFINITY,
                        f32::INFINITY,
                        f32::NEG_INFINITY,
                        f32::NEG_INFINITY,
                    ),
                    |r, p| {
                        Rect::new(
                            r.min.x.min(p.x),
                            r.min.y.min(p.y),
                            r.max.x.max(p.x),
                            r.max.y.max(p.y),
                        )
                    },
                )
            };
            let chars: Vec<Rect> = spans.iter().map(|s| place(s.1, s.2)).collect();
            let whole = chars.iter().skip(1).fold(chars[0], |a, b| {
                Rect::new(
                    a.min.x.min(b.min.x),
                    a.min.y.min(b.min.y),
                    a.max.x.max(b.max.x),
                    a.max.y.max(b.max.y),
                )
            });
            let mut run = TextRun::new(shown, whole);
            run.chars = chars;
            self.runs.push(run);
        }

        let Some(path) = path.finish() else { return };
        let Some(fill) = self.paint(node, "Fill", scope.opacity) else {
            return;
        };
        // Simulated bold: the outline drawn a little fatter.
        if simulations.contains("Bold") {
            self.draw(Draw {
                path: path.clone(),
                rule: FillRule::Winding,
                fill: fill.clone(),
                stroke: Some(Stroke {
                    width: em * 0.02,
                    ..Stroke::default()
                }),
                transform: scope.transform,
                clips: scope.clips.clone(),
            });
        }
        self.draw(Draw {
            path,
            rule: FillRule::Winding,
            fill,
            stroke: None,
            transform: scope.transform,
            clips: scope.clips,
        });
    }
}

impl Xps {
    pub fn new(bytes: Vec<u8>) -> Result<Xps, Error> {
        let mut reader = Reader {
            package: Package::new(bytes)?,
            fonts: HashMap::new(),
            pictures: HashMap::new(),
        };
        let package = &mut reader.package;
        // The root relationship names the sequence of documents.
        let data = part(package, "_rels/.rels").ok_or_else(|| other("this is not an XPS file"))?;
        let text = decode(&data);
        let sequence = parse_xml(&text)?
            .descendants()
            .find(|n| {
                n.attribute("Type")
                    .is_some_and(|t| t.ends_with("/fixedrepresentation"))
            })
            .and_then(|n| Some(resolve("", n.attribute("Target")?)))
            .ok_or_else(|| other("this is not an XPS file"))?;
        let mut names = Vec::new();
        for (_, document) in references(package, &sequence, "DocumentReference")? {
            names.extend(
                references(package, &document, "PageContent")?
                    .into_iter()
                    .map(|(_, p)| p),
            );
        }
        let mut pages = Vec::new();
        for name in names {
            let data = part(&mut reader.package, &name)
                .ok_or_else(|| other(format!("a page is missing: {name}")))?;
            let text = decode(&data);
            let doc = parse_xml(&text)?;
            let root = doc.root_element();
            let side = |a: &str| {
                root.attribute(a)
                    .and_then(|v| v.parse::<f32>().ok())
                    .filter(|v| *v > 0.0)
            };
            let (Some(width), Some(height)) = (side("Width"), side("Height")) else {
                return Err(other("a page has no size"));
            };
            let mut page = PageReader {
                reader: &mut reader,
                part: name,
                resources: Vec::new(),
                draws: Vec::new(),
                runs: Vec::new(),
                nested: 0,
            };
            page.read_resources(root);
            let scope = Scope {
                transform: Transform::identity(),
                opacity: 1.0,
                clips: Arc::default(),
            };
            page.children(root, &scope, 0);
            pages.push(Page {
                size: Size::new(width * POINTS, height * POINTS),
                draws: page.draws,
                runs: page.runs,
            });
        }
        if let Some(error) = reader.package.failure() {
            return Err(error);
        }
        if pages.is_empty() {
            return Err(Error::Empty);
        }
        Ok(Xps { pages })
    }
}

/// The picture of one tile and its mirrored neighbours, so that repeating it mirrors.
fn mirrored(tile: &Pixmap, across: bool, down: bool) -> Option<Pixmap> {
    let (w, h) = (tile.width(), tile.height());
    let mut out = Pixmap::new(w * if across { 2 } else { 1 }, h * if down { 2 } else { 1 })?;
    for row in 0..out.height() / h {
        for column in 0..out.width() / w {
            let flip_x = if column == 1 {
                (-1.0, 2.0 * w as f32)
            } else {
                (1.0, 0.0)
            };
            let flip_y = if row == 1 {
                (-1.0, 2.0 * h as f32)
            } else {
                (1.0, 0.0)
            };
            let place = Transform::from_row(flip_x.0, 0.0, 0.0, flip_y.0, flip_x.1, flip_y.1);
            out.draw_pixmap(0, 0, tile.as_ref(), &PixmapPaint::default(), place, None);
        }
    }
    Some(out)
}

/// Pixels as a brush on a shape: `place` takes them to the shape's coordinates; `area` is
/// the one tile's rectangle there.
#[allow(clippy::too_many_arguments)]
fn draw_picture(
    canvas: &mut Pixmap,
    item: &Draw,
    transform: Transform,
    mask: Option<&Mask>,
    pixels: &Pixmap,
    place: Transform,
    tile: Tiling,
    area: &Path,
    opacity: f32,
) {
    // A picture shows where both the shape and (untiled) its viewport are.
    let (w, h) = (canvas.width(), canvas.height());
    let mut shape = match mask {
        Some(mask) => mask.clone(),
        None => {
            let Some(mut full) = Mask::new(w, h) else {
                return;
            };
            full.data_mut().fill(255);
            full
        }
    };
    match &item.stroke {
        Some(stroke) => {
            let Some(outline) = item.path.stroke(stroke, 1.0) else {
                return;
            };
            shape.intersect_path(&outline, FillRule::Winding, true, transform);
        }
        None => shape.intersect_path(&item.path, item.rule, true, transform),
    }
    if tile == Tiling::Once {
        shape.intersect_path(area, FillRule::Winding, true, transform);
        let paint = PixmapPaint {
            opacity,
            quality: FilterQuality::Bilinear,
            ..PixmapPaint::default()
        };
        canvas.draw_pixmap(
            0,
            0,
            pixels.as_ref(),
            &paint,
            place.post_concat(transform),
            Some(&shape),
        );
        return;
    }
    let flipped = match tile {
        Tiling::Mirror { across, down } => mirrored(pixels, across, down),
        _ => None,
    };
    let pixels = flipped.as_ref().unwrap_or(pixels);
    let paint = Paint {
        shader: Pattern::new(
            pixels.as_ref(),
            SpreadMode::Repeat,
            FilterQuality::Bilinear,
            opacity,
            place,
        ),
        anti_alias: true,
        ..Paint::default()
    };
    // The whole canvas, in the shape's coordinates, cut to the shape by the mask.
    let (Some(inverse), Some(whole)) = (
        transform.invert(),
        resvg::tiny_skia::Rect::from_xywh(0.0, 0.0, w as f32, h as f32),
    ) else {
        return;
    };
    if let Some(whole) = PathBuilder::from_rect(whole).transform(inverse) {
        canvas.fill_path(&whole, &paint, FillRule::Winding, transform, Some(&shape));
    }
}

fn draw(canvas: &mut Pixmap, item: &Draw, view: Transform, mask: Option<&Mask>) {
    let transform = item.transform.post_concat(view);
    match &item.fill {
        Fill::Picture {
            pixels,
            transform: place,
            tile,
            area,
            opacity,
        } => {
            draw_picture(
                canvas, item, transform, mask, pixels, *place, *tile, area, *opacity,
            );
            return;
        }
        Fill::Visual {
            items,
            viewbox: [vx, vy, vw, vh],
            viewport: [px, py, pw, ph],
            transform: brush,
            tile,
            opacity,
        } => {
            // One tile is drawn at the size it will show, then used as a picture.
            let on_screen = brush.post_concat(transform);
            let length = |x: f32, y: f32| x.hypot(y);
            let wide = (pw * length(on_screen.sx, on_screen.ky))
                .ceil()
                .clamp(1.0, 2048.0);
            let tall = (ph * length(on_screen.kx, on_screen.sy))
                .ceil()
                .clamp(1.0, 2048.0);
            let Some(mut one) = Pixmap::new(wide as u32, tall as u32) else {
                return;
            };
            let into = Transform::from_translate(-vx, -vy).post_scale(wide / vw, tall / vh);
            draw_items(&mut one, items, into);
            let place = Transform::from_scale(pw / wide, ph / tall)
                .post_translate(*px, *py)
                .post_concat(*brush);
            let area = resvg::tiny_skia::Rect::from_xywh(*px, *py, *pw, *ph)
                .and_then(|r| PathBuilder::from_rect(r).transform(*brush));
            if let Some(area) = area {
                draw_picture(
                    canvas, item, transform, mask, &one, place, *tile, &area, *opacity,
                );
            }
            return;
        }
        _ => {}
    }
    let shader = match &item.fill {
        Fill::Solid(color) => Some(Shader::SolidColor(*color)),
        Fill::Linear {
            from,
            to,
            stops,
            spread,
            transform,
        } => LinearGradient::new(*from, *to, stops.clone(), *spread, *transform),
        Fill::Radial {
            origin,
            center,
            radius,
            stops,
            spread,
            transform,
        } => RadialGradient::new(
            *origin,
            *center,
            *radius,
            stops.clone(),
            *spread,
            *transform,
        ),
        Fill::Picture { .. } | Fill::Visual { .. } => None,
    };
    let Some(shader) = shader else { return };
    let paint = Paint {
        shader,
        anti_alias: true,
        ..Paint::default()
    };
    match &item.stroke {
        Some(stroke) => canvas.stroke_path(&item.path, &paint, stroke, transform, mask),
        None => canvas.fill_path(&item.path, &paint, item.rule, transform, mask),
    }
}

/// The clip mask last made: neighbouring things share their clips, so it is usually the next
/// one too.
type LastClip = Option<(*const Vec<Clip>, Mask)>;

fn draw_items(canvas: &mut Pixmap, items: &[Item], view: Transform) {
    let (width, height) = (canvas.width(), canvas.height());
    let mut last: LastClip = None;
    for item in items {
        match item {
            Item::Draw(item) => {
                let mask = if item.clips.is_empty() {
                    None
                } else {
                    let key = Arc::as_ptr(&item.clips);
                    if last.as_ref().is_none_or(|(k, _)| *k != key) {
                        let Some(mut mask) = Mask::new(width, height) else {
                            return;
                        };
                        for (n, clip) in item.clips.iter().enumerate() {
                            let transform = clip.transform.post_concat(view);
                            if n == 0 {
                                mask.fill_path(&clip.path, clip.rule, true, transform);
                            } else {
                                mask.intersect_path(&clip.path, clip.rule, true, transform);
                            }
                        }
                        last = Some((key, mask));
                    }
                    last.as_ref().map(|(_, m)| m)
                };
                draw(canvas, item, view, mask);
            }
            Item::Masked {
                mask,
                transform,
                items,
            } => {
                let (Some(mut layer), Some(mut cover)) =
                    (Pixmap::new(width, height), Pixmap::new(width, height))
                else {
                    return;
                };
                draw_items(&mut layer, items, view);
                // The mask brush over everything, in the element's coordinates.
                let placed = transform.post_concat(view);
                let whole =
                    resvg::tiny_skia::Rect::from_xywh(0.0, 0.0, width as f32, height as f32)
                        .and_then(|r| PathBuilder::from_rect(r).transform(placed.invert()?));
                if let Some(path) = whole {
                    let brush = Draw {
                        path,
                        rule: FillRule::Winding,
                        fill: (**mask).clone(),
                        stroke: None,
                        transform: *transform,
                        clips: Arc::default(),
                    };
                    draw(&mut cover, &brush, view, None);
                }
                // Premultiplied pixels: fading scales every channel.
                for (p, m) in layer
                    .data_mut()
                    .as_chunks_mut::<4>()
                    .0
                    .iter_mut()
                    .zip(cover.data().as_chunks::<4>().0)
                {
                    let alpha = u16::from(m[3]);
                    for channel in p {
                        *channel = ((u16::from(*channel) * alpha + 127) / 255) as u8;
                    }
                }
                canvas.draw_pixmap(
                    0,
                    0,
                    layer.as_ref(),
                    &PixmapPaint::default(),
                    Transform::identity(),
                    None,
                );
            }
        }
    }
}

impl Tiles for Xps {
    fn count(&self) -> usize {
        self.pages.len()
    }

    fn size(&self, page: usize) -> Option<Size> {
        self.pages.get(page).map(|p| p.size)
    }

    fn render_tile(
        &self,
        page: usize,
        region: Rect,
        scale: f32,
        width: u32,
        height: u32,
    ) -> Result<Image, Error> {
        let page = self.pages.get(page).ok_or_else(|| other("no such page"))?;
        let mut canvas =
            Pixmap::new(width, height).ok_or_else(|| other("the tile is empty or too large"))?;
        canvas.fill(Color::WHITE);
        let k = scale * POINTS;
        let view =
            Transform::from_row(k, 0.0, 0.0, k, -region.min.x * scale, -region.min.y * scale);
        draw_items(&mut canvas, &page.draws, view);
        Ok(Image::new(width, height, Arc::from(canvas.take())))
    }

    fn runs(&self, page: usize) -> Option<PageText> {
        let page = self.pages.get(page)?;
        (!page.runs.is_empty()).then(|| PageText {
            runs: page.runs.clone(),
        })
    }
}

crate::source::page_source!(Xps);
