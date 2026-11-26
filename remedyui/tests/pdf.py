"""Cross-check PDF viewing, editing and saving against PyMuPDF (a test reference, never shipped).
Run from remedyui/: python tests/pdf.py"""
import pathlib, subprocess, tempfile
import pymupdf
from PIL import Image, ImageChops, ImageStat

subprocess.run(["cargo", "build", "-q", "--example", "check"], check=True)
EXE = next(p for p in pathlib.Path("target/debug/examples").glob("check*") if p.suffix in ("", ".exe"))
SCALE = 1.5
PERMS = pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY


def check(*args, expect=0):
    run = subprocess.run([str(EXE), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == expect, f"{args[0]} exited {run.returncode}: {run.stderr.strip()}"
    return run.stdout


def make(path, rotate, crop, password, form):
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=700)
    page.insert_text((90, 110), "Quarterly report", fontsize=22)
    page.insert_text((90, 600), "Footer line", fontsize=11)
    page.draw_rect(pymupdf.Rect(330, 520, 430, 640), color=(0, 0.5, 0), fill=(0.6, 0.9, 0.6))
    if form:
        w = pymupdf.Widget()
        w.field_type, w.field_name, w.field_value = pymupdf.PDF_WIDGET_TYPE_TEXT, "name", "Filled in field"
        w.rect = pymupdf.Rect(90, 140, 300, 165)
        page.add_widget(w)
    if crop:
        page.set_cropbox(pymupdf.Rect(30, 40, 480, 660))
    page.set_rotation(rotate)
    extra = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password,
                 permissions=PERMS) if password else {}
    doc.save(path, **extra)
    doc.close()


def opened(path, password):
    doc = pymupdf.open(path)
    if password:
        assert doc.needs_pass and doc.authenticate(password), "not protected with the password"
    else:
        assert not doc.needs_pass
    return doc


def shown(page, rect):
    """A PyMuPDF rectangle (unrotated page space) as displayed."""
    return (rect * page.rotation_matrix).normalize()


def drawn_like_mupdf(path, password, raw, w, h):
    ours = Image.frombytes("RGBA", (w, h), raw.read_bytes()).convert("RGB")
    with opened(path, password) as doc:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), alpha=False)
    theirs = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    assert abs(pix.width - w) <= 1 and abs(pix.height - h) <= 1, f"size {w}x{h} vs {pix.width}x{pix.height}"
    # Antialiasing differs between the libraries: compare a quarter-size picture.
    small = (w // 4, h // 4)
    diff = ImageChops.difference(ours.resize(small, Image.BOX), theirs.resize(small, Image.BOX))
    mean = sum(ImageStat.Stat(diff).mean) / 3
    bad = sum(1 for p in diff.getdata() if max(p) > 80) / (small[0] * small[1])
    assert mean < 3 and bad < 0.005, f"drawn differently: mean {mean:.2f}, {bad:.2%} far off"
    return ours


def dump(path, password, raw):
    lines = check("dump", path, password or "-", SCALE, raw).splitlines()
    w, h, differing = map(int, lines[0].split())
    assert differing <= w * h * 4 // 2000, f"a tile differs from the whole page in {differing} bytes"
    runs = [(tuple(map(float, box.split())), text) for box, text in (l.split("\t", 1) for l in lines[1:])]
    return w, h, runs


def found(runs, page, needle):
    """Our run holding `needle` sits where PyMuPDF finds it."""
    run = next((box for box, text in runs if needle in text), None)
    assert run, f"no text run holds {needle!r}: {[t for _, t in runs]}"
    ref = shown(page, page.search_for(needle)[0])
    ours = pymupdf.Rect(run)
    overlap = pymupdf.Rect(ours) & ref
    assert overlap.get_area() > 0.5 * min(ours.get_area(), ref.get_area()), f"{needle!r} at {ours}, MuPDF says {ref}"


failed = 0
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
    d = pathlib.Path(d)
    picture = d / "picture.png"  # 2:1, red left, blue right: shows flips, turns and stretching
    art = Image.new("RGB", (80, 40), (220, 20, 20))
    art.paste((20, 20, 220), (40, 0, 80, 40))
    art.save(picture)
    cases = [(r, c, p, False) for r in (0, 90, 180, 270) for c in (False, True) for p in (None, "pässwörd ✓")]
    cases += [(0, False, None, True), (90, False, "secret", True)]
    for rotate, crop, password, form in cases:
        name = f"rot{rotate}{'-crop' if crop else ''}{'-locked' if password else ''}{'-form' if form else ''}"
        source, saved, raw = d / f"{name}.pdf", d / f"{name}-out.pdf", d / f"{name}.rgba"
        try:
            make(source, rotate, crop, password, form)
            original = source.read_bytes()
            if password:
                check("dump", source, "-", SCALE, raw, expect=3)
                check("dump", source, "wrong", SCALE, raw, expect=3)
            w, h, runs = dump(source, password, raw)
            drawn_like_mupdf(source, password, raw, w, h)
            with opened(source, password) as doc:
                for needle in ("Quarterly", "Footer"):
                    found(runs, doc[0], needle)

            check("edit", source, password or "-", saved, picture)
            assert source.read_bytes() == original, "the source file changed"
            with opened(saved, password) as doc:
                page = doc[0]
                if password:
                    assert "256-bit AES" in doc.metadata["encryption"]
                    with opened(source, password) as before:
                        assert doc.permissions == before.permissions, "permissions changed"
                    assert b"Added by Remedy" not in saved.read_bytes()
                assert page.rotation == rotate
                for needle in ("Quarterly report", "Footer line", "Added by Remedy"):
                    assert page.search_for(needle), f"lost {needle!r}"
                if form:
                    assert [x.field_value for x in page.widgets()] == ["Filled in field"], "form field lost"
                # The new text reads left to right on screen, with its baseline at (72, 200).
                line = next(l for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                            if "Added by Remedy" in "".join(s["text"] for s in l["spans"]))
                m = page.rotation_matrix
                direction = pymupdf.Point(line["dir"]) * pymupdf.Matrix(m.a, m.b, m.c, m.d, 0, 0)
                assert abs(direction.x - 1) < 0.01 and abs(direction.y) < 0.01, f"text runs {direction}"
                origin = pymupdf.Point(line["spans"][0]["origin"]) * m
                assert abs(origin.x - 72) < 0.5 and abs(origin.y - 200) < 0.5, f"baseline at {origin}"
                # 2:1 picture fitted and centred in (72,250)-(272,450).
                placed = shown(page, page.get_image_rects(page.get_images()[0][0])[0])
                want = pymupdf.Rect(72, 300, 272, 400)
                assert all(abs(a - b) < 0.5 for a, b in zip(placed, want)), f"picture at {placed}"
            w, h, runs = dump(saved, password, raw)
            ours = drawn_like_mupdf(saved, password, raw, w, h)
            for x, colour in ((97, (220, 20, 20)), (247, (20, 20, 220))):
                got = ours.getpixel((int(x * SCALE), int(350 * SCALE)))
                assert all(abs(a - b) < 12 for a, b in zip(got, colour)), f"picture pixel {got} at x={x}"
            with opened(saved, password) as doc:
                found(runs, doc[0], "Added")
            assert not [f for f in d.iterdir() if f.suffix not in (".pdf", ".png", ".rgba")], "temp file left"
            print("ok  ", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, e)
raise SystemExit(f"{failed} failed" if failed else 0)
