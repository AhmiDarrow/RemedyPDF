"""Cross-check against PyMuPDF (a test reference only, never shipped).
Run from remedyui/: python tests/encryption.py"""
import pathlib, subprocess, tempfile
import pymupdf

subprocess.run(["cargo", "build", "-q", "--example", "resave"], check=True)
EXE = next(p for p in pathlib.Path("target/debug/examples").glob("resave*") if p.suffix in ("", ".exe"))
KINDS = {"aes256": pymupdf.PDF_ENCRYPT_AES_256, "aes128": pymupdf.PDF_ENCRYPT_AES_128,
         "rc4_128": pymupdf.PDF_ENCRYPT_RC4_128, "rc4_40": pymupdf.PDF_ENCRYPT_RC4_40}
PASSWORDS = ["secret", "pässwörd ✓"]
PERMS = pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY
failed = 0
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    png.set_rect(png.irect, (200, 30, 30))
    for kind, method in KINDS.items():
        for n, pw in enumerate(PASSWORDS):
            if n and kind != "aes256":
                continue  # non-ASCII passwords are only well defined for AES-256
            for objstm in (0, 1):
                path = pathlib.Path(d, f"{kind}-{n}-{objstm}.pdf")
                doc = pymupdf.open()
                for i in range(3):
                    page = doc.new_page()
                    page.insert_text((72, 72), f"Quarterly report page {i + 1}")
                    page.insert_image(pymupdf.Rect(72, 100, 172, 200), pixmap=png)
                doc.set_metadata({"title": "Secret title"})
                doc.set_toc([[1, "First chapter", 1]])
                doc.save(path, encryption=method, user_pw=pw, owner_pw=pw, permissions=PERMS, use_objstms=objstm)
                doc.close()
                def read():
                    with pymupdf.open(path) as r:
                        locked = bool(r.needs_pass)
                        assert r.authenticate(pw), "password rejected"
                        return (locked, r.permissions, r.metadata["title"], r.get_toc(),
                                [(p.get_text(), p.get_pixmap().samples) for p in r], r.metadata["encryption"])
                before = read()
                run = subprocess.run([str(EXE), str(path), pw], capture_output=True, text=True, encoding="utf-8")
                try:
                    assert run.returncode == 0, run.stderr.strip()
                    # Again, on our own output (/Encrypt as a separate object, not inline).
                    run = subprocess.run([str(EXE), str(path), pw], capture_output=True, text=True, encoding="utf-8")
                    assert run.returncode == 0, run.stderr.strip()
                    after = read()
                    for i, what in enumerate(["locked", "permissions", "title", "outline", "pages"]):
                        assert after[i] == before[i], f"{what} changed"
                    assert "256-bit AES" in after[5], after[5]
                    raw = path.read_bytes()
                    assert b"Quarterly" not in raw and b"Secret title" not in raw, "plaintext on disk"
                    assert not pymupdf.open(path).authenticate("wrong"), "wrong password accepted"
                    assert [f for f in path.parent.iterdir() if f.suffix != ".pdf"] == [], "temp file left"
                    print("ok  ", path.name)
                except Exception as e:
                    failed += 1
                    print("FAIL", path.name, e)
raise SystemExit(f"{failed} failed" if failed else 0)
