//! How things look: the nine themes of 1.x (window and page colours) and the page filters.

use remedy_ui::core::style::Theme;
use remedy_ui::core::{Color, ColorMatrix};
use remedy_ui::themes;

/// A theme's colours, as 1.x had them. Pages are recoloured to `ink` on `paper`.
pub struct Look {
    pub id: &'static str,
    pub label: &'static str,
    bg: u32,
    panel: u32,
    card: u32,
    line: u32,
    text: u32,
    muted: u32,
    faint: u32,
    accent: u32,
    accent_hover: u32,
    on_accent: u32,
    /// `None`: pages keep their own colours.
    page: Option<(u32, u32)>,
}

macro_rules! look {
    ($id:literal, $label:literal, $($v:expr),+; $page:expr) => {
        look!(@ $id, $label, $($v),+; $page)
    };
    (@ $id:literal, $label:literal, $bg:expr, $panel:expr, $card:expr, $line:expr, $text:expr, $muted:expr,
     $faint:expr, $accent:expr, $hover:expr, $on:expr; $page:expr) => {
        Look { id: $id, label: $label, bg: $bg, panel: $panel, card: $card, line: $line, text: $text,
               muted: $muted, faint: $faint, accent: $accent, accent_hover: $hover, on_accent: $on, page: $page }
    };
}

/// In the order the theme command cycles through.
pub const LOOKS: [Look; 9] = [
    look!("normal", "Normal (no theme)", 0xF0F0F0, 0xFFFFFF, 0xF7F7F7, 0xC8C8C8, 0x1A1A1A, 0x4A4A4A, 0x808080,
          0x0067C0, 0x1975C5, 0xFFFFFF; None),
    look!("dark", "Dark", 0x1A1B26, 0x24283B, 0x1F2335, 0x3B4261, 0xC0CAF5, 0x9AA5CE, 0x565F89,
          0x6C5CE7, 0x7F71F0, 0xFFFFFF; Some((0xC0CAF5, 0x1A1B26))),
    look!("light", "Light", 0xF7F8FC, 0xFFFFFF, 0xEEF0F7, 0xD8DCE8, 0x1A1B26, 0x4A5168, 0x8B93A7,
          0x6C5CE7, 0x7F71F0, 0xFFFFFF; Some((0x1A1B26, 0xFFFFFF))),
    look!("high_contrast", "High contrast", 0x000000, 0x0A0A0A, 0x141414, 0xFFFFFF, 0xFFFFFF, 0xF0F0F0, 0xBBBBBB,
          0x00E5FF, 0x66F0FF, 0x000000; Some((0xFFFFFF, 0x000000))),
    look!("sepia", "Sepia (paper)", 0xF4ECD8, 0xFBF6EA, 0xEDE4CF, 0xC9B896, 0x3B2F1E, 0x5C4A32, 0x8A7350,
          0x8B6914, 0xA67C1A, 0xFFF8E7; Some((0x3B2F1E, 0xF4ECD8))),
    look!("night", "Night (OLED)", 0x000000, 0x0B0D12, 0x12151C, 0x2A3142, 0xA8B4D4, 0x7A869E, 0x4A5568,
          0x7C6CF0, 0x9588F5, 0xFFFFFF; Some((0xA8B4D4, 0x000000))),
    look!("midnight", "Midnight blue", 0x0D1526, 0x152238, 0x101C30, 0x2A4060, 0xD6E4FF, 0x9BB0D4, 0x5A7198,
          0x4C8DFF, 0x6BA3FF, 0xFFFFFF; Some((0xD6E4FF, 0x0D1526))),
    look!("paper", "Soft paper", 0xF3EFE6, 0xFAF7F0, 0xEBE6DA, 0xD0C8B6, 0x2C2820, 0x5A5346, 0x8A8274,
          0x5B4FC7, 0x6C5CE7, 0xFFFFFF; Some((0x2C2820, 0xFAF7F0))),
    look!("slate", "Slate gray", 0x1E2228, 0x272C34, 0x22262E, 0x3D4450, 0xE8EAED, 0xB0B6C0, 0x6B7280,
          0x7B6CF0, 0x9588F5, 0xFFFFFF; Some((0xE8EAED, 0x1E2228))),
];

fn rgb(v: u32) -> Color {
    let [_, r, g, b] = v.to_be_bytes();
    Color::rgb8(r, g, b)
}

pub fn find(id: &str) -> &'static Look {
    LOOKS.iter().find(|l| l.id == id).unwrap_or(&LOOKS[0])
}

pub fn next(id: &str) -> &'static Look {
    let at = LOOKS.iter().position(|l| l.id == id).unwrap_or(0);
    &LOOKS[(at + 1) % LOOKS.len()]
}

impl Look {
    /// The window theme, with text `scale` times its usual size.
    pub fn theme(&self, scale: f32) -> Theme {
        // Every colour below replaces the base palette's.
        let base = themes::PALETTES
            .iter()
            .find(|p| p.id == "light")
            .unwrap_or(&themes::PALETTES[0]);
        let mut theme = themes::theme(base);
        theme.name = self.label.to_owned();
        theme.text_scale = scale;
        let c = &mut theme.colors;
        (c.bg, c.panel, c.card, c.text, c.muted) = (
            rgb(self.bg),
            rgb(self.panel),
            rgb(self.card),
            rgb(self.text),
            rgb(self.muted),
        );
        (c.accent, c.on_accent, c.line) =
            (rgb(self.accent), rgb(self.on_accent), Some(rgb(self.line)));
        c.custom.insert("faint".into(), rgb(self.faint));
        c.custom
            .insert("accent-hover".into(), rgb(self.accent_hover));
        theme
    }
}

pub const FILTERS: [(&str, &str); 6] = [
    ("none", "Normal page"),
    ("invert", "Invert page (dark paper)"),
    ("sepia", "Sepia page"),
    ("grayscale", "Grayscale page"),
    ("warm", "Warm page"),
    ("cool", "Cool page"),
];

pub fn filter_label(id: &str) -> &'static str {
    FILTERS
        .iter()
        .find(|f| f.0 == id)
        .map_or(FILTERS[0].1, |f| f.1)
}

/// The change to page colours, in 1.x's order: the theme's ink and paper, brightness,
/// contrast, then the named filter. View only: the document is not touched.
pub fn page_colors(
    theme: &str,
    filter: &str,
    brightness: f32,
    contrast: f32,
) -> Option<ColorMatrix> {
    let mut steps = Vec::new();
    if let Some((ink, paper)) = find(theme).page {
        steps.push(ColorMatrix::ink_paper(rgb(ink), rgb(paper)));
    }
    if (brightness - 1.0).abs() > 1e-3 {
        steps.push(ColorMatrix::brightness(brightness));
    }
    if (contrast - 1.0).abs() > 1e-3 {
        steps.push(ColorMatrix::contrast(contrast));
    }
    match filter {
        "invert" => steps.push(ColorMatrix::invert(1.0)),
        "sepia" => steps.push(ColorMatrix::sepia(1.0)),
        "grayscale" => steps.push(ColorMatrix::grayscale(1.0)),
        "warm" => steps.push(ColorMatrix::warm(1.0)),
        "cool" => steps.push(ColorMatrix::cool(1.0)),
        _ => {}
    }
    steps.into_iter().reduce(|all, step| all.then(&step))
}
