//! MOBI files: the PalmDB container, both of its compressions, and its pictures. The markup
//! inside is read as HTML. (The `mobi` crate is not used: it drops the last text record.)

use crate::pdf::Error;
use std::sync::Arc;

/// Text that expands past this is a decompression bomb.
const MAX_TEXT: usize = 256 << 20;
const DEEPEST: usize = 32;

fn broken() -> Error {
    Error::Other("this MOBI file is damaged".into())
}

fn u16_at(data: &[u8], at: usize) -> Option<u16> {
    Some(u16::from_be_bytes(
        data.get(at..at.checked_add(2)?)?.try_into().ok()?,
    ))
}

fn u32_at(data: &[u8], at: usize) -> Option<u32> {
    Some(u32::from_be_bytes(
        data.get(at..at.checked_add(4)?)?.try_into().ok()?,
    ))
}

fn records(file: &[u8]) -> Option<Vec<&[u8]>> {
    let count = usize::from(u16_at(file, 76)?);
    let starts: Vec<usize> = (0..count)
        .map(|n| u32_at(file, 78 + n * 8).map(|v| v as usize))
        .collect::<Option<_>>()?;
    (0..count)
        .map(|n| file.get(starts[n]..starts.get(n + 1).copied().unwrap_or(file.len())))
        .collect()
}

/// Removes the index data that follows a text record's own bytes, as the header's flags say.
fn trim(mut data: &[u8], flags: u16) -> &[u8] {
    for bit in 1..16 {
        if flags & (1 << bit) != 0 {
            // Each entry ends with its own length, seven bits to a byte.
            let mut size = 0usize;
            for byte in &data[data.len().saturating_sub(4)..] {
                if byte & 0x80 != 0 {
                    size = 0;
                }
                size = (size << 7) | usize::from(byte & 0x7f);
            }
            data = &data[..data.len().saturating_sub(size)];
        }
    }
    if flags & 1 != 0
        && let Some(last) = data.last()
    {
        data = &data[..data.len().saturating_sub(usize::from(last & 3) + 1)];
    }
    data
}

/// PalmDoc's LZ77.
fn palmdoc(data: &[u8], out: &mut Vec<u8>) -> Option<()> {
    let start = out.len();
    let mut at = 0;
    while let Some(&c) = data.get(at) {
        at += 1;
        match c {
            1..=8 => {
                out.extend_from_slice(data.get(at..at + usize::from(c))?);
                at += usize::from(c);
            }
            0 | 9..=0x7f => out.push(c),
            0x80..=0xbf => {
                let pair = (usize::from(c) << 8 | usize::from(*data.get(at)?)) & 0x3fff;
                at += 1;
                let (back, length) = (pair >> 3, (pair & 7) + 3);
                if back == 0 || back > out.len() - start {
                    return None;
                }
                for _ in 0..length {
                    out.push(out[out.len() - back]);
                }
            }
            0xc0.. => out.extend_from_slice(&[b' ', c ^ 0x80]),
        }
    }
    Some(())
}

/// Huffman codes into a dictionary of phrases, which may themselves be coded.
struct Huff<'a> {
    /// By a code's first byte: its length, whether that is final, and the largest such code.
    first: [(u32, bool, u64); 256],
    least: [u64; 33],
    most: [u64; 33],
    phrases: Vec<(&'a [u8], bool)>,
    /// Phrases already expanded.
    expanded: Vec<Option<Arc<[u8]>>>,
    /// Phrases being expanded, so that one cannot contain itself.
    busy: Vec<bool>,
}

impl<'a> Huff<'a> {
    fn new(tables: &[&'a [u8]]) -> Option<Self> {
        let (huff, dictionaries) = tables.split_first()?;
        if !huff.starts_with(b"HUFF") {
            return None;
        }
        let (a, b) = (u32_at(huff, 8)? as usize, u32_at(huff, 12)? as usize);
        let mut first = [(0, false, 0); 256];
        for (i, entry) in first.iter_mut().enumerate() {
            let v = u32_at(huff, a + i * 4)?;
            let length = v & 0x1f;
            if length == 0 {
                return None;
            }
            let largest = ((u64::from(v >> 8) + 1) << (32 - length)) - 1;
            *entry = (length, v & 0x80 != 0, largest);
        }
        let (mut least, mut most) = ([0; 33], [0; 33]);
        for length in 1..=32 {
            let at = b + (length - 1) * 8;
            least[length] = u64::from(u32_at(huff, at)?) << (32 - length);
            most[length] =
                ((u64::from(u32_at(huff, at + 4)?) + 1) << (32 - length)).wrapping_sub(1);
        }
        let mut phrases = Vec::new();
        for table in dictionaries {
            if !table.starts_with(b"CDIC") {
                return None;
            }
            let total = u32_at(table, 8)? as usize;
            let bits = u32_at(table, 12)?;
            let count = (1usize << bits.min(16)).min(total.saturating_sub(phrases.len()));
            for n in 0..count {
                let offset = usize::from(u16_at(table, 16 + n * 2)?);
                let header = u16_at(table, 16 + offset)?;
                let begin = 18 + offset;
                let phrase = table.get(begin..begin + usize::from(header & 0x7fff))?;
                phrases.push((phrase, header & 0x8000 != 0));
            }
        }
        let count = phrases.len();
        Some(Huff {
            first,
            least,
            most,
            phrases,
            expanded: vec![None; count],
            busy: vec![false; count],
        })
    }

    fn unpack(&mut self, data: &[u8], out: &mut Vec<u8>, depth: usize) -> Option<()> {
        let mut bits_left = data.len() as i64 * 8;
        let mut padded = data.to_vec();
        padded.extend([0; 8]);
        let window = |at: usize| {
            padded
                .get(at..at + 8)?
                .try_into()
                .ok()
                .map(u64::from_be_bytes)
        };
        let (mut at, mut x, mut n) = (0usize, window(0)?, 32i32);
        loop {
            if n <= 0 {
                at += 4;
                x = window(at)?;
                n += 32;
            }
            let code = (x >> n) & 0xffff_ffff;
            let (mut length, fixed, mut largest) = self.first[(code >> 24) as usize];
            if !fixed {
                while code < *self.least.get(length as usize)? {
                    length += 1;
                }
                largest = *self.most.get(length as usize)?;
            }
            n -= length as i32;
            bits_left -= i64::from(length);
            if bits_left < 0 {
                return Some(());
            }
            let index = (largest.checked_sub(code)? >> (32 - length)) as usize;
            let (phrase, plain) = *self.phrases.get(index)?;
            if plain {
                out.extend_from_slice(phrase);
            } else if let Some(done) = &self.expanded[index] {
                out.extend_from_slice(done);
            } else {
                if self.busy[index] || depth >= DEEPEST {
                    return None;
                }
                self.busy[index] = true;
                let mut inner = Vec::new();
                self.unpack(phrase, &mut inner, depth + 1)?;
                self.busy[index] = false;
                out.extend_from_slice(&inner);
                self.expanded[index] = Some(inner.into());
            }
            if out.len() > MAX_TEXT {
                return None;
            }
        }
    }
}

pub struct Mobi {
    /// The book's HTML.
    pub text: String,
    /// Records that may be pictures; `recindex="1"` is the first.
    pub pictures: Vec<Arc<[u8]>>,
}

pub fn read(file: &[u8]) -> Result<Mobi, Error> {
    if !matches!(file.get(60..68), Some(b"BOOKMOBI" | b"TEXtREAd")) {
        return Err(broken());
    }
    let records = records(file).ok_or_else(broken)?;
    let head = *records.first().ok_or_else(broken)?;
    let compression = u16_at(head, 0).ok_or_else(broken)?;
    let count = usize::from(u16_at(head, 8).ok_or_else(broken)?);
    if u16_at(head, 12).ok_or_else(broken)? != 0 {
        return Err(Error::Other("this book is copy protected".into()));
    }
    // A plain PalmDoc has no MOBI header.
    let mobi = head.get(16..20) == Some(b"MOBI");
    let header = if mobi {
        u32_at(head, 20).unwrap_or(0)
    } else {
        0
    };
    let utf8 = mobi && u32_at(head, 28) == Some(65001);
    let flags = if header >= 0xe4 {
        u16_at(head, 242).unwrap_or(0)
    } else {
        0
    };
    let sections = records.get(1..=count).ok_or_else(broken)?;
    let mut raw = Vec::new();
    match compression {
        1 => sections
            .iter()
            .for_each(|s| raw.extend_from_slice(trim(s, flags))),
        2 => {
            for section in sections {
                palmdoc(trim(section, flags), &mut raw).ok_or_else(broken)?;
                if raw.len() > MAX_TEXT {
                    return Err(broken());
                }
            }
        }
        // "DH"
        0x4448 => {
            let start = u32_at(head, 112).ok_or_else(broken)? as usize;
            let tables = u32_at(head, 116).ok_or_else(broken)? as usize;
            let tables = records
                .get(start..start.saturating_add(tables))
                .ok_or_else(broken)?;
            let mut huff = Huff::new(tables).ok_or_else(broken)?;
            for section in sections {
                huff.unpack(trim(section, flags), &mut raw, 0)
                    .ok_or_else(broken)?;
            }
        }
        _ => {
            return Err(Error::Other(
                "this MOBI uses a compression that is not supported".into(),
            ));
        }
    }
    let text = if utf8 {
        String::from_utf8_lossy(&raw).into_owned()
    } else {
        encoding_rs::WINDOWS_1252.decode(&raw).0.into_owned()
    };
    let first = mobi
        .then(|| u32_at(head, 108))
        .flatten()
        .map_or(usize::MAX, |v| v as usize);
    let pictures = records
        .get(first..)
        .unwrap_or(&[])
        .iter()
        .map(|r| Arc::from(*r))
        .collect();
    Ok(Mobi { text, pictures })
}
