"""A real self-update on this PC, with a test copy that cannot touch an installed RemedyPDF:
its own name, installer id and folder. It builds the current version and a newer throwaway
one, installs the first, lets it update itself from a local server, and checks the result.
It also checks that a download which is not signed with the update key is refused.

  python pack/e2e_update.py        (from remedyui/; needs CARGO_REMEDY and REMEDY_UPDATE_KEY)
"""
import base64, functools, hashlib, http.server, json, os, pathlib, shutil, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "target" / "e2e"
NAME = "RemedyPDF Test"
APP_ID = "{5E57C0DE-0000-4E2E-9A11-52656D656479}"
INSTALL = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Programs" / NAME
REAL = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Programs" / "RemedyPDF"
PORT = 18765
SILENT = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CURRENTUSER"]
PACKAGER = os.environ["CARGO_REMEDY"]


def snapshot(folder):
    if not folder.exists():
        return {}
    return {str(f.relative_to(folder)): (f.stat().st_size, f.stat().st_mtime_ns)
            for f in folder.rglob("*") if f.is_file()}


def build(version):
    """Packages the test identity at `version`, then puts the sources back."""
    manifest, lock, toml = ROOT / "Cargo.toml", ROOT / "Cargo.lock", ROOT / "remedy.toml"
    saved = {f: f.read_bytes() for f in (manifest, lock, toml)}
    try:
        text = manifest.read_text(encoding="utf-8")
        current = text.split('version = "', 1)[1].split('"', 1)[0]
        manifest.write_text(text.replace(f'version = "{current}"', f'version = "{version}"', 1), encoding="utf-8")
        config = toml.read_text(encoding="utf-8")
        config = config.replace('name = "RemedyPDF"', f'name = "{NAME}"')
        config = config.replace("{B7E2C4A1-8F3D-4A9E-9C1B-5D6E8F0A2B3C}", APP_ID)
        toml.write_text(config, encoding="utf-8")
        subprocess.run([PACKAGER, "remedy", "package"], cwd=ROOT, check=True)
    finally:
        for f, data in saved.items():
            f.write_bytes(data)
    out = WORK / version
    out.mkdir(parents=True, exist_ok=True)
    for suffix in ("setup.exe", "setup.exe.sig"):
        name = f"RemedyPDF_{version}_x64-{suffix}"
        shutil.copy(ROOT / "target" / "remedy" / "dist" / name, out / name)
    return out / f"RemedyPDF_{version}_x64-setup.exe"


def running():
    """(pid, window title) of every process running the test copy's program, and no other."""
    script = ("Get-Process RemedyPDF -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq '"
              + str(INSTALL / "RemedyPDF.exe") + "' } | ForEach-Object { \"$($_.Id)`t$($_.MainWindowTitle)\" }")
    out = subprocess.run(["pwsh", "-NoProfile", "-Command", script], capture_output=True, text=True,
                         encoding="utf-8").stdout
    return [(int(a), b) for a, _, b in (line.partition("\t") for line in out.splitlines() if line.strip())]


def stop_test_copy():
    for pid, _ in running():
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def version_of(exe):
    script = f"(Get-Item -LiteralPath '{exe}').VersionInfo.ProductVersion"
    return subprocess.run(["pwsh", "-NoProfile", "-Command", script], capture_output=True, text=True).stdout.strip()


def wait(what, check, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        got = check()
        if got:
            return got
        time.sleep(1)
    raise AssertionError(f"never happened: {what}")


def feed(setup, signature_of=None):
    name = setup.name
    signature = pathlib.Path(str(signature_of or setup) + ".sig").read_bytes()
    entry = {"url": f"http://127.0.0.1:{PORT}/{name}", "signature": base64.b64encode(signature).decode(),
             "sha256": hashlib.sha256(setup.read_bytes()).hexdigest(), "size": setup.stat().st_size}
    version = name.split("_")[1]
    (setup.parent / "latest.json").write_text(json.dumps({"version": version, "platforms": {"windows-x86_64": entry}}))


def start(folder, document):
    env = dict(os.environ, REMEDYPDF_UPDATE_FEED=f"http://127.0.0.1:{PORT}/latest.json")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    subprocess.Popen([str(INSTALL / "RemedyPDF.exe"), str(document), "--install-update"], env=env)
    return server


def main():
    assert not INSTALL.exists(), f"{INSTALL} already exists: remove the old test copy first"
    real_before = snapshot(REAL)
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    old = build("2.0.0")
    new = build("2.0.1")
    document = WORK / "reading.pdf"
    import pymupdf
    doc = pymupdf.open()
    for n in range(5):
        doc.new_page().insert_text((72, 100), f"Page {n + 1}", fontsize=30)
    doc.save(document)
    server = None
    try:
        subprocess.run([str(old), *SILENT], check=True, timeout=180)
        wait("the first install", lambda: (INSTALL / "RemedyPDF.exe").exists())
        assert version_of(INSTALL / "RemedyPDF.exe") == "2.0.0"
        for needed in ("pdfium.dll", "THIRD-PARTY-NOTICES.txt", "pdfium-licenses/pdfium.txt"):
            assert (INSTALL / needed).is_file(), f"the install lacks {needed}"
        # Setup opens the app after a silent install; close that one before the test's own.
        time.sleep(3)
        stop_test_copy()
        print("ok   installed 2.0.0 silently, with PDFium and the notices")

        # A download signed for another file is refused, and nothing changes.
        bad = WORK / "bad"
        bad.mkdir()
        shutil.copy(new, bad / new.name)
        (bad / new.name).write_bytes(new.read_bytes() + b"changed")
        shutil.copy(str(new) + ".sig", bad / (new.name + ".sig"))
        feed(bad / new.name)
        server = start(bad, document)
        time.sleep(25)
        assert version_of(INSTALL / "RemedyPDF.exe") == "2.0.0", "a tampered download was installed"
        assert running(), "the app should still be running after refusing the download"
        server.shutdown()
        server.server_close()
        server = None
        stop_test_copy()
        print("ok   a tampered download is refused")

        # The real thing: no clicks.
        feed(new)
        server = start(new.parent, document)
        first = wait("the app starts", running, 30)[0][0]
        wait("2.0.1 installs", lambda: version_of(INSTALL / "RemedyPDF.exe") == "2.0.1", 150)
        again = wait("the new version reopens the document",
                     lambda: [p for p in running() if p[0] != first and p[1].startswith("reading.pdf")], 90)
        time.sleep(5)
        assert [p[0] for p in running()] == [again[0][0]], f"expected one running copy: {running()}"
        print("ok   2.0.0 updated itself to 2.0.1 with no clicks, and reopened the document")
    finally:
        if server:
            server.shutdown()
            server.server_close()
        stop_test_copy()
        uninstaller = INSTALL / "unins000.exe"
        if uninstaller.exists():
            subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=180)
            time.sleep(5)
        assert snapshot(REAL) == real_before, "the installed RemedyPDF changed"
        print("ok   the installed RemedyPDF is untouched; the test copy is removed" if not INSTALL.exists()
              else f"note: {INSTALL} is still there")


if __name__ == "__main__":
    main()
