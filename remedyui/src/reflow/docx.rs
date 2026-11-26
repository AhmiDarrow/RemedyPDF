//! Reader for Word documents (.docx).

use super::{Block, Content, Inline, Justify, Paragraph, TEXT_SIZE};
use crate::pdf::Error;
use crate::zipped::Package;
use roxmltree::Node;
use std::collections::HashMap;
use std::sync::Arc;

/// Word's usual body size; sizes are shown in proportion to it.
const WORD_BODY: f32 = 11.0;
const DEEPEST: usize = 60;

fn other(e: impl std::fmt::Display) -> Error {
    Error::Other(e.to_string())
}

fn child<'a, 'i>(node: Node<'a, 'i>, name: &str) -> Option<Node<'a, 'i>> {
    node.children().find(|c| c.tag_name().name() == name)
}

/// The attribute `name`, whatever its namespace prefix.
fn value<'a>(node: Node<'a, '_>, name: &str) -> Option<&'a str> {
    node.attributes()
        .find(|a| a.name() == name)
        .map(|a| a.value())
}

/// A switch such as `<w:b/>`: on unless it says otherwise.
fn switch(properties: Node, name: &str) -> Option<bool> {
    child(properties, name).map(|n| !matches!(value(n, "val"), Some("0" | "false" | "none")))
}

/// How a run or paragraph looks; unset parts are inherited.
#[derive(Clone, Default)]
struct Look {
    bold: Option<bool>,
    italic: Option<bool>,
    underline: Option<bool>,
    strike: Option<bool>,
    mono: Option<bool>,
    color: Option<[u8; 3]>,
    size: Option<f32>,
    raised: Option<bool>,
    align: Option<Justify>,
    indent: Option<f32>,
    before: Option<f32>,
    after: Option<f32>,
    list: Option<(String, usize)>,
    heading: bool,
}

impl Look {
    fn over(mut self, base: &Look) -> Look {
        self.bold = self.bold.or(base.bold);
        self.italic = self.italic.or(base.italic);
        self.underline = self.underline.or(base.underline);
        self.strike = self.strike.or(base.strike);
        self.mono = self.mono.or(base.mono);
        self.color = self.color.or(base.color);
        self.size = self.size.or(base.size);
        self.raised = self.raised.or(base.raised);
        self.align = self.align.or(base.align);
        self.indent = self.indent.or(base.indent);
        self.before = self.before.or(base.before);
        self.after = self.after.or(base.after);
        self.list = self.list.or_else(|| base.list.clone());
        self.heading |= base.heading;
        self
    }

    fn run(&mut self, properties: Node) {
        self.bold = switch(properties, "b").or(self.bold);
        self.italic = switch(properties, "i").or(self.italic);
        self.underline = switch(properties, "u").or(self.underline);
        self.strike = switch(properties, "strike").or(self.strike);
        if let Some(size) =
            child(properties, "sz").and_then(|n| value(n, "val")?.parse::<f32>().ok())
        {
            // Half points.
            self.size = Some(size / 2.0);
        }
        if let Some(hex) = child(properties, "color").and_then(|n| value(n, "val"))
            && hex.len() == 6
            && hex.is_ascii()
        {
            let channel = |i: usize| u8::from_str_radix(&hex[i..i + 2], 16).ok();
            self.color = match (channel(0), channel(2), channel(4)) {
                (Some(r), Some(g), Some(b)) => Some([r, g, b]),
                _ => self.color,
            };
        }
        if let Some(font) = child(properties, "rFonts").and_then(|n| value(n, "ascii")) {
            let font = font.to_ascii_lowercase();
            self.mono = Some(
                ["mono", "courier", "consolas"]
                    .iter()
                    .any(|m| font.contains(m)),
            );
        }
        if let Some(position) = child(properties, "vertAlign").and_then(|n| value(n, "val")) {
            self.raised = Some(position == "superscript" || position == "subscript");
        }
    }

    fn paragraph(&mut self, properties: Node) {
        // Twentieths of a point.
        let twips =
            |node: Node, name: &str| value(node, name)?.parse::<f32>().ok().map(|v| v / 20.0);
        match child(properties, "jc").and_then(|n| value(n, "val")) {
            Some("center") => self.align = Some(Justify::Center),
            Some("right" | "end") => self.align = Some(Justify::End),
            Some("both" | "distribute") => self.align = Some(Justify::Both),
            Some(_) => self.align = Some(Justify::Start),
            None => {}
        }
        if let Some(indent) = child(properties, "ind") {
            self.indent = twips(indent, "left")
                .or_else(|| twips(indent, "start"))
                .or(self.indent);
        }
        if let Some(spacing) = child(properties, "spacing") {
            self.before = twips(spacing, "before").or(self.before);
            self.after = twips(spacing, "after").or(self.after);
        }
        if let Some(numbering) = child(properties, "numPr") {
            let id = child(numbering, "numId").and_then(|n| value(n, "val"));
            let level = child(numbering, "ilvl")
                .and_then(|n| value(n, "val")?.parse().ok())
                .unwrap_or(0);
            self.list = id.map(|id| (id.to_owned(), level));
        }
        if child(properties, "outlineLvl").is_some() {
            self.heading = true;
        }
    }
}

struct Reader {
    package: Package,
    styles: HashMap<String, Look>,
    base: Look,
    /// Relationship id to a path in the package.
    links: HashMap<String, String>,
    /// (list, level) to (format, text pattern, first number).
    levels: HashMap<(String, usize), (String, String, u32)>,
    counts: HashMap<String, Vec<u32>>,
    blocks: Vec<Block>,
    /// Footnotes and endnotes by (part, id), and those referred to, in order.
    notes: HashMap<(&'static str, String), String>,
    cited: Vec<(&'static str, String)>,
}

fn with_xml<T>(source: &[u8], read: impl FnOnce(Node) -> T) -> Result<T, Error> {
    let text = super::markup::decode(source);
    let doc = super::markup::parse_xml(&text)?;
    Ok(read(doc.root_element()))
}

fn read_styles(root: Node) -> (HashMap<String, Look>, Look) {
    let mut base = Look::default();
    if let Some(defaults) = child(root, "docDefaults") {
        if let Some(p) = child(defaults, "rPrDefault").and_then(|d| child(d, "rPr")) {
            base.run(p);
        }
        if let Some(p) = child(defaults, "pPrDefault").and_then(|d| child(d, "pPr")) {
            base.paragraph(p);
        }
    }
    let mut own = HashMap::new();
    for style in root.children().filter(|n| n.tag_name().name() == "style") {
        let Some(id) = value(style, "styleId") else {
            continue;
        };
        let mut look = Look::default();
        if let Some(p) = child(style, "pPr") {
            look.paragraph(p);
        }
        if let Some(p) = child(style, "rPr") {
            look.run(p);
        }
        let name = child(style, "name")
            .and_then(|n| value(n, "val"))
            .unwrap_or("")
            .to_ascii_lowercase();
        look.heading |= name.starts_with("heading") || name == "title";
        let parent = child(style, "basedOn")
            .and_then(|n| value(n, "val"))
            .map(str::to_owned);
        let default =
            value(style, "default") == Some("1") && value(style, "type") == Some("paragraph");
        own.insert(id.to_owned(), (look, parent));
        if default && let Some((look, _)) = own.get(id) {
            base = look.clone().over(&base);
        }
    }
    let styles = own
        .keys()
        .map(|id| {
            let mut look = Look::default();
            let mut next = Some(id.clone());
            for _ in 0..DEEPEST {
                let Some((own, parent)) = next.and_then(|id| own.get(&id).cloned()) else {
                    break;
                };
                look = look.over(&own);
                next = parent;
            }
            (id.clone(), look)
        })
        .collect();
    (styles, base)
}

fn read_levels(root: Node) -> HashMap<(String, usize), (String, String, u32)> {
    let mut shapes = HashMap::new();
    for shape in root
        .children()
        .filter(|n| n.tag_name().name() == "abstractNum")
    {
        let Some(id) = value(shape, "abstractNumId") else {
            continue;
        };
        let levels: Vec<_> = shape
            .children()
            .filter(|n| n.tag_name().name() == "lvl")
            .filter_map(|level| {
                let n: usize = value(level, "ilvl")?.parse().ok()?;
                let get = |name: &str| child(level, name).and_then(|c| value(c, "val"));
                let start = get("start").and_then(|s| s.parse().ok()).unwrap_or(1u32);
                let format = get("numFmt").unwrap_or("decimal").to_owned();
                Some((n, format, get("lvlText").unwrap_or("").to_owned(), start))
            })
            .collect();
        shapes.insert(id.to_owned(), levels);
    }
    let mut out = HashMap::new();
    for list in root.children().filter(|n| n.tag_name().name() == "num") {
        let (Some(id), Some(shape)) = (
            value(list, "numId"),
            child(list, "abstractNumId").and_then(|n| value(n, "val")),
        ) else {
            continue;
        };
        for (level, format, text, start) in shapes.get(shape).into_iter().flatten() {
            out.insert(
                (id.to_owned(), *level),
                (format.clone(), text.clone(), *start),
            );
        }
    }
    out
}

fn numeral(format: &str, mut n: u32) -> String {
    match format {
        "lowerLetter" | "upperLetter" => {
            let letter = char::from(b'a' + ((n.max(1) - 1) % 26) as u8);
            let text = letter
                .to_string()
                .repeat(((n.max(1) - 1) / 26 + 1).min(4) as usize);
            if format == "upperLetter" {
                text.to_uppercase()
            } else {
                text
            }
        }
        "lowerRoman" | "upperRoman" if n < 4000 => {
            let mut text = String::new();
            for (value, digits) in [
                (1000, "m"),
                (900, "cm"),
                (500, "d"),
                (400, "cd"),
                (100, "c"),
                (90, "xc"),
                (50, "l"),
                (40, "xl"),
                (10, "x"),
                (9, "ix"),
                (5, "v"),
                (4, "iv"),
                (1, "i"),
            ] {
                while n >= value {
                    text.push_str(digits);
                    n -= value;
                }
            }
            if format == "upperRoman" {
                text.to_uppercase()
            } else {
                text
            }
        }
        _ => n.to_string(),
    }
}

impl Reader {
    fn marker(&mut self, list: &str, level: usize) -> Option<String> {
        let level = level.min(8);
        let (format, pattern, _) = self.levels.get(&(list.to_owned(), level))?.clone();
        let starts: Vec<u32> = (0..9)
            .map(|l| self.levels.get(&(list.to_owned(), l)).map_or(1, |x| x.2))
            .collect();
        // A count of 0 means the level has not started.
        let counts = self
            .counts
            .entry(list.to_owned())
            .or_insert_with(|| vec![0; 9]);
        counts[level] = if counts[level] == 0 {
            starts[level].max(1)
        } else {
            counts[level].saturating_add(1)
        };
        counts[level + 1..].fill(0);
        let counts = counts.clone();
        match format.as_str() {
            "bullet" => Some("\u{2022}".into()),
            "none" => None,
            _ => {
                let mut text = pattern;
                for l in 0..=level {
                    let own = self
                        .levels
                        .get(&(list.to_owned(), l))
                        .map_or("decimal", |x| x.0.as_str());
                    let n = if counts[l] == 0 { starts[l] } else { counts[l] };
                    text = text.replace(&format!("%{}", l + 1), &numeral(own, n));
                }
                Some(text)
            }
        }
    }

    fn body(&mut self, node: Node, depth: usize) {
        if depth > DEEPEST {
            return;
        }
        for item in node.children().filter(Node::is_element) {
            match item.tag_name().name() {
                "p" => self.paragraph(item),
                "tbl" => self.table(item, depth),
                "sectPr" => {}
                // Content controls and tracked insertions hold ordinary content.
                _ => self.body(item, depth + 1),
            }
        }
    }

    fn table(&mut self, table: Node, depth: usize) {
        let mut rows = Vec::new();
        for row in table.children().filter(|n| n.tag_name().name() == "tr") {
            let mut cells = Vec::new();
            for cell in row.children().filter(|n| n.tag_name().name() == "tc") {
                let outer = std::mem::take(&mut self.blocks);
                self.body(cell, depth + 1);
                cells.push(std::mem::replace(&mut self.blocks, outer));
            }
            rows.push(cells);
        }
        self.blocks.push(Block::Table {
            rows,
            borders: true,
        });
    }

    fn paragraph(&mut self, node: Node) {
        let properties = child(node, "pPr");
        let mut look = Look::default();
        if let Some(p) = properties {
            look.paragraph(p);
        }
        let style = properties
            .and_then(|p| child(p, "pStyle"))
            .and_then(|n| value(n, "val"));
        if let Some(style) = style.and_then(|s| self.styles.get(s)) {
            look = look.over(style);
        }
        let look = look.over(&self.base);
        if properties.is_some_and(|p| switch(p, "pageBreakBefore") == Some(true)) {
            self.blocks.push(Block::PageBreak);
        }
        let marker = look
            .list
            .as_ref()
            .and_then(|(list, level)| self.marker(list, *level));
        let list_indent = look
            .list
            .as_ref()
            .map_or(0.0, |(_, level)| (*level as f32 + 1.0) * 18.0);
        let size = look.size.unwrap_or(WORD_BODY) / WORD_BODY * TEXT_SIZE;
        let blank = Paragraph {
            size,
            align: look.align.unwrap_or_default(),
            indent: look.indent.unwrap_or(list_indent).clamp(0.0, 150.0),
            before: look.before.unwrap_or(0.0).clamp(0.0, 72.0),
            after: look.after.unwrap_or(4.0).clamp(0.0, 72.0),
            marker,
            keep_with_next: look.heading,
            ..Paragraph::default()
        };
        let mut open = blank.clone();
        let mut wrote = false;
        self.runs(node, &look, size, &mut open, &blank, &mut wrote, 0);
        if !open.inlines.is_empty() {
            self.blocks.push(Block::Text(open));
        } else if !wrote {
            // An empty paragraph is a blank line.
            let mut empty = blank;
            empty.inlines = vec![Inline {
                text: " ".into(),
                ..Inline::default()
            }];
            self.blocks.push(Block::Text(empty));
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn runs(
        &mut self,
        node: Node,
        look: &Look,
        size: f32,
        open: &mut Paragraph,
        blank: &Paragraph,
        wrote: &mut bool,
        depth: usize,
    ) {
        for item in node.children().filter(Node::is_element) {
            match item.tag_name().name() {
                "pPr" | "del" | "moveFrom" | "instrText" => {}
                "r" => {
                    let mut own = Look::default();
                    if let Some(properties) = child(item, "rPr") {
                        own.run(properties);
                        let style = child(properties, "rStyle").and_then(|n| value(n, "val"));
                        if let Some(style) = style.and_then(|s| self.styles.get(s)) {
                            own = own.over(style);
                        }
                    }
                    let own = own.over(look);
                    let raised = own.raised == Some(true);
                    let scale = own.size.map_or(1.0, |s| s / WORD_BODY * TEXT_SIZE / size);
                    let style = Inline {
                        text: String::new(),
                        bold: own.bold.unwrap_or(false) || own.heading,
                        italic: own.italic.unwrap_or(false),
                        mono: own.mono.unwrap_or(false),
                        underline: own.underline.unwrap_or(false),
                        strike: own.strike.unwrap_or(false),
                        scale: if raised { scale * 0.7 } else { scale },
                        color: own.color,
                    };
                    for part in item.children().filter(Node::is_element) {
                        let text = match part.tag_name().name() {
                            "t" => part.text().unwrap_or("").to_owned(),
                            "tab" => "    ".into(),
                            "noBreakHyphen" => "\u{2011}".into(),
                            "br" if value(part, "type") == Some("page") => {
                                if !open.inlines.is_empty() {
                                    self.blocks
                                        .push(Block::Text(std::mem::replace(open, blank.clone())));
                                    open.marker = None;
                                }
                                self.blocks.push(Block::PageBreak);
                                *wrote = true;
                                continue;
                            }
                            "br" | "cr" => "\n".into(),
                            kind @ ("footnoteReference" | "endnoteReference") => {
                                let part_name = if kind == "footnoteReference" {
                                    "footnote"
                                } else {
                                    "endnote"
                                };
                                if let Some(id) = value(part, "id") {
                                    self.cited.push((part_name, id.to_owned()));
                                    // A raised number points to the note at the end.
                                    let mut mark = style.clone();
                                    mark.text = self.cited.len().to_string();
                                    mark.scale = scale * 0.7;
                                    open.inlines.push(mark);
                                }
                                continue;
                            }
                            "drawing" | "pict" | "object" | "AlternateContent" => {
                                self.picture(part, open, blank, wrote, depth);
                                continue;
                            }
                            _ => continue,
                        };
                        if !text.is_empty() {
                            open.inlines.push(Inline {
                                text,
                                ..style.clone()
                            });
                        }
                    }
                }
                _ if depth < DEEPEST => self.runs(item, look, size, open, blank, wrote, depth + 1),
                _ => {}
            }
        }
    }

    /// A drawing: a text box, whose paragraphs follow where it is anchored, or a picture.
    fn picture(
        &mut self,
        node: Node,
        open: &mut Paragraph,
        blank: &Paragraph,
        wrote: &mut bool,
        depth: usize,
    ) {
        // Newer files hold a box twice (for old and new readers): the first is enough.
        if let Some(contents) = node
            .descendants()
            .find(|n| n.tag_name().name() == "txbxContent")
        {
            if depth < DEEPEST {
                if !open.inlines.is_empty() {
                    self.blocks
                        .push(Block::Text(std::mem::replace(open, blank.clone())));
                    open.marker = None;
                }
                self.body(contents, depth + 1);
                *wrote = true;
            }
            return;
        }
        // `a:blip r:embed` in drawings, `v:imagedata r:id` in older ones.
        let found = node.descendants().find_map(|n| match n.tag_name().name() {
            "blip" => value(n, "embed"),
            "imagedata" => value(n, "id"),
            _ => None,
        });
        let Some(path) = found.and_then(|id| self.links.get(id)).cloned() else {
            return;
        };
        let Some(data) = self.package.read(&path) else {
            return;
        };
        // The width in EMUs, 12700 to the point.
        let width = node
            .descendants()
            .find(|n| n.tag_name().name() == "extent")
            .and_then(|n| value(n, "cx")?.parse::<f32>().ok())
            .map(|cx| cx / 12700.0);
        if !open.inlines.is_empty() {
            self.blocks
                .push(Block::Text(std::mem::replace(open, blank.clone())));
            open.marker = None;
        }
        self.blocks.push(Block::Picture {
            data: Arc::from(data),
            width,
            align: blank.align,
        });
        *wrote = true;
    }
}

pub fn docx(bytes: Vec<u8>) -> Result<Content, Error> {
    let mut package = Package::new(bytes)?;
    let document = package
        .read("word/document.xml")
        .ok_or_else(|| other("this is not a Word document"))?;
    let (styles, base) = match package.read("word/styles.xml") {
        Some(data) => with_xml(&data, read_styles)?,
        None => Default::default(),
    };
    let levels = match package.read("word/numbering.xml") {
        Some(data) => with_xml(&data, read_levels)?,
        None => HashMap::new(),
    };
    let links = match package.read("word/_rels/document.xml.rels") {
        Some(data) => with_xml(&data, |root| {
            root.children()
                .filter(|r| value(*r, "TargetMode") != Some("External"))
                .filter_map(|r| {
                    let target = value(r, "Target")?;
                    let path = match target.strip_prefix('/') {
                        Some(whole) => whole.to_owned(),
                        None => format!("word/{target}"),
                    };
                    Some((value(r, "Id")?.to_owned(), path))
                })
                .collect()
        })?,
        None => HashMap::new(),
    };
    let mut notes = HashMap::new();
    for kind in ["footnote", "endnote"] {
        if let Some(data) = package.read(&format!("word/{kind}s.xml")) {
            with_xml(&data, |root| {
                for note in root.children().filter(|n| n.tag_name().name() == kind) {
                    let Some(id) = value(note, "id") else {
                        continue;
                    };
                    let paragraphs: Vec<String> = note
                        .descendants()
                        .filter(|n| n.tag_name().name() == "p")
                        .map(|p| {
                            p.descendants()
                                .filter(|n| n.tag_name().name() == "t")
                                .filter_map(|n| n.text())
                                .collect()
                        })
                        .collect();
                    notes.insert(
                        (kind, id.to_owned()),
                        paragraphs.join("\n").trim().to_owned(),
                    );
                }
            })?;
        }
    }
    let mut reader = Reader {
        package,
        styles,
        base,
        links,
        levels,
        counts: HashMap::new(),
        blocks: Vec::new(),
        notes,
        cited: Vec::new(),
    };
    let text = super::markup::decode(&document);
    let doc = super::markup::parse_xml(&text)?;
    let body =
        child(doc.root_element(), "body").ok_or_else(|| other("the document has no body"))?;
    reader.body(body, 0);
    if !reader.cited.is_empty() {
        reader.blocks.push(Block::Rule);
        for (n, key) in reader.cited.iter().enumerate() {
            let text = reader.notes.get(key).cloned().unwrap_or_default();
            reader.blocks.push(Block::Text(Paragraph {
                inlines: vec![Inline {
                    text: format!("{}. {text}", n + 1),
                    ..Inline::default()
                }],
                size: TEXT_SIZE * 0.85,
                after: 3.0,
                ..Paragraph::default()
            }));
        }
    }
    if let Some(error) = reader.package.failure() {
        return Err(error);
    }
    Ok(Content {
        blocks: reader.blocks,
        margin: 33.0,
    })
}
