"""Builds x86_64 APKs of this version and a newer throwaway one, for testing on an emulator,
signed as releases are.  python pack/android_test_apks.py
(needs CARGO_REMEDY, ANDROID_HOME and REMEDY_ANDROID_KEYSTORE_PASSWORD)"""
import os, pathlib, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "target" / "e2e-android"


def build(version):
    manifest, lock, toml = ROOT / "Cargo.toml", ROOT / "Cargo.lock", ROOT / "remedy.toml"
    saved = {f: f.read_bytes() for f in (manifest, lock, toml)}
    try:
        text = manifest.read_text(encoding="utf-8")
        current = text.split('version = "', 1)[1].split('"', 1)[0]
        manifest.write_text(text.replace(f'version = "{current}"', f'version = "{version}"', 1), encoding="utf-8")
        config = toml.read_text(encoding="utf-8").replace(
            'targets = ["aarch64-linux-android", "armv7-linux-androideabi"]', 'targets = ["x86_64-linux-android"]')
        assert 'targets = ["x86_64-linux-android"]' in config
        toml.write_text(config, encoding="utf-8")
        subprocess.run([os.environ["CARGO_REMEDY"], "remedy", "package", "--target", "android"], cwd=ROOT, check=True)
    finally:
        for f, data in saved.items():
            f.write_bytes(data)
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"RemedyPDF_{version}_x86_64.apk"
    for each in (name, name + ".sig"):
        shutil.copy(ROOT / "target" / "remedy" / "dist" / each, OUT / each)


if __name__ == "__main__":
    build("2.0.0")
    build("2.0.1")
    print("ok  ", *sorted(p.name for p in OUT.glob("*.apk")))
