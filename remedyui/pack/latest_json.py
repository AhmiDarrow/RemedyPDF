"""Gathers the signed packages into target/release-upload and writes latest.json for them.
One list serves both updaters: RemedyPDF 1.x reads the Windows url and sha256, and 2.x
reads its platform's url, signature, sha256 and size.

  python pack/latest_json.py        (from remedyui/; after all three packages are built)

The Linux program is built in WSL without the update key, so it is signed here
(needs minisign and REMEDY_UPDATE_KEY).
"""
import base64, datetime, hashlib, json, os, pathlib, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST, LINUX = ROOT / "target" / "remedy" / "dist", ROOT / "target" / "remedy" / "dist-linux"
OUT = ROOT / "target" / "release-upload"
REPO = "https://github.com/AhmiDarrow/RemedyPDF"


def main():
    version = (ROOT / "Cargo.toml").read_text(encoding="utf-8").split('version = "', 1)[1].split('"', 1)[0]
    setup = DIST / f"RemedyPDF_{version}_x64-setup.exe"
    apk = DIST / f"RemedyPDF_{version}_universal.apk"
    program = LINUX / f"RemedyPDF_{version}_linux-x86_64"
    archive = next(LINUX.glob(f"*{version}*.tar.gz"))
    if not pathlib.Path(f"{program}.sig").exists():
        subprocess.run(["minisign", "-S", "-s", os.environ["REMEDY_UPDATE_KEY"], "-m", str(program),
                        "-x", f"{program}.sig", "-t", program.name], check=True, input="\n", text=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    files = [setup, DIST / f"RemedyPDF_{version}_x64-portable.zip", apk, program, archive]
    for f in files:
        shutil.copy(f, OUT / f.name)
        if pathlib.Path(f"{f}.sig").exists():
            shutil.copy(f"{f}.sig", OUT / f"{f.name}.sig")

    def entry(f):
        data = f.read_bytes()
        return {"url": f"{REPO}/releases/download/v{version}/{f.name}",
                "signature": base64.b64encode(pathlib.Path(f"{f}.sig").read_bytes()).decode(),
                "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}

    windows, android = entry(setup), entry(apk)
    page = f"{REPO}/releases/tag/v{version}"
    feed = {
        "version": version, "tag_name": f"v{version}", "name": f"RemedyPDF v{version}",
        "notes": f"RemedyPDF {version}: rebuilt as a native app for Windows, Linux and Android.",
        "url": page, "html_url": page,
        "pub_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {"windows-x86_64": windows, "linux-x86_64": entry(program),
                      "android-aarch64": android, "android-armv7": android},
        # Where 1.x looks if the platform entry has none.
        "sha256": windows["sha256"], "installer_sha256": windows["sha256"],
    }
    (OUT / "latest.json").write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
    print("ok  ", *sorted(f.name for f in OUT.iterdir()), sep="\n  ")


if __name__ == "__main__":
    main()
