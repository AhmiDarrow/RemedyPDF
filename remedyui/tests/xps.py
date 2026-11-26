"""Cross-check XPS against PyMuPDF with a file made by Windows' own XPS writer.
Run from remedyui/: python tests/xps.py [folder-to-keep-page-pictures-in]"""
import pathlib, subprocess, sys, tempfile, zipfile
import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageStat

subprocess.run(["cargo", "build", "-q", "--example", "check"], check=True)
EXE = next(p for p in pathlib.Path("target/debug/examples").glob("check*") if p.suffix in ("", ".exe"))
KEEP = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
SCRIPT = pathlib.Path(__file__).with_name("make_xps.ps1").resolve()


def ours(path, folder):
    prefix = folder / "raw"
    run = subprocess.run([str(EXE), "pages", str(path), "-", str(prefix)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr.strip()
    pages = []
    for n, line in enumerate(run.stdout.splitlines()):
        w, h, pw, ph = line.split()
        image = Image.frombytes("RGBA", (int(pw), int(ph)), pathlib.Path(f"{prefix}.{n}").read_bytes()).convert("RGB")
        runs = []
        for entry in pathlib.Path(f"{prefix}.{n}.txt").read_text(encoding="utf-8").splitlines():
            box, text = entry.split("\t", 1)
            runs.append((tuple(map(float, box.split())), text))
        pages.append((float(w), float(h), image, runs))
    return pages


failed = 0
if sys.platform != "win32":
    raise SystemExit("SKIP: the XPS fixture needs Windows")
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
    d = pathlib.Path(d)
    art = Image.new("RGB", (160, 80), (240, 240, 200))
    pen = ImageDraw.Draw(art)
    pen.rectangle((4, 4, 70, 76), fill=(200, 30, 30))
    pen.ellipse((90, 4, 156, 76), fill=(30, 60, 200))
    art.save(d / "art.png")
    source = d / "real.xps"
    subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                    str(source), str(d / "art.png")], check=True)
    try:
        with zipfile.ZipFile(source) as z:
            assert any(n.lower().endswith(".odttf") for n in z.namelist()), "the fixture has no scrambled font"
        pages = ours(source, d)
        with pymupdf.open(source) as doc:
            assert len(pages) == len(doc) == 3, f"{len(pages)} pages, MuPDF has {len(doc)}"
            for n, ((w, h, picture, runs), page) in enumerate(zip(pages, doc)):
                assert abs(w - page.rect.width) < 0.6 and abs(h - page.rect.height) < 0.6, f"size {w}x{h}"
                pix = page.get_pixmap(alpha=False)
                theirs = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                if KEEP:
                    picture.save(KEEP / f"ours{n}.png")
                    theirs.save(KEEP / f"mupdf{n}.png")
                small = (picture.width // 4, picture.height // 4)
                diff = ImageChops.difference(picture.resize(small, Image.BOX), theirs.resize(small, Image.BOX))
                mean = sum(ImageStat.Stat(diff).mean) / 3
                bad = sum(1 for p in diff.getdata() if max(p) > 80) / (small[0] * small[1])
                print(f"     page {n + 1}: mean difference {mean:.2f}, {bad:.2%} of it far off")
                assert mean < 4 and bad < 0.012, f"page {n} drawn differently"
                # Each word MuPDF reads is in our text, at the same place.
                for x0, y0, x1, y1, word, *_ in page.get_text("words"):
                    if not word.isascii():
                        continue
                    middle = ((x0 + x1) / 2, (y0 + y1) / 2)
                    hit = any(word in text and a - 2 <= middle[0] <= c + 2 and b - 2 <= middle[1] <= e + 2
                              for (a, b, c, e), text in runs)
                    assert hit, f"{word!r} missing near {middle}; have {[t for _, t in runs]}"
        run = subprocess.run([str(EXE), "export", str(source), "-", str(d / "out.pdf")], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr.strip()
        with pymupdf.open(d / "out.pdf") as doc:
            assert len(doc) == 3
        print("ok   real.xps")
        # The same package stored in interleaved pieces reads the same.
        with zipfile.ZipFile(source) as z, zipfile.ZipFile(d / "pieces.oxps", "w") as out:
            for name in z.namelist():
                data = z.read(name)
                if name.endswith(".fpage"):
                    half = len(data) // 2
                    out.writestr(f"{name}/[0].piece", data[:half])
                    out.writestr(f"{name}/[1].last.piece", data[half:])
                else:
                    out.writestr(name, data)
        again = ours(d / "pieces.oxps", d)
        assert [p[2].tobytes() for p in again] == [p[2].tobytes() for p in pages], "pieces read differently"
        print("ok   pieces.oxps")
    except Exception as e:
        failed += 1
        print("FAIL", e)
    for name, data in {"bad.xps": b"PK\x03\x04junk", "bad.oxps": b"junk"}.items():
        (d / name).write_bytes(data)
        run = subprocess.run([str(EXE), "pages", str(d / name), "-", str(d / "raw")], capture_output=True, text=True)
        good = run.returncode == 1 and "panicked" not in run.stderr
        print(f"ok   {name} is an error" if good else f"FAIL {name} {run.returncode} {run.stderr[-300:]}")
        failed += not good
raise SystemExit(f"{failed} failed" if failed else 0)
