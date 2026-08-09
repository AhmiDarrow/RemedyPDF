"""Build RemedyPDF icon + logo from Remedy brand references + PDF badge."""
from __future__ import annotations

import shutil
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources"
REF = OUT / "brand_ref"
REF.mkdir(parents=True, exist_ok=True)

# Source brand assets (read-only)
SOURCES = {
    "icon": Path(r"C:\Users\Administrator\Old-Remedy\assets\remedy_icon.png"),
    "logo": Path(r"C:\Users\Administrator\Old-Remedy\assets\remedy_logo.png"),
    "icon_dark": Path(
        r"C:\Users\Administrator\Desktop\Remedy_logo_previews\hero_icon_color_on_dark.png"
    ),
    "logo_dark": Path(
        r"C:\Users\Administrator\Desktop\Remedy_logo_previews\hero_logo_color_on_dark.png"
    ),
    "icon_light": Path(
        r"C:\Users\Administrator\Desktop\Remedy_logo_previews\hero_icon_color_on_light.png"
    ),
    "logo_light": Path(
        r"C:\Users\Administrator\Desktop\Remedy_logo_previews\hero_logo_color_on_light.png"
    ),
}

# Brand-ish palette (Remedy teal / cyan on dark)
TEAL = (0, 212, 190, 255)
TEAL_DEEP = (0, 150, 140, 255)
PDF_RED = (220, 53, 69, 255)
PDF_RED_DARK = (170, 30, 45, 255)
WHITE = (255, 255, 255, 255)
INK = (18, 22, 28, 255)
SOFT = (230, 245, 242, 255)


def copy_refs() -> dict[str, Path]:
    local: dict[str, Path] = {}
    for key, src in SOURCES.items():
        if not src.is_file():
            print(f"skip missing: {src}")
            continue
        dest = REF / src.name
        shutil.copy2(src, dest)
        local[key] = dest
        im = Image.open(dest)
        print(f"ref {key}: {dest.name} {im.size} {im.mode}")
    return local


def _font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _trim_alpha(im: Image.Image, pad: int = 0) -> Image.Image:
    im = im.convert("RGBA")
    bbox = im.getbbox()
    if not bbox:
        return im
    im = im.crop(bbox)
    if pad:
        canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
        canvas.paste(im, (pad, pad), im)
        return canvas
    return im


def _rounded_rect(size: tuple[int, int], radius: int, fill: tuple[int, ...]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill)
    return img


def _pdf_badge(size: int) -> Image.Image:
    """Small document + PDF mark for corner badge."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # soft shadow
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    m = max(2, s // 16)
    sd.rounded_rectangle((m, m + 1, s - m // 2, s - m // 2), radius=s // 6, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, s // 24)))
    img = Image.alpha_composite(img, shadow)
    d = ImageDraw.Draw(img)

    # page body
    left, top = s * 0.12, s * 0.08
    right, bottom = s * 0.88, s * 0.92
    page = [left, top, right, bottom]
    d.rounded_rectangle(page, radius=max(2, s // 10), fill=WHITE, outline=TEAL_DEEP, width=max(1, s // 28))

    # folded corner
    fold = s * 0.28
    d.polygon(
        [
            (right - fold, top),
            (right, top + fold),
            (right - fold, top + fold),
        ],
        fill=SOFT,
        outline=TEAL_DEEP,
    )
    d.line([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=TEAL_DEEP, width=max(1, s // 36))

    # text lines on page
    line_color = (180, 200, 198, 255)
    y0 = top + s * 0.38
    for i in range(3):
        y = y0 + i * s * 0.12
        x1 = left + s * 0.14
        x2 = right - s * 0.14 - (0 if i < 2 else s * 0.12)
        d.rounded_rectangle((x1, y, x2, y + max(2, s * 0.045)), radius=1, fill=line_color)

    # red PDF pill
    pill_h = max(10, int(s * 0.28))
    pill_w = max(18, int(s * 0.72))
    px = (s - pill_w) // 2
    py = int(s * 0.58)
    d.rounded_rectangle((px, py, px + pill_w, py + pill_h), radius=pill_h // 3, fill=PDF_RED)
    # slight depth
    d.rounded_rectangle(
        (px, py, px + pill_w, py + pill_h),
        radius=pill_h // 3,
        outline=PDF_RED_DARK,
        width=max(1, s // 40),
    )

    font = _font(max(8, int(s * 0.18)), bold=True)
    label = "PDF"
    bbox = d.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = px + (pill_w - tw) / 2
    ty = py + (pill_h - th) / 2 - max(1, s // 48)
    d.text((tx, ty), label, font=font, fill=WHITE)
    return img


def make_icon(base_path: Path, out_png: Path, canvas: int = 1024) -> Image.Image:
    base = Image.open(base_path).convert("RGBA")
    base = _trim_alpha(base, pad=2)

    # Fit mark into upper-left area, leave room for PDF badge
    icon = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))

    # subtle rounded plate (app-icon friendly)
    plate = _rounded_rect((canvas, canvas), radius=canvas // 5, fill=(14, 18, 24, 255))
    # inner glow ring
    ring = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    inset = canvas // 28
    rd.rounded_rectangle(
        (inset, inset, canvas - inset - 1, canvas - inset - 1),
        radius=canvas // 5 - inset // 2,
        outline=(*TEAL[:3], 70),
        width=max(2, canvas // 64),
    )
    icon = Image.alpha_composite(plate, ring)

    # main mark ~62% of canvas, slightly up-left
    mark_size = int(canvas * 0.62)
    mark = base.copy()
    mark.thumbnail((mark_size, mark_size), Image.Resampling.LANCZOS)
    mx = int(canvas * 0.12)
    my = int(canvas * 0.10)
    icon.paste(mark, (mx, my), mark)

    # PDF badge bottom-right
    badge = _pdf_badge(int(canvas * 0.42))
    bx = canvas - badge.width - int(canvas * 0.06)
    by = canvas - badge.height - int(canvas * 0.06)
    icon.paste(badge, (bx, by), badge)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    icon.save(out_png, "PNG")
    print(f"wrote {out_png} {icon.size}")
    return icon


def make_logo(logo_path: Path, out_png: Path, height: int = 512) -> Image.Image:
    logo = Image.open(logo_path).convert("RGBA")
    logo = _trim_alpha(logo, pad=4)

    # scale logo to target height
    scale = height / logo.height
    new_w = max(1, int(logo.width * scale))
    logo_r = logo.resize((new_w, height), Image.Resampling.LANCZOS)

    badge_h = int(height * 0.72)
    badge = _pdf_badge(badge_h)

    gap = int(height * 0.10)
    # wordmark "PDF" after logo as clean type, plus badge
    font = _font(int(height * 0.42), bold=True)
    tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    tb = td.textbbox((0, 0), "PDF", font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]

    pad_x = int(height * 0.12)
    pad_y = int(height * 0.14)
    total_w = pad_x + logo_r.width + gap + tw + gap + badge.width + pad_x
    total_h = height + pad_y * 2

    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    # optional dark plate for preview readability
    plate = _rounded_rect((total_w, total_h), radius=total_h // 6, fill=(14, 18, 24, 255))
    canvas = Image.alpha_composite(canvas, plate)

    x = pad_x
    y_logo = (total_h - logo_r.height) // 2
    canvas.paste(logo_r, (x, y_logo), logo_r)
    x += logo_r.width + gap

    d = ImageDraw.Draw(canvas)
    # teal "PDF" word
    ty = (total_h - th) // 2 - max(1, height // 40)
    # slight outline for punch
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((x + ox, ty + oy), "PDF", font=font, fill=TEAL_DEEP)
    d.text((x, ty), "PDF", font=font, fill=TEAL)
    x += tw + gap

    by = (total_h - badge.height) // 2
    canvas.paste(badge, (x, by), badge)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png, "PNG")
    print(f"wrote {out_png} {canvas.size}")
    return canvas


def make_logo_transparent(logo_path: Path, out_png: Path, height: int = 512) -> Image.Image:
    """Horizontal lockup without dark plate — for light/dark UI chrome."""
    logo = Image.open(logo_path).convert("RGBA")
    logo = _trim_alpha(logo, pad=4)
    scale = height / logo.height
    logo_r = logo.resize((max(1, int(logo.width * scale)), height), Image.Resampling.LANCZOS)
    badge = _pdf_badge(int(height * 0.78))
    font = _font(int(height * 0.44), bold=True)
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    tb = d0.textbbox((0, 0), "PDF", font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    gap = int(height * 0.08)
    total_w = logo_r.width + gap + tw + gap + badge.width
    total_h = max(logo_r.height, badge.height, th) + 8
    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y_logo = (total_h - logo_r.height) // 2
    canvas.paste(logo_r, (0, y_logo), logo_r)
    x = logo_r.width + gap
    d = ImageDraw.Draw(canvas)
    ty = (total_h - th) // 2 - 2
    d.text((x, ty), "PDF", font=font, fill=TEAL)
    x += tw + gap
    canvas.paste(badge, (x, (total_h - badge.height) // 2), badge)
    canvas.save(out_png, "PNG")
    print(f"wrote {out_png} {canvas.size}")
    return canvas


def write_ico(png_img: Image.Image, ico_path: Path, sizes: list[int] | None = None) -> None:
    sizes = sizes or [16, 24, 32, 48, 64, 128, 256]
    # Build multi-size ICO manually for broad Windows support
    frames: list[bytes] = []
    entries: list[tuple[int, int, int, bytes]] = []  # w, h, bpp_placeholder, png_bytes

    for s in sizes:
        frame = png_img.resize((s, s), Image.Resampling.LANCZOS)
        # store as PNG-compressed ICO image (Vista+)
        import io

        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        data = buf.getvalue()
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        entries.append((w, h, len(data), data))

    # ICONDIR + ICONDIRENTRY*n + image data
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    dir_entries = b""
    payload = b""
    for w, h, size, data in entries:
        dir_entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, offset)
        payload += data
        offset += size

    ico_path.write_bytes(header + dir_entries + payload)
    print(f"wrote {ico_path} ({ico_path.stat().st_size} bytes, {len(entries)} sizes)")


def export_sizes(icon: Image.Image, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for s in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        p = folder / f"icon_{s}.png"
        icon.resize((s, s), Image.Resampling.LANCZOS).save(p, "PNG")
    print(f"wrote size pack -> {folder}")


def main() -> None:
    refs = copy_refs()
    if "icon" not in refs and "icon_dark" not in refs:
        raise SystemExit("No Remedy icon reference found")
    if "logo" not in refs and "logo_dark" not in refs:
        raise SystemExit("No Remedy logo reference found")

    icon_src = refs.get("icon") or refs.get("icon_dark")
    logo_src = refs.get("logo") or refs.get("logo_dark")

    # Primary app icon (used by app + installer)
    icon = make_icon(icon_src, OUT / "icon.png", canvas=1024)
    write_ico(icon, OUT / "icon.ico")
    export_sizes(icon, OUT / "icons")

    # Also keep a light-friendly transparent mark (no plate) for in-app chrome
    mark = Image.open(icon_src).convert("RGBA")
    mark = _trim_alpha(mark)
    badge = _pdf_badge(int(max(mark.size) * 0.55))
    # composite mark + badge on transparent square
    side = max(mark.width, mark.height)
    canvas_s = int(side * 1.25)
    ticon = Image.new("RGBA", (canvas_s, canvas_s), (0, 0, 0, 0))
    m = mark.copy()
    m.thumbnail((int(canvas_s * 0.7), int(canvas_s * 0.7)), Image.Resampling.LANCZOS)
    ticon.paste(m, (int(canvas_s * 0.08), int(canvas_s * 0.06)), m)
    b = badge.resize((int(canvas_s * 0.42), int(canvas_s * 0.42)), Image.Resampling.LANCZOS)
    ticon.paste(b, (canvas_s - b.width - int(canvas_s * 0.04), canvas_s - b.height - int(canvas_s * 0.04)), b)
    ticon.save(OUT / "icon_transparent.png", "PNG")
    print(f"wrote {OUT / 'icon_transparent.png'} {ticon.size}")

    # Logos
    make_logo(logo_src, OUT / "logo.png", height=512)
    make_logo_transparent(logo_src, OUT / "logo_transparent.png", height=512)
    # smaller UI logo
    make_logo_transparent(logo_src, OUT / "logo_ui.png", height=128)

    # Preview sheet
    sheet_w, sheet_h = 1400, 800
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (24, 28, 34, 255))
    d = ImageDraw.Draw(sheet)
    title_font = _font(36, bold=True)
    d.text((40, 30), "RemedyPDF brand assets", font=title_font, fill=WHITE)
    # place icon
    ic = icon.resize((320, 320), Image.Resampling.LANCZOS)
    sheet.paste(ic, (60, 120), ic)
    d.text((60, 460), "icon.png / icon.ico", font=_font(22), fill=SOFT)
    # place logo
    lg = Image.open(OUT / "logo.png").convert("RGBA")
    lg.thumbnail((900, 280), Image.Resampling.LANCZOS)
    sheet.paste(lg, (420, 160), lg)
    d.text((420, 460), "logo.png", font=_font(22), fill=SOFT)
    lt = Image.open(OUT / "logo_transparent.png").convert("RGBA")
    lt.thumbnail((900, 160), Image.Resampling.LANCZOS)
    # light strip behind transparent logo
    d.rounded_rectangle((420, 520, 420 + 920, 520 + 200), radius=16, fill=(245, 248, 250, 255))
    sheet.paste(lt, (450, 560), lt)
    d.text((450, 700), "logo_transparent.png (on light)", font=_font(20), fill=INK)
    sheet_path = OUT / "brand_preview.png"
    sheet.convert("RGB").save(sheet_path, "PNG")
    print(f"wrote {sheet_path}")
    print("DONE")


if __name__ == "__main__":
    main()
