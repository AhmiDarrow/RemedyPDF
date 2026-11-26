"""Cross-check TXT, HTML, EPUB, FB2, MOBI and DOCX against PyMuPDF.
Layout differs by design (other fonts and line breaking), so the test is that nothing is lost:
the same words in the same order, a similar number of pages, and all text on its page.
Run from remedyui/: python tests/reflow.py [folder-to-keep-page-pictures-in]"""
import base64, io, pathlib, re, struct, subprocess, sys, tempfile, zipfile
import pymupdf
from PIL import Image, ImageDraw

subprocess.run(["cargo", "build", "-q", "--example", "check"], check=True)
EXE = next(p for p in pathlib.Path("target/debug/examples").glob("check*") if p.suffix in ("", ".exe"))
KEEP = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None

LOREM = ("Reading should stay comfortable on every screen, and each word must arrive in order. "
         "Numbers like 1234 and names like Zoë, naïve café and Привет matter too. ")


def picture():
    im = Image.new("RGB", (240, 120), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.rectangle((10, 10, 110, 110), fill=(200, 30, 30))
    d.ellipse((130, 10, 230, 110), fill=(30, 60, 200))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def chapter(n):
    paragraphs = "".join(f"<p>Chapter {n} paragraph {i}. {LOREM * 2}</p>" for i in range(14))
    return f"<h1>Chapter {n}</h1>{paragraphs}"


BODY = ("<h1>The Title</h1><p>Plain, <b>bold</b>, <i>italic</i> and <code>code()</code> words.</p>"
        "<p style='text-align:center'>Centred line</p><ul><li>first item</li><li>second item</li></ul>"
        "<ol><li>one thing</li><li>another thing</li></ol><blockquote>Quoted words here.</blockquote>"
        "<table border='1'><tr><th>Name</th><th>Count</th></tr><tr><td>apples</td><td>12</td></tr>"
        "<tr><td>pears and a much longer description that wraps inside its cell</td><td>7</td></tr></table>"
        "<pre>line one\n    line two indented</pre>")


def epub(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        ids = "".join(f'<item id="c{i}" href="text/c{i}.xhtml" media-type="application/xhtml+xml"/>' for i in (1, 2))
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="u">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>T</dc:title><dc:identifier id="u">x</dc:identifier></metadata>'
                   f'<manifest>{ids}<item id="p" href="img/p.png" media-type="image/png"/><item id="s" href="s.css" media-type="text/css"/></manifest>'
                   '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
        z.writestr("OEBPS/s.css", ".hidden { display: none } /* x { */ h1 { text-align: center }")
        z.writestr("OEBPS/img/p.png", picture())
        for i in (1, 2):
            z.writestr(f"OEBPS/text/c{i}.xhtml",
                       '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title/>'
                       '<link rel="stylesheet" href="../s.css"/></head><body>'
                       f'<a id="top"/>{chapter(i)}<img src="../img/p.png" alt="art"/><p class="hidden">SECRET</p></body></html>')


def fb2(path):
    sections = "".join(
        f"<section><title><p>Part {n}</p></title>" +
        "".join(f"<p>Part {n} paragraph {i} with <emphasis>stress</emphasis> and <strong>weight</strong>. {LOREM * 2}</p>" for i in range(10)) +
        '<image l:href="#p.png"/></section>' for n in (1, 2))
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" '
        'xmlns:l="http://www.w3.org/1999/xlink"><description><title-info><book-title>B</book-title></title-info></description>'
        f'<body>{sections}</body><binary id="p.png" content-type="image/png">{base64.b64encode(picture()).decode()}</binary></FictionBook>',
        encoding="utf-8")


def palmdoc(data):
    """PalmDoc compression using every kind of token."""
    out, at = bytearray(), 0
    while at < len(data):
        best = 0
        for back in range(1, min(at, 2047) + 1):
            n = 0
            while n < 10 and at + n < len(data) and data[at + n] == data[at - back + n]:
                n += 1
            if n > best:
                best, distance = n, back
                if n == 10:
                    break
        if best >= 3:
            out += struct.pack(">H", 0x8000 | distance << 3 | best - 3)
            at += best
        elif data[at] == 32 and at + 1 < len(data) and 0x40 <= data[at + 1] <= 0x7f:
            out.append(data[at + 1] ^ 0x80)
            at += 2
        elif data[at] == 0 or 9 <= data[at] <= 0x7f:
            out.append(data[at])
            at += 1
        else:
            n = 1
            while n < 8 and at + n < len(data) and data[at + n] >= 0x80:
                n += 1
            out.append(n)
            out += data[at:at + n]
            at += n
    return bytes(out)


SHORT, LONG = 1, b"Record paragraph "


def huffman_tables():
    table = struct.pack(">I", 255 << 8 | 0x80 | 8) * 256
    huff = b"HUFF" + struct.pack(">IIIII", 24, 24, 24 + 1024, 0, 0) + table + bytes(256)
    entries = []
    for index in range(256):
        byte = 255 - index
        coded = byte == SHORT
        phrase = LONG if coded else bytes([byte])
        entries.append(struct.pack(">H", len(phrase) | (0 if coded else 0x8000)) + phrase)
    at, offsets = 512, []
    for entry in entries:
        offsets.append(at)
        at += len(entry)
    cdic = b"CDIC" + struct.pack(">III", 16, 256, 8) + struct.pack(">256H", *offsets) + b"".join(entries)
    return [huff, cdic]


def mobi(path, compression=1, flags=0):
    """A minimal MOBI: PalmDB, a MOBI header, several text records, one picture."""
    html = ("<html><body><h1>Mobi Book</h1>" + "".join(f"<p>Record paragraph {i}. {LOREM}</p>" for i in range(12)) +
            '<mbp:pagebreak/><p>After the break.</p><img recindex="00001"/></body></html>').encode()
    chunks = [html[i:i + 1500] for i in range(0, len(html), 1500)]
    count = len(chunks)
    if compression == 2:
        chunks = [palmdoc(c) for c in chunks]
    if compression == 0x4448:
        chunks = [c.replace(LONG, bytes([SHORT])) for c in chunks]
    if flags:
        # One index entry (bit 1), ending with its own length, then the overlap byte (bit 0).
        chunks = [c + b"\x00" + b"junk" + bytes([0x80 | 5]) for c in chunks]
    title = b"Test"
    header = bytearray(232)
    header[0:4] = b"MOBI"
    first_image = 1 + len(chunks)
    fields = {4: 232, 8: 2, 12: 65001, 16: 1, 20: 6, 64: first_image, 68: 16 + 232, 72: len(title), 76: 9,
              88: 6, 92: first_image}
    for at in range(24, 64, 4):
        struct.pack_into(">I", header, at, 0xFFFFFFFF)
    for at, value in fields.items():
        struct.pack_into(">I", header, at, value)
    struct.pack_into(">HH", header, 176, 1, len(chunks))
    struct.pack_into(">I", header, 224, 0xFFFFFFFF)
    struct.pack_into(">H", header, 242 - 16, flags)
    start = struct.pack(">HHIHHHH", compression, 0, len(html), count, 4096, 0, 0)
    tables = huffman_tables() if compression == 0x4448 else []
    if tables:
        struct.pack_into(">II", header, 96, 1 + len(chunks) + 1, len(tables))
    records = [start + bytes(header) + title + b"\0\0", *chunks, picture(), *tables]
    offset = 78 + 8 * len(records) + 2
    table = b""
    for n, record in enumerate(records):
        table += struct.pack(">II", offset, n * 2)
        offset += len(record)
    db = (b"Test".ljust(32, b"\0") + struct.pack(">HHIIIIII", 0, 0, 0, 0, 0, 0, 0, 0) + b"BOOKMOBI" +
          struct.pack(">IIH", len(records) * 2, 0, len(records)))
    path.write_bytes(db + table + b"\0\0" + b"".join(records))


def docx(path):
    """A Word file written by hand: styles, lists, a table, a picture and a page break."""
    ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
          'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
          'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
          'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')

    def run(text, props=""):
        return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'

    def para(content, props=""):
        return f"<w:p><w:pPr>{props}</w:pPr>{content}</w:p>"

    def item(text, num):
        return para(run(text), f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>')

    rows = "".join("<w:tr>" + "".join(f"<w:tc>{para(run(t))}</w:tc>" for t in row) + "</w:tr>"
                   for row in (("Name", "Count"), ("apples", "12")))
    drawing = ('<w:r><w:drawing><wp:inline><wp:extent cx="1828800" cy="914400"/><wp:docPr id="1" name="p"/><a:graphic>'
               '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
               '<pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rId9"/>'
               '</pic:blipFill><pic:spPr/></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
    body = (para(run("Word Heading"), '<w:pStyle w:val="Heading1"/>') +
            para(run("Plain, ") + run("bold", "<w:b/>") + run(", ") + run("italic", "<w:i/>") + run(" words.")) +
            item("alpha item", 1) + item("beta item", 1) + item("first step", 2) + item("second step", 2) +
            f"<w:tbl>{rows}</w:tbl>" + para(drawing) +
            "".join(para(run(f"Body paragraph {i}. {LOREM * 2}")) for i in range(12)) +
            para('<w:r><w:br w:type="page"/></w:r>') + para(run("On the last page.")))
    levels = "".join(
        f'<w:abstractNum w:abstractNumId="{n}"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="{kind}"/>'
        f'<w:lvlText w:val="{text}"/></w:lvl></w:abstractNum>' for n, kind, text in ((1, "bullet", "o"), (2, "decimal", "%1.")))
    nums = "".join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="{n}"/></w:num>' for n in (1, 2))
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="r1" Type="{rel}/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId9" Type="{rel}/image" Target="media/p.png"/></Relationships>')
        z.writestr("word/document.xml", f"<w:document {ns}><w:body>{body}<w:sectPr/></w:body></w:document>")
        z.writestr("word/styles.xml", f'<w:styles {ns}><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
                   '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style></w:styles>')
        z.writestr("word/numbering.xml", f"<w:numbering {ns}>{levels}{nums}</w:numbering>")
        z.writestr("word/media/p.png", picture())


def ours(path, folder):
    prefix = folder / "raw"
    run = subprocess.run([str(EXE), "pages", str(path), "-", str(prefix)], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr.strip()
    pages = []
    for n, line in enumerate(run.stdout.splitlines()):
        w, h, pw, ph = line.split()
        image = Image.frombytes("RGBA", (int(pw), int(ph)), pathlib.Path(f"{prefix}.{n}").read_bytes())
        runs = []
        for entry in pathlib.Path(f"{prefix}.{n}.txt").read_text(encoding="utf-8").splitlines():
            box, text = entry.split("\t", 1)
            runs.append((tuple(map(float, box.split())), text))
        pages.append((float(w), float(h), image, runs))
    return pages


def words(text):
    # Bullets and list numbers are drawn, not text, in one engine or the other.
    return re.findall(r"[^\W\d_]+|\d{2,}", text)


failed = 0
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
    d = pathlib.Path(d)
    (d / "art.png").write_bytes(picture())
    (d / "plain.txt").write_text("Title line\n\n" + "\n".join(LOREM * 6 for _ in range(14)) + "\n\tindented end\n", encoding="utf-8")
    (d / "page.html").write_text(f"<!DOCTYPE html><html><head><meta charset=utf-8><style>.x{{display:none}}</style><script>var no=1</script></head>"
                                 f"<body>{BODY}<img src='art.png'><div class=x>SECRET</div>{chapter(9)}</body></html>", encoding="utf-8")
    epub(d / "book.epub")
    fb2(d / "story.fb2")
    mobi(d / "kindle.mobi")
    docx(d / "letter.docx")
    mobi(d / "packed.mobi", compression=2, flags=3)
    mobi(d / "huffman.mobi", compression=0x4448)
    for name in ("plain.txt", "page.html", "book.epub", "story.fb2", "kindle.mobi", "packed.mobi", "huffman.mobi", "letter.docx"):
        try:
            pages = ours(d / name, d)
            # MuPDF is not trusted with the trailing data: the same book without it is the reference.
            with pymupdf.open(d / ("kindle.mobi" if name in ("packed.mobi", "huffman.mobi") else name)) as doc:
                # "[image]" is MuPDF's mark for the HTML page's picture, which it does not load.
                reference = [w for page in doc for w in words(page.get_text().replace("[image]", ""))]
                count = len(doc)
            got = [w for *_, runs in pages for _, text in runs for w in words(text)]
            assert "SECRET" not in got and "var" not in got, "hidden content shows"
            it = iter(got)
            missing = [w for w in reference if w not in it]
            assert not missing, f"words lost or out of order, starting at {missing[:6]}"
            assert abs(len(got) - len(reference)) <= len(reference) * 0.03 + 3, f"{len(got)} words, MuPDF has {len(reference)}"
            assert count * 0.65 - 1 <= len(pages) <= count * 1.35 + 1, f"{len(pages)} pages, MuPDF has {count}"
            coloured = 0
            for n, (w, h, image, runs) in enumerate(pages):
                assert (w, h) == (400, 600)
                for (x0, y0, x1, y1), text in runs:
                    assert 0 <= x0 <= x1 <= 401 and 0 <= y0 < y1 <= 600, f"page {n}: {text!r} at {(x0, y0, x1, y1)}"
                    box = image.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1)).convert("L")
                    assert text.isspace() or box.getextrema()[0] < 160, f"page {n}: nothing drawn for {text!r}"
                coloured += sum(1 for r, g, b, _ in image.getdata() if r > 170 and g < 60 and b < 60)
                if KEEP:
                    image.save(KEEP / f"{name}.{n}.png")
            if name != "plain.txt":
                assert coloured > 2000, "the picture is missing"
            run = subprocess.run([str(EXE), "export", str(d / name), "-", str(d / "out.pdf")], capture_output=True, text=True)
            assert run.returncode == 0, run.stderr.strip()
            with pymupdf.open(d / "out.pdf") as doc:
                assert len(doc) == len(pages)
            print(f"ok   {name}: {len(pages)} pages (MuPDF {count}), {len(got)} words")
        except Exception as e:
            failed += 1
            print("FAIL", name, e)
    try:
        docx(d / "notes.docx")
        with zipfile.ZipFile(d / "notes.docx") as z:
            parts = {n: z.read(n) for n in z.namelist()}
        ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        extra = ('<w:p><w:r><w:t>Noted</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r></w:p>'
                 '<w:p><w:r><w:pict><w:txbxContent><w:p><w:r><w:t>Inside the box</w:t></w:r></w:p></w:txbxContent>'
                 '</w:pict></w:r></w:p>')
        parts["word/document.xml"] = parts["word/document.xml"].replace(b"<w:sectPr/>", extra.encode() + b"<w:sectPr/>")
        parts["word/footnotes.xml"] = (f'<w:footnotes {ns}><w:footnote w:id="2"><w:p><w:r><w:t>The footnote itself</w:t>'
                                       '</w:r></w:p></w:footnote></w:footnotes>').encode()
        with zipfile.ZipFile(d / "notes.docx", "w") as z:
            for n, data in parts.items():
                z.writestr(n, data)
        text = " ".join(t for *_, runs in ours(d / "notes.docx", d) for _, t in runs)
        for needle in ("Noted1", "Inside the box", "1. The footnote itself"):
            assert needle in text, f"missing {needle!r}"
        assert text.index("Inside the box") < text.index("The footnote itself")
        print("ok   footnotes and text boxes")
    except Exception as e:
        failed += 1
        print("FAIL notes.docx", e)
    for name, data in {"bad.epub": b"PK\x03\x04junk", "bad.docx": b"junk", "bad.mobi": b"x" * 100,
                       "bad.fb2": b"<a", "deep.html": b"<div>" * 20000 + b"deep",
                       "deep.xhtml": b"<div>" * 20000 + b"deep" + b"</div>" * 20000,
                       "deep.fb2": b"<FictionBook><body>" + b"<section>" * 20000 + b"</section>" * 20000 +
                                   b"</body></FictionBook>"}.items():
        (d / name).write_bytes(data)
        run = subprocess.run([str(EXE), "pages", str(d / name), "-", str(d / "raw")], capture_output=True, text=True, timeout=120)
        # An error or a page, never a crash.
        good = "panicked" not in run.stderr and "overflow" not in run.stderr and run.returncode in (0, 1)
        print(f"ok   {name} exits {run.returncode}" if good else f"FAIL {name} {run.returncode} {run.stderr[-300:]}")
        failed += not good
raise SystemExit(f"{failed} failed" if failed else 0)
