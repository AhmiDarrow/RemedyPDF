import sys
from pathlib import Path
from unittest.mock import patch

from utils.paths import project_root, resources_dir


def test_project_root_contains_src():
    root = project_root()
    assert (root / "src").is_dir()
    assert (root / "setup.py").is_file()


def test_resources_dir():
    res = resources_dir()
    assert res.name == "resources"
    assert res.parent == project_root()
    # brand assets ship with the tree
    assert (res / "icon.png").is_file()
    assert (res / "logo.png").is_file()


def test_frozen_resources_prefer_meipass(tmp_path: Path):
    """Packaged builds must resolve resources under sys._MEIPASS / exe dir."""
    mei = tmp_path / "mei"
    res = mei / "resources"
    res.mkdir(parents=True)
    (res / "icon.png").write_bytes(b"x")
    fake_exe = tmp_path / "RemedyPDF.exe"
    fake_exe.write_bytes(b"")
    with patch.object(sys, "frozen", True, create=True), patch.object(
        sys, "_MEIPASS", str(mei), create=True
    ), patch.object(sys, "executable", str(fake_exe)):
        assert project_root() == mei
        assert resources_dir() == res
