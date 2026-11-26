"""Writes the third-party notices a release ships: every crate built into the program, with
its licence texts, and PDFium's licences.  python pack/notices.py   (from remedyui/)"""
import json, pathlib, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "target" / "notices"
TARGETS = ["x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu", "aarch64-linux-android", "armv7-linux-androideabi"]


def packages():
    """Every package built into a release on any platform (not build or test only)."""
    found = {}
    for target in TARGETS:
        data = json.loads(subprocess.run(
            ["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", target],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
        by_id = {p["id"]: p for p in data["packages"]}
        nodes = {n["id"]: n for n in data["resolve"]["nodes"]}
        waiting, seen = [data["resolve"]["root"]], set()
        while waiting:
            at = waiting.pop()
            if at in seen:
                continue
            seen.add(at)
            for dep in nodes[at]["deps"]:
                if any(kind["kind"] is None for kind in dep["dep_kinds"]):
                    waiting.append(dep["pkg"])
        for at in seen - {data["resolve"]["root"]}:
            p = by_id[at]
            found[(p["name"], p["version"])] = p
    return [found[k] for k in sorted(found)]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    parts = ["RemedyPDF includes the following open-source software.",
             "PDFium's licences are in the pdfium-licenses folder.", ""]
    bare = []
    for p in packages():
        folder = pathlib.Path(p["manifest_path"]).parent
        texts = sorted(f for f in folder.iterdir()
                       if f.is_file() and f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "UNLICENSE")))
        parts.append("=" * 78)
        parts.append(f"{p['name']} {p['version']}  ({p['license'] or 'see its files'})")
        if p.get("repository"):
            parts.append(p["repository"])
        if not texts:
            # Named by its authors; the licence's own text is at the end.
            bare.append(f"{p['name']} {p['version']}")
            if p.get("authors"):
                parts.append("Copyright: " + ", ".join(p["authors"]))
        for f in texts:
            parts += ["", f"--- {f.name}", f.read_text(encoding="utf-8", errors="replace").strip()]
        parts.append("")
    parts += ["=" * 78, "Standard texts, for the packages above that ship no licence file of their own.", ""]
    for name, source in (("MIT", "LICENSE-MIT"), ("Apache-2.0", "LICENSE-APACHE")):
        parts += [f"--- {name}", (ROOT.parent.parent / "Projects" / "RemedyUI" / source).read_text(encoding="utf-8").strip(), ""]
    (OUT / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(parts), encoding="utf-8")
    pdfium = OUT / "pdfium-licenses"
    shutil.copytree(ROOT / "pdfium" / "licenses", pdfium)
    shutil.copy(ROOT / "pdfium" / "LICENSE", pdfium / "pdfium-binaries.txt")
    # The Android builds of PDFium carry a few more.
    for f in (ROOT / "pdfium" / "arm64-v8a" / "licenses").iterdir():
        if not (pdfium / f.name).exists():
            shutil.copy(f, pdfium / f.name)
    print(f"notices: {OUT}; {len(bare)} packages ship no licence file of their own: {', '.join(bare)}")


if __name__ == "__main__":
    main()
