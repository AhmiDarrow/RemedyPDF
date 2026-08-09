from pathlib import Path

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
