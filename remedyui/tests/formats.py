"""Cross-check images, TIFF, comics and SVG against PyMuPDF, and export to PDF.
Run from remedyui/: python tests/formats.py"""
import io, pathlib, shutil, subprocess, tempfile, zipfile
import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageStat

subprocess.run(["cargo", "build", "-q", "--example", "check"], check=True)
EXE = next(p for p in pathlib.Path("target/debug/examples").glob("check*") if p.suffix in ("", ".exe"))


def art(w, h, shade=0, mode="RGB"):
    """Asymmetric, so a flip, turn, stretch or wrong page shows."""
    im = Image.new("RGB", (w, h), (240, 240 - shade, 240))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w // 2, h // 3), fill=(200, 30, 30 + shade))
    d.ellipse((w // 2, h // 2, w - 2, h - 2), fill=(30, 60 + shade, 200))
    return im.convert(mode)


def encoded(im, kind, **kw):
    out = io.BytesIO()
    im.save(out, kind, **kw)
    return out.getvalue()


def pages(path, out):
    """Our pages: [(width_pt, height_pt, picture at 1 px per point)]."""
    run = subprocess.run([str(EXE), "pages", str(path), "-", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr.strip()
    result = []
    for n, line in enumerate(run.stdout.split("\n")[:-1]):
        w, h, pw, ph = line.split()
        raw = pathlib.Path(f"{out}.{n}").read_bytes()
        result.append((float(w), float(h), Image.frombytes("RGBA", (int(pw), int(ph)), raw).convert("RGB")))
    return result


def same(ours, path, limit=4.0):
    with pymupdf.open(path) as doc:
        assert len(ours) == len(doc), f"{len(ours)} pages, MuPDF has {len(doc)}"
        for n, ((w, h, picture), page) in enumerate(zip(ours, doc)):
            assert abs(w - page.rect.width) < 0.6 and abs(h - page.rect.height) < 0.6, \
                f"page {n} is {w}x{h}, MuPDF says {page.rect.width}x{page.rect.height}"
            pix = page.get_pixmap(alpha=False)
            theirs = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            small = (max(1, picture.width // 4), max(1, picture.height // 4))
            diff = ImageChops.difference(picture.resize(small, Image.BOX), theirs.resize(small, Image.BOX))
            mean = sum(ImageStat.Stat(diff).mean) / 3
            assert mean < limit, f"page {n} drawn differently (mean {mean:.1f})"


def make(d):
    base = art(600, 900)
    rotated = Image.Exif()
    rotated[274] = 6
    files = {
        "plain.png": encoded(base, "PNG"),
        "dpi300.png": encoded(base, "PNG", dpi=(300, 300)),
        "photo.jpg": encoded(base, "JPEG", quality=95, dpi=(72, 72)),
        "turned.jpg": encoded(base, "JPEG", quality=95, exif=rotated),
        "pic.bmp": encoded(base, "BMP", dpi=(150, 150)),
        "pic.webp": encoded(base, "WEBP", lossless=True),
        "clear.png": encoded(art(300, 200, mode="RGBA").point(lambda v: v if v < 255 else 128), "PNG"),
        "move.gif": encoded(base, "GIF", save_all=True, append_images=[art(600, 900, 90)]),
        "scan.tif": encoded(base, "TIFF", save_all=True, append_images=[art(300, 300, 50), art(500, 250, 120)]),
        "fine.tif": encoded(base, "TIFF", dpi=(200, 200), compression="tiff_lzw"),
        "box.svg": b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="80" height="60" fill="red"/><circle cx="150" cy="50" r="40" fill="blue"/></svg>',
        "viewbox.svg": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><path d="M0 0H200V100Z" fill="green"/></svg>',
    }
    for name, data in files.items():
        (d / name).write_bytes(data)
    names = ["p10.png", "p2.png", "p1.png", "sub/p0.png", "A.png", ".hidden.png"]
    with zipfile.ZipFile(d / "comic.cbz", "w", zipfile.ZIP_DEFLATED) as z:
        for i, name in enumerate(names):
            z.writestr(name, encoded(art(200 + 20 * i, 300, 25 * i), "PNG"))
        z.writestr("notes.txt", "not a page")
    shutil.copy(d / "comic.cbz", d / "zipped.cbr")  # many .cbr files are zips
    return [*files, "comic.cbz", "zipped.cbr"]


failed = 0
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
    d = pathlib.Path(d)
    for name in make(d):
        try:
            ours = pages(d / name, d / "raw")
            if name in ("pic.webp", "move.gif"):
                # 1.x cannot open WebP and shows a GIF's last frame; we show its first, as image
                # viewers do. Pillow is the reference for both.
                (w, h, picture), = ours
                with Image.open(d / name) as im:
                    assert (round(w), round(h)) == (450, 675), f"{w}x{h}"
                    ref = im.convert("RGB").resize(picture.size, Image.BOX)
                mean = sum(ImageStat.Stat(ImageChops.difference(picture, ref)).mean) / 3
                assert mean < 4, f"drawn differently (mean {mean:.1f})"
            else:
                # MuPDF reads a zip named .cbr only by its contents; compare through the .cbz.
                same(ours, d / ("comic.cbz" if name == "zipped.cbr" else name))
            exported = d / "exported.pdf"
            run = subprocess.run([str(EXE), "export", str(d / name), "-", str(exported)], capture_output=True, text=True)
            assert run.returncode == 0, run.stderr.strip()
            with pymupdf.open(exported) as doc:
                assert len(doc) == len(ours), "export lost pages"
                for (w, h, picture), page in zip(ours, doc):
                    assert abs(page.rect.width - w) < 0.1 and abs(page.rect.height - h) < 0.1, "export changed the page size"
                    pix = page.get_pixmap(alpha=False)
                    got = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).resize(picture.size, Image.BOX)
                    mean = sum(ImageStat.Stat(ImageChops.difference(got, picture)).mean) / 3
                    assert mean < 4, f"export looks different (mean {mean:.1f})"
            print("ok  ", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, e)
    # Real RAR comics, made by WinRAR where it is installed.
    rar = pathlib.Path("C:/Program Files/WinRAR/Rar.exe")
    if not rar.exists():
        print("SKIP real RAR comics: WinRAR is not installed")
    else:
        tree = d / "tree"
        with zipfile.ZipFile(d / "comic.cbz") as z:
            z.extractall(tree)

        def raw_pages(archive, password, expect=0):
            run = subprocess.run([str(EXE), "pages", str(archive), password, str(d / "raw")],
                                 capture_output=True, text=True, encoding="utf-8")
            assert run.returncode == expect, f"password {password!r} exited {run.returncode}: {run.stderr}"
            return [(line.split()[2:], (d / f"raw.{n}").read_bytes())
                    for n, line in enumerate(run.stdout.splitlines())]

        want = raw_pages(d / "comic.cbz", "-")
        kinds = {"normal": [], "solid": ["-s"], "best-solid": ["-s", "-m5"], "stored": ["-m0"],
                 "locked": ["-psecret"], "locked-names": ["-hpsecret"],
                 "rar4": ["-ma4"], "rar4-solid": ["-ma4", "-s", "-m5"], "locked-rar4": ["-ma4", "-psecret"],
                 "locked-names-rar4": ["-ma4", "-hpsecret"]}
        for kind, switches in kinds.items():
            try:
                archive = d / f"{kind}.cbr"
                subprocess.run([str(rar), "a", "-r", "-idq", *switches, str(archive), "*"], cwd=tree, check=True)
                password = "-"
                if kind.startswith("locked"):
                    password = "secret"
                    for wrong in ("-", "wrong"):
                        raw_pages(archive, wrong, expect=3)
                assert raw_pages(archive, password) == want, "pages differ from the same comic as a zip"
                print("ok   rar", kind)
            except Exception as e:
                failed += 1
                print("FAIL rar", kind, e)
    junk = d / "broken.cbr"
    junk.write_bytes(b"Rar!\x1a\x07\x01\x00" + b"\xff" * 200)
    run = subprocess.run([str(EXE), "pages", str(junk), "-", str(d / "raw")], capture_output=True, text=True)
    ok = run.returncode != 0 and "panicked" not in run.stderr
    print("ok   broken.cbr is an error" if ok else f"FAIL broken.cbr {run.stderr}")
    failed += not ok
raise SystemExit(f"{failed} failed" if failed else 0)
