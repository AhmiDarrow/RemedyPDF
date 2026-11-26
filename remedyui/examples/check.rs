//! Drives `PdfFile` for tests/pdf.py.
//!   check dump <pdf> <password|-> <scale> <out.rgba>   prints the size, then one line per text run
//!   check edit <pdf> <password|-> <out.pdf> <picture>
//! and for any format, for tests/formats.py:
//!   check pages <file> <password|-> <prefix>      each page at 1 px per point, as prefix.N
//!   check export <file> <password|-> <out.pdf>

use remedy_ui::core::Rect;
use remedypdf::document::Document;
use remedypdf::pdf::{Error, PdfFile, export};
use remedypdf::source::Tiles;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let password = (a[2] != "-").then_some(a[2].as_str());
    if a[0] == "pages" || a[0] == "export" {
        let pages = match Document::open(a[1].as_ref(), password) {
            Err(Error::Password) => std::process::exit(3),
            other => other?.pages(),
        };
        if a[0] == "export" {
            return Ok(export(&*pages, a[3].as_ref())?);
        }
        for n in 0..pages.count() {
            let size = pages.size(n).ok_or("no page")?;
            let (w, h) = (
                size.width.round().max(1.0) as u32,
                size.height.round().max(1.0) as u32,
            );
            let tile =
                pages.render_tile(n, Rect::new(0.0, 0.0, size.width, size.height), 1.0, w, h)?;
            std::fs::write(format!("{}.{n}", a[3]), &tile.pixels[..])?;
            println!("{} {} {w} {h}", size.width, size.height);
            // Each page's text, kept apart from the sizes above.
            let mut text = String::new();
            for run in pages.runs(n).map(|t| t.runs).unwrap_or_default() {
                let b = run.bounds;
                text += &format!(
                    "{} {} {} {}\t{}\n",
                    b.min.x, b.min.y, b.max.x, b.max.y, run.text
                );
            }
            std::fs::write(format!("{}.{n}.txt", a[3]), text)?;
        }
        return Ok(());
    }
    let file = match PdfFile::open(a[1].as_ref(), password) {
        Err(Error::Password) => std::process::exit(3),
        other => other?,
    };
    match a[0].as_str() {
        "dump" => {
            let scale: f32 = a[3].parse()?;
            let size = file.size(0).ok_or("no page")?;
            let (w, h) = (
                (size.width * scale).round() as u32,
                (size.height * scale).round() as u32,
            );
            let tile = |x: u32, y: u32, width: u32, height: u32| {
                let region = Rect::new(
                    x as f32 / scale,
                    y as f32 / scale,
                    (x + width) as f32 / scale,
                    (y + height) as f32 / scale,
                );
                file.render_tile(0, region, scale, width, height)
            };
            let full = tile(0, 0, w, h)?;
            // A tile from the middle must match the same area of the whole page.
            let (x, y, tw, th) = (w / 5, h / 7, w / 2, h / 3);
            let part = tile(x, y, tw, th)?;
            let mut differing = 0usize;
            for row in 0..th {
                let from = (((y + row) * w + x) * 4) as usize;
                let part_row = &part.pixels[(row * tw * 4) as usize..][..(tw * 4) as usize];
                differing += part_row
                    .iter()
                    .zip(&full.pixels[from..])
                    .filter(|(p, f)| p.abs_diff(**f) > 8)
                    .count();
            }
            println!("{w} {h} {differing}");
            for run in file.runs(0).map(|t| t.runs).unwrap_or_default() {
                let b = run.bounds;
                println!(
                    "{} {} {} {}\t{}",
                    b.min.x, b.min.y, b.max.x, b.max.y, run.text
                );
            }
            std::fs::write(&a[4], &full.pixels[..])?;
        }
        "edit" => {
            file.add_text(0, 72.0, 200.0, "Added by Remedy", 18.0, [0, 0, 200])?;
            file.add_image(0, Rect::new(72.0, 250.0, 272.0, 450.0), a[4].as_ref())?;
            file.save(a[3].as_ref())?;
        }
        _ => return Err("unknown command".into()),
    }
    Ok(())
}
