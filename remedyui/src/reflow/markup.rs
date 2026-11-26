//! Readers for TXT, HTML, EPUB, FB2 and MOBI.

use super::{Block, Content, Inline, Justify, Paragraph, TEXT_SIZE};
use crate::pdf::Error;
use crate::zipped::Package;
use base64::Engine as _;
use html5ever::tendril::TendrilSink;
use markup5ever_rcdom::{Handle, NodeData, RcDom};
use std::collections::HashMap;
use std::path::{Component, Path};
use std::sync::Arc;

/// Elements nested deeper than this are read as if they were not nested.
const DEEPEST: usize = 200;

fn other(e: impl std::fmt::Display) -> Error {
    Error::Other(e.to_string())
}

/// Text in whatever encoding it declares or is marked with: UTF-8, UTF-16, else the charset
/// an HTML file names, else Windows-1252.
pub fn decode(bytes: &[u8]) -> String {
    if let Some((encoding, _)) = encoding_rs::Encoding::for_bom(bytes) {
        return encoding.decode(bytes).0.into_owned();
    }
    if let Ok(text) = std::str::from_utf8(bytes) {
        return text.to_owned();
    }
    let head = String::from_utf8_lossy(&bytes[..bytes.len().min(2048)]).to_ascii_lowercase();
    let named = ["charset=", "encoding="].iter().find_map(|key| {
        let rest = head.split_once(key)?.1.trim_start_matches(['"', '\'']);
        let end = rest.find(|c: char| !(c.is_ascii_alphanumeric() || "-_".contains(c)))?;
        encoding_rs::Encoding::for_label(&rest.as_bytes()[..end])
    });
    named
        .unwrap_or(encoding_rs::WINDOWS_1252)
        .decode(bytes)
        .0
        .into_owned()
}

pub fn text(bytes: &[u8]) -> Content {
    let blocks = decode(bytes)
        .lines()
        .map(|line| {
            // A form feed starts a page.
            if line == "\u{c}" {
                return Block::PageBreak;
            }
            let mut line = line.replace('\t', "        ").replace('\u{c}', "");
            if line.is_empty() {
                line.push(' ');
            }
            Block::Text(Paragraph {
                inlines: vec![Inline {
                    text: line,
                    mono: true,
                    ..Inline::default()
                }],
                ..Paragraph::default()
            })
        })
        .collect();
    Content {
        blocks,
        margin: 22.0,
    }
}

// ---- A small DOM, from XML where the file is well formed and from HTML otherwise ----

#[derive(Debug)]
enum Node {
    Text(String),
    Element {
        tag: String,
        attributes: Vec<(String, String)>,
        children: Vec<Node>,
    },
}

fn from_xml(node: roxmltree::Node, depth: usize, out: &mut Vec<Node>) {
    if node.is_text() {
        out.push(Node::Text(node.text().unwrap_or_default().to_owned()));
        return;
    }
    if depth >= DEEPEST {
        let text: String = node
            .descendants()
            .filter(roxmltree::Node::is_text)
            .filter_map(|n| n.text())
            .collect();
        out.push(Node::Text(text));
        return;
    }
    let mut children = Vec::new();
    for child in node.children() {
        from_xml(child, depth + 1, &mut children);
    }
    if node.is_element() {
        out.push(Node::Element {
            tag: node.tag_name().name().to_ascii_lowercase(),
            // `l:href` and `xlink:href` are both just `href` here.
            attributes: node
                .attributes()
                .map(|a| (a.name().to_ascii_lowercase(), a.value().to_owned()))
                .collect(),
            children,
        });
    } else {
        out.append(&mut children);
    }
}

/// All the text under `node`, however deeply it nests.
fn flat_text(node: &Handle) -> String {
    let mut text = String::new();
    let mut waiting = vec![node.clone()];
    while let Some(node) = waiting.pop() {
        if let NodeData::Text { contents } = &node.data {
            text.push_str(&contents.borrow());
        }
        waiting.extend(node.children.borrow().iter().rev().cloned());
    }
    text
}

fn from_html(node: &Handle, depth: usize, out: &mut Vec<Node>) {
    if depth >= DEEPEST {
        out.push(Node::Text(flat_text(node)));
        return;
    }
    match &node.data {
        NodeData::Text { contents } => out.push(Node::Text(contents.borrow().to_string())),
        NodeData::Element { name, attrs, .. } => {
            let mut children = Vec::new();
            for child in node.children.borrow().iter() {
                from_html(child, depth + 1, &mut children);
            }
            let attributes = attrs
                .borrow()
                .iter()
                .map(|a| {
                    (
                        a.name.local.to_ascii_lowercase().to_string(),
                        a.value.to_string(),
                    )
                })
                .collect();
            out.push(Node::Element {
                tag: name.local.to_string(),
                attributes,
                children,
            });
        }
        _ => {
            for child in node.children.borrow().iter() {
                from_html(child, depth + 1, out);
            }
        }
    }
}

/// Whether markup nests deeper than the XML parser, which recurses, can safely follow.
fn too_deep(source: &str) -> bool {
    let (mut depth, mut deepest) = (0usize, 0usize);
    for tag in source.split('<').skip(1) {
        let tag = tag.split('>').next().unwrap_or("");
        if tag.starts_with('/') {
            depth = depth.saturating_sub(1);
        } else if !tag.starts_with(['!', '?']) && !tag.ends_with('/') {
            depth += 1;
            deepest = deepest.max(depth);
        }
    }
    deepest > DEEPEST * 3
}

/// Parses XML that a document supplied.
pub(crate) fn parse_xml(text: &str) -> Result<roxmltree::Document<'_>, Error> {
    if too_deep(text) {
        return Err(other("the file nests too deeply"));
    }
    let options = roxmltree::ParsingOptions {
        allow_dtd: true,
        ..Default::default()
    };
    roxmltree::Document::parse_with_options(text, options).map_err(other)
}

fn dom(source: &str, try_xml: bool) -> Vec<Node> {
    let mut out = Vec::new();
    if try_xml && !too_deep(source) {
        let options = roxmltree::ParsingOptions {
            allow_dtd: true,
            ..Default::default()
        };
        if let Ok(doc) = roxmltree::Document::parse_with_options(source, options) {
            from_xml(doc.root_element(), 0, &mut out);
            return out;
        }
    }
    let dom = html5ever::parse_document(RcDom::default(), Default::default()).one(source);
    from_html(&dom.document, 0, &mut out);
    out
}

fn attribute<'a>(attributes: &'a [(String, String)], name: &str) -> Option<&'a str> {
    attributes
        .iter()
        .find(|(n, _)| n == name)
        .map(|(_, v)| v.as_str())
}

// ---- The part of CSS that books use for their look ----

#[derive(Default)]
struct Sheet {
    /// (tag, class, id, declarations); an empty part matches anything.
    rules: Vec<(String, String, String, String)>,
}

impl Sheet {
    fn add(&mut self, css: &str) {
        let mut rest = css;
        let mut clean = String::new();
        while let Some((before, after)) = rest.split_once("/*") {
            clean.push_str(before);
            rest = after.split_once("*/").map_or("", |(_, r)| r);
        }
        clean.push_str(rest);
        for rule in clean.split('}') {
            let Some((selectors, body)) = rule.rsplit_once('{') else {
                continue;
            };
            for selector in selectors.split(',') {
                let selector = selector.trim();
                // Only simple selectors: others would match more than they should.
                if selector.is_empty()
                    || selector.contains([' ', '>', '+', '~', ':', '[', '@', '*'])
                {
                    continue;
                }
                let (selector, id) = selector.split_once('#').unwrap_or((selector, ""));
                let (tag, class) = selector.split_once('.').unwrap_or((selector, ""));
                if !class.contains('.') {
                    self.rules.push((
                        tag.to_ascii_lowercase(),
                        class.into(),
                        id.into(),
                        body.into(),
                    ));
                }
            }
        }
    }

    /// The declarations that apply to an element, weakest first.
    fn declarations(&self, tag: &str, attributes: &[(String, String)]) -> Vec<(String, String)> {
        let classes: Vec<&str> = attribute(attributes, "class")
            .unwrap_or("")
            .split_whitespace()
            .collect();
        let id = attribute(attributes, "id").unwrap_or("");
        let mut matched: Vec<(u8, &str)> = self
            .rules
            .iter()
            .filter(|(t, c, i, _)| {
                (t.is_empty() || t == tag)
                    && (c.is_empty() || classes.contains(&c.as_str()))
                    && (i.is_empty() || i == id)
            })
            .map(|(t, c, i, body)| {
                let weight = u8::from(!t.is_empty())
                    + 2 * u8::from(!c.is_empty())
                    + 4 * u8::from(!i.is_empty());
                (weight, body.as_str())
            })
            .collect();
        matched.sort_by_key(|(weight, _)| *weight);
        matched.extend(attribute(attributes, "style").map(|s| (u8::MAX, s)));
        matched
            .iter()
            .flat_map(|(_, body)| body.split(';'))
            .filter_map(|d| d.split_once(':'))
            .map(|(k, v)| {
                let v = v.trim().trim_end_matches("!important").trim();
                (k.trim().to_ascii_lowercase(), v.to_ascii_lowercase())
            })
            .collect()
    }
}

/// A CSS length in points, relative to text of `em` points.
fn length(value: &str, em: f32) -> Option<f32> {
    let split = value
        .find(|c: char| c.is_ascii_alphabetic() || c == '%')
        .unwrap_or(value.len());
    let number: f32 = value[..split].trim().parse().ok()?;
    let points = match &value[split..] {
        "pt" => number,
        "px" | "" => number * 0.75,
        "em" => number * em,
        "rem" => number * TEXT_SIZE,
        "%" => number / 100.0 * em,
        "in" => number * 72.0,
        "cm" => number * 28.35,
        "mm" => number * 2.835,
        _ => return None,
    };
    points.is_finite().then_some(points)
}

fn color(value: &str) -> Option<[u8; 3]> {
    if let Some(hex) = value.strip_prefix('#').filter(|h| h.is_ascii()) {
        let digit = |i: usize, n: usize| u8::from_str_radix(&hex[i * n..(i + 1) * n], 16).ok();
        return match hex.len() {
            3 => Some([digit(0, 1)? * 17, digit(1, 1)? * 17, digit(2, 1)? * 17]),
            6 => Some([digit(0, 2)?, digit(1, 2)?, digit(2, 2)?]),
            _ => None,
        };
    }
    Some(match value {
        "red" => [255, 0, 0],
        "green" => [0, 128, 0],
        "blue" => [0, 0, 255],
        "gray" | "grey" => [128, 128, 128],
        "black" => [0, 0, 0],
        _ => return None,
    })
}

// ---- HTML to blocks ----

/// Fetches a picture or stylesheet a document refers to.
type Fetch<'a> = dyn FnMut(&str) -> Option<Arc<[u8]>> + 'a;

#[derive(Clone)]
struct Look {
    inline: Inline,
    size: f32,
    align: Justify,
    indent: f32,
    preformatted: bool,
}

struct Reader<'a, 'f> {
    fetch: &'a mut Fetch<'f>,
    css: Sheet,
    blocks: Vec<Block>,
    open: Paragraph,
    /// The next paragraph's marker, from a list item.
    marker: Option<String>,
    /// Open lists: the next number for an ordered one.
    lists: Vec<Option<u32>>,
}

impl Reader<'_, '_> {
    fn flush(&mut self) {
        let mut paragraph = std::mem::take(&mut self.open);
        if let Some(last) = paragraph.inlines.last_mut()
            && !last.text.ends_with('\n')
        {
            let kept = last.text.trim_end_matches(' ').len();
            last.text.truncate(kept);
        }
        paragraph.inlines.retain(|i| !i.text.is_empty());
        if !paragraph.inlines.is_empty() {
            self.blocks.push(Block::Text(paragraph));
        }
    }

    fn push_text(&mut self, text: &str, look: &Look) {
        let mut added = String::new();
        if look.preformatted {
            added = text.replace('\t', "        ").replace('\r', "");
        } else {
            let at_start = self
                .open
                .inlines
                .last()
                .is_none_or(|i| i.text.ends_with([' ', '\n']));
            let mut space = at_start;
            for c in text.chars() {
                // A non-breaking space is not white space here.
                if matches!(c, ' ' | '\t' | '\n' | '\r' | '\u{c}') {
                    if !space {
                        added.push(' ');
                    }
                    space = true;
                } else {
                    added.push(c);
                    space = false;
                }
            }
        }
        if added.is_empty() {
            return;
        }
        if self.open.inlines.is_empty() {
            self.open.size = look.size;
            self.open.align = look.align;
            self.open.indent = look.indent;
            self.open.marker = self.marker.take();
        }
        let mut inline = look.inline.clone();
        inline.scale *= look.size / self.open.size;
        inline.text = added;
        self.open.inlines.push(inline);
    }

    fn walk(&mut self, node: &Node, look: &Look) {
        let (tag, attributes, children) = match node {
            Node::Text(text) => return self.push_text(text, look),
            Node::Element {
                tag,
                attributes,
                children,
            } => (tag.as_str(), attributes, children),
        };
        match tag {
            "script" | "template" | "title" | "iframe" | "object" | "video" | "audio"
            | "noscript" => return,
            "style" => {
                for child in children {
                    if let Node::Text(css) = child {
                        self.css.add(css);
                    }
                }
                return;
            }
            "link" => {
                let stylesheet =
                    attribute(attributes, "rel").is_some_and(|r| r.contains("stylesheet"));
                if let Some(data) = attribute(attributes, "href")
                    .filter(|_| stylesheet)
                    .and_then(|h| (self.fetch)(h))
                {
                    self.css.add(&decode(&data));
                }
                return;
            }
            "br" => {
                let mut look = look.clone();
                look.preformatted = true;
                return self.push_text("\n", &look);
            }
            _ => {}
        }
        let mut look = look.clone();
        let mut block = matches!(
            tag,
            "p" | "div"
                | "section"
                | "article"
                | "header"
                | "footer"
                | "nav"
                | "aside"
                | "main"
                | "body"
                | "h1"
                | "h2"
                | "h3"
                | "h4"
                | "h5"
                | "h6"
                | "ul"
                | "ol"
                | "li"
                | "blockquote"
                | "pre"
                | "figure"
                | "figcaption"
                | "dl"
                | "dt"
                | "dd"
                | "center"
                | "address"
                | "table"
                | "hr"
                | "caption"
        );
        let (mut before, mut after) = (0.0, 0.0);
        let mut keep = false;
        let heading = |scale: f32| (TEXT_SIZE * scale, TEXT_SIZE * scale * 0.67);
        match tag {
            "p" | "ul" | "ol" | "dl" | "figure" => (before, after) = (look.size, look.size),
            "h1" | "h2" | "h3" | "h4" | "h5" | "h6" => {
                let scale = match tag {
                    "h1" => 2.0,
                    "h2" => 1.5,
                    "h3" => 1.17,
                    "h4" => 1.0,
                    "h5" => 0.83,
                    _ => 0.67,
                };
                let (size, space) = heading(scale);
                look.size = size;
                look.inline.bold = true;
                (before, after) = (space.max(TEXT_SIZE), space.max(TEXT_SIZE * 0.6));
                keep = true;
            }
            "b" | "strong" | "th" => look.inline.bold = true,
            "i" | "em" | "cite" | "var" | "dfn" | "address" => look.inline.italic = true,
            "u" | "ins" => look.inline.underline = true,
            "a" if attribute(attributes, "href").is_some() => {
                look.inline.underline = true;
                look.inline.color = Some([0, 0, 238]);
            }
            "s" | "strike" | "del" => look.inline.strike = true,
            "code" | "tt" | "kbd" | "samp" => look.inline.mono = true,
            "pre" => {
                look.inline.mono = true;
                look.preformatted = true;
                (before, after) = (look.size, look.size);
            }
            "small" => look.inline.scale *= 0.83,
            "big" => look.inline.scale *= 1.2,
            "sub" | "sup" => look.inline.scale *= 0.7,
            "blockquote" => {
                look.indent += look.size * 2.0;
                (before, after) = (look.size, look.size);
            }
            "dd" => look.indent += look.size * 2.0,
            "center" | "caption" => look.align = Justify::Center,
            _ => {}
        }
        match attribute(attributes, "align") {
            Some("center") => look.align = Justify::Center,
            Some("right") => look.align = Justify::End,
            Some("justify") => look.align = Justify::Both,
            _ => {}
        }
        let (mut break_before, mut break_after) = (false, false);
        for (property, value) in self.css.declarations(tag, attributes) {
            match property.as_str() {
                "display" if value == "none" => return,
                "display" if value == "block" => block = true,
                "text-align" => {
                    look.align = match value.as_str() {
                        "center" => Justify::Center,
                        "right" | "end" => Justify::End,
                        "justify" => Justify::Both,
                        _ => Justify::Start,
                    }
                }
                "font-weight" => {
                    look.inline.bold =
                        value.starts_with("bold") || value.parse::<u32>().is_ok_and(|w| w >= 600);
                }
                "font-style" => look.inline.italic = value == "italic" || value == "oblique",
                "font-family" if value.contains("mono") || value.contains("courier") => {
                    look.inline.mono = true
                }
                "text-decoration" | "text-decoration-line" => {
                    look.inline.underline = value.contains("underline");
                    look.inline.strike = value.contains("line-through");
                }
                "color" => look.inline.color = color(&value).or(look.inline.color),
                "font-size" => {
                    let size = match value.as_str() {
                        "x-small" => Some(TEXT_SIZE * 0.69),
                        "small" => Some(TEXT_SIZE * 0.83),
                        "medium" => Some(TEXT_SIZE),
                        "large" => Some(TEXT_SIZE * 1.2),
                        "x-large" => Some(TEXT_SIZE * 1.5),
                        v => length(v, look.size),
                    };
                    look.size = size.map_or(look.size, |s| s.clamp(4.0, 96.0));
                }
                "margin-left" if block => {
                    look.indent += length(&value, look.size).unwrap_or(0.0).clamp(0.0, 150.0);
                }
                "margin-top" => {
                    before = length(&value, look.size).map_or(before, |v| v.clamp(0.0, 100.0))
                }
                "margin-bottom" => {
                    after = length(&value, look.size).map_or(after, |v| v.clamp(0.0, 100.0))
                }
                "page-break-before" | "break-before" => {
                    break_before = value == "always" || value == "page"
                }
                "page-break-after" | "break-after" => {
                    break_after = value == "always" || value == "page"
                }
                _ => {}
            }
        }
        if block {
            self.flush();
        }
        if break_before {
            self.flush();
            self.blocks.push(Block::PageBreak);
        }
        match tag {
            "img" | "image" => {
                // `<image>` is SVG's, as EPUB covers use it.
                let source = attribute(attributes, "src")
                    .or_else(|| attribute(attributes, "href"))
                    .map(str::to_owned)
                    .or_else(|| attribute(attributes, "recindex").map(|r| format!("recindex:{r}")));
                if let Some(data) = source.and_then(|s| picture_data(&s, self.fetch)) {
                    self.flush();
                    let width = attribute(attributes, "width").and_then(|w| length(w, look.size));
                    self.blocks.push(Block::Picture {
                        data,
                        width,
                        align: look.align,
                    });
                } else if let Some(alt) = attribute(attributes, "alt") {
                    self.push_text(alt, &look);
                }
            }
            "hr" => self.blocks.push(Block::Rule),
            "mbp:pagebreak" | "pagebreak" => {
                self.flush();
                self.blocks.push(Block::PageBreak);
                for child in children {
                    self.walk(child, &look);
                }
            }
            "table" => self.table(attributes, children, &look),
            "ul" | "ol" => {
                let start = attribute(attributes, "start")
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(1);
                self.lists.push((tag == "ol").then_some(start));
                look.indent += look.size * 2.0;
                // A list inside a list has no space of its own.
                if self.lists.len() > 1 {
                    (before, after) = (0.0, 0.0);
                }
                let first = self.blocks.len();
                for child in children {
                    self.walk(child, &look);
                }
                self.flush();
                self.lists.pop();
                self.space(first, before, after);
            }
            _ => {
                if tag == "li" {
                    self.marker = Some(match self.lists.last_mut() {
                        Some(Some(n)) => {
                            let marker = format!("{n}.");
                            *n = n.saturating_add(1);
                            marker
                        }
                        _ => "\u{2022}".into(),
                    });
                }
                let first = self.blocks.len();
                for child in children {
                    self.walk(child, &look);
                }
                if block {
                    self.flush();
                    self.space(first, before, after);
                    if keep && let Some(Block::Text(p)) = self.blocks.last_mut() {
                        p.keep_with_next = true;
                    }
                }
            }
        }
        if break_after {
            self.flush();
            self.blocks.push(Block::PageBreak);
        }
    }

    /// Gives an element's top and bottom space to its first and last paragraphs.
    fn space(&mut self, first: usize, before: f32, after: f32) {
        if let Some(Block::Text(p)) = self.blocks.get_mut(first) {
            p.before = p.before.max(before);
        }
        if self.blocks.len() > first
            && let Some(Block::Text(p)) = self.blocks.last_mut()
        {
            p.after = p.after.max(after);
        }
    }

    fn table(&mut self, attributes: &[(String, String)], children: &[Node], look: &Look) {
        let mut rows = Vec::new();
        self.rows(children, look, &mut rows);
        let borders = attribute(attributes, "border").is_some_and(|b| b != "0");
        self.blocks.push(Block::Table { rows, borders });
    }

    fn rows(&mut self, nodes: &[Node], look: &Look, rows: &mut Vec<Vec<Vec<Block>>>) {
        for node in nodes {
            let Node::Element { tag, children, .. } = node else {
                continue;
            };
            match tag.as_str() {
                "tr" => {
                    let mut row = Vec::new();
                    for cell in children {
                        let Node::Element { tag, .. } = cell else {
                            continue;
                        };
                        if tag != "td" && tag != "th" {
                            continue;
                        }
                        let outer = std::mem::take(&mut self.blocks);
                        let mut inside = look.clone();
                        inside.indent = 0.0;
                        self.walk(cell, &inside);
                        self.flush();
                        row.push(std::mem::replace(&mut self.blocks, outer));
                    }
                    rows.push(row);
                }
                "thead" | "tbody" | "tfoot" => self.rows(children, look, rows),
                "caption" => self.walk(node, look),
                _ => {}
            }
        }
    }
}

fn picture_data(source: &str, fetch: &mut Fetch) -> Option<Arc<[u8]>> {
    if let Some(rest) = source.strip_prefix("data:") {
        let (kind, data) = rest.split_once(',')?;
        if !kind.ends_with(";base64") {
            return None;
        }
        return base64_bytes(data);
    }
    fetch(source)
}

fn base64_bytes(text: &str) -> Option<Arc<[u8]>> {
    let clean: String = text.chars().filter(|c| !c.is_ascii_whitespace()).collect();
    base64::engine::general_purpose::STANDARD
        .decode(clean)
        .ok()
        .map(Arc::from)
}

fn read_html(source: &str, xml: bool, fetch: &mut Fetch, blocks: &mut Vec<Block>) {
    let nodes = dom(source, xml);
    let mut reader = Reader {
        fetch,
        css: Sheet::default(),
        blocks: std::mem::take(blocks),
        open: Paragraph::default(),
        marker: None,
        lists: Vec::new(),
    };
    let look = Look {
        inline: Inline::default(),
        size: TEXT_SIZE,
        align: Justify::Start,
        indent: 0.0,
        preformatted: false,
    };
    for node in &nodes {
        reader.walk(node, &look);
    }
    reader.flush();
    *blocks = reader.blocks;
}

/// A reference as a path within the folder `base`, or `None` if it points anywhere else.
fn within(base: &str, reference: &str) -> Option<String> {
    let reference = reference.split(['#', '?']).next()?;
    if reference.is_empty() || reference.contains(':') || reference.starts_with(['/', '\\']) {
        return None;
    }
    let reference = percent_encoding::percent_decode_str(reference)
        .decode_utf8()
        .ok()?;
    let mut parts: Vec<&str> = base.split('/').filter(|p| !p.is_empty()).collect();
    for part in reference.split(['/', '\\']) {
        match part {
            "" | "." => {}
            ".." => {
                parts.pop()?;
            }
            p if p.contains(':') => return None,
            p => parts.push(p),
        }
    }
    Some(parts.join("/"))
}

/// An HTML file. Pictures and stylesheets may come from its folder and below, nowhere else.
pub fn html(bytes: &[u8], path: &Path) -> Content {
    let folder = path.parent().map(Path::to_path_buf).unwrap_or_default();
    let mut fetch = move |reference: &str| -> Option<Arc<[u8]>> {
        let relative = within("", reference)?;
        if !Path::new(&relative)
            .components()
            .all(|c| matches!(c, Component::Normal(_)))
        {
            return None;
        }
        // A link inside the folder must not lead out of it.
        let file = folder.join(relative).canonicalize().ok()?;
        let root = if folder.as_os_str().is_empty() {
            Path::new(".")
        } else {
            &folder
        };
        if !file.starts_with(root.canonicalize().ok()?) || file.metadata().ok()?.len() > 64 << 20 {
            return None;
        }
        std::fs::read(file).ok().map(Arc::from)
    };
    let xml = path
        .extension()
        .is_some_and(|e| e.eq_ignore_ascii_case("xhtml"));
    let mut blocks = Vec::new();
    read_html(&decode(bytes), xml, &mut fetch, &mut blocks);
    Content {
        blocks,
        margin: 33.0,
    }
}

pub fn epub(bytes: Vec<u8>) -> Result<Content, Error> {
    let mut package = Package::new(bytes)?;
    let xml = |package: &mut Package, name: &str| -> Result<String, Error> {
        let data = package
            .read(name)
            .ok_or_else(|| other(format!("the book has no {name}")))?;
        Ok(decode(&data))
    };
    let parse = |text: &str| {
        let doc = parse_xml(text)?;
        let mut out = Vec::new();
        from_xml(doc.root_element(), 0, &mut out);
        Ok::<_, Error>(out)
    };
    fn each<'a>(nodes: &'a [Node], found: &mut dyn FnMut(&'a str, &'a [(String, String)])) {
        for node in nodes {
            if let Node::Element {
                tag,
                attributes,
                children,
            } = node
            {
                found(tag, attributes);
                each(children, found);
            }
        }
    }
    let container = parse(&xml(&mut package, "META-INF/container.xml")?)?;
    let mut opf = None;
    each(&container, &mut |tag, a| {
        if tag == "rootfile" && opf.is_none() {
            opf = attribute(a, "full-path").map(str::to_owned);
        }
    });
    let opf = opf.ok_or_else(|| other("the book does not say where its contents are"))?;
    let base = opf
        .rsplit_once('/')
        .map_or("", |(folder, _)| folder)
        .to_owned();
    let listing = parse(&xml(&mut package, &opf)?)?;
    let (mut items, mut spine) = (HashMap::new(), Vec::new());
    each(&listing, &mut |tag, a| match tag {
        "item" => {
            if let (Some(id), Some(href)) = (attribute(a, "id"), attribute(a, "href")) {
                items.insert(id.to_owned(), href.to_owned());
            }
        }
        "itemref" => spine.extend(attribute(a, "idref").map(str::to_owned)),
        _ => {}
    });
    let mut blocks = Vec::new();
    for id in spine {
        let Some(chapter) = items.get(&id).and_then(|href| within(&base, href)) else {
            continue;
        };
        let Some(data) = package.read(&chapter) else {
            continue;
        };
        let source = decode(&data);
        // Copy-protected chapters are not text.
        if source.contains('\0') {
            return Err(other("this book is copy protected"));
        }
        let folder = chapter
            .rsplit_once('/')
            .map_or("", |(folder, _)| folder)
            .to_owned();
        let mut fetch = |reference: &str| package.read(&within(&folder, reference)?).map(Arc::from);
        blocks.push(Block::PageBreak);
        read_html(&source, true, &mut fetch, &mut blocks);
    }
    if let Some(error) = package.failure() {
        return Err(error);
    }
    Ok(Content {
        blocks,
        margin: 33.0,
    })
}

pub fn fb2(bytes: &[u8]) -> Result<Content, Error> {
    let source = decode(bytes);
    let doc = parse_xml(&source)?;
    let root = doc.root_element();
    let pictures: HashMap<&str, Arc<[u8]>> = root
        .children()
        .filter(|n| n.tag_name().name() == "binary")
        .filter_map(|n| Some((n.attribute("id")?, base64_bytes(n.text()?)?)))
        .collect();
    let mut book = Fb2 {
        pictures,
        blocks: Vec::new(),
    };
    // The cover is named in the description.
    for cover in root
        .descendants()
        .filter(|n| n.tag_name().name() == "coverpage")
    {
        for image in cover.children() {
            book.picture(image);
        }
    }
    for body in root.children().filter(|n| n.tag_name().name() == "body") {
        book.blocks.push(Block::PageBreak);
        book.element(body, 0, 0.0, Justify::Both);
    }
    Ok(Content {
        blocks: book.blocks,
        margin: 33.0,
    })
}

struct Fb2<'a> {
    pictures: HashMap<&'a str, Arc<[u8]>>,
    blocks: Vec<Block>,
}

impl Fb2<'_> {
    fn picture(&mut self, node: roxmltree::Node) {
        let href = node
            .attributes()
            .find(|a| a.name() == "href")
            .map(|a| a.value());
        if let Some(data) = href.and_then(|h| self.pictures.get(h.trim_start_matches('#'))) {
            self.blocks.push(Block::Picture {
                data: data.clone(),
                width: None,
                align: Justify::Center,
            });
        }
    }

    fn element(&mut self, node: roxmltree::Node, depth: usize, indent: f32, align: Justify) {
        if depth > DEEPEST {
            return;
        }
        let name = node.tag_name().name();
        match name {
            "image" => self.picture(node),
            "empty-line" => self.line(Vec::new(), TEXT_SIZE, indent, align),
            "p" | "v" | "subtitle" | "text-author" | "date" => {
                let parent = node.parent().map_or("", |p| p.tag_name().name());
                let mut look = Inline::default();
                let (mut size, mut align) = (TEXT_SIZE, align);
                if parent == "title" {
                    (size, align, look.bold) = (TEXT_SIZE * 1.5, Justify::Center, true);
                }
                match name {
                    "subtitle" => (align, look.bold) = (Justify::Center, true),
                    "text-author" => (align, look.italic) = (Justify::End, true),
                    "v" => align = Justify::Start,
                    _ => {}
                }
                let mut inlines = Vec::new();
                spans(node, &look, 0, &mut inlines);
                self.line(inlines, size, indent, align);
                if parent == "title"
                    && let Some(Block::Text(p)) = self.blocks.last_mut()
                {
                    p.keep_with_next = true;
                    p.after = TEXT_SIZE;
                }
                for child in node.children().filter(|c| c.tag_name().name() == "image") {
                    self.picture(child);
                }
            }
            "table" => {
                let rows = node
                    .children()
                    .filter(|r| r.tag_name().name() == "tr")
                    .map(|row| {
                        row.children()
                            .filter(roxmltree::Node::is_element)
                            .map(|cell| {
                                let mut inlines = Vec::new();
                                spans(cell, &Inline::default(), 0, &mut inlines);
                                vec![Block::Text(Paragraph {
                                    inlines,
                                    ..Paragraph::default()
                                })]
                            })
                            .collect()
                    })
                    .collect();
                self.blocks.push(Block::Table {
                    rows,
                    borders: true,
                });
            }
            _ => {
                // Chapters start on their own page.
                if name == "section" && node.parent().is_some_and(|p| p.tag_name().name() == "body")
                {
                    self.blocks.push(Block::PageBreak);
                }
                let indent = indent
                    + match name {
                        "cite" | "poem" | "epigraph" => TEXT_SIZE * 2.0,
                        _ => 0.0,
                    };
                for child in node.children().filter(roxmltree::Node::is_element) {
                    self.element(child, depth + 1, indent, align);
                }
            }
        }
    }

    fn line(&mut self, mut inlines: Vec<Inline>, size: f32, indent: f32, align: Justify) {
        if inlines.iter().all(|i| i.text.trim().is_empty()) {
            inlines = vec![Inline {
                text: " ".into(),
                ..Inline::default()
            }];
        }
        self.blocks.push(Block::Text(Paragraph {
            inlines,
            size,
            indent,
            align,
            after: size * 0.3,
            ..Paragraph::default()
        }));
    }
}

fn spans(node: roxmltree::Node, look: &Inline, depth: usize, out: &mut Vec<Inline>) {
    for child in node.children() {
        if child.is_text() {
            let words: Vec<&str> = child
                .text()
                .unwrap_or("")
                .split_ascii_whitespace()
                .collect();
            let raw = child.text().unwrap_or("");
            let mut text = words.join(" ");
            if raw.starts_with(|c: char| c.is_ascii_whitespace()) && !out.is_empty() {
                text.insert(0, ' ');
            }
            if raw.ends_with(|c: char| c.is_ascii_whitespace()) && !words.is_empty() {
                text.push(' ');
            }
            if !text.is_empty() {
                out.push(Inline {
                    text,
                    ..look.clone()
                });
            }
        } else if depth < DEEPEST {
            let mut look = look.clone();
            match child.tag_name().name() {
                "emphasis" => look.italic = true,
                "strong" => look.bold = true,
                "code" => look.mono = true,
                "strikethrough" => look.strike = true,
                "sub" | "sup" => look.scale *= 0.7,
                _ => {}
            }
            spans(child, &look, depth + 1, out);
        }
    }
}

pub fn mobi(bytes: &[u8]) -> Result<Content, Error> {
    let book = super::mobi::read(bytes)?;
    let mut fetch = |reference: &str| {
        // Pictures are numbered from 1.
        let number: usize = reference.strip_prefix("recindex:")?.parse().ok()?;
        book.pictures.get(number.checked_sub(1)?).cloned()
    };
    let mut blocks = Vec::new();
    read_html(&book.text, false, &mut fetch, &mut blocks);
    Ok(Content {
        blocks,
        margin: 33.0,
    })
}
