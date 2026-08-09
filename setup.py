from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parent


def _version() -> str:
    init = ROOT / "src" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


setup(
    name="RemedyPDF",
    version=_version(),
    description="Sleek multi-format PDF/EPUB viewer and editor with GitHub auto-update",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Ahmi Darrow",
    url="https://github.com/AhmiDarrow/RemedyPDF",
    project_urls={
        "Homepage": "https://github.com/AhmiDarrow/RemedyPDF",
        "Releases": "https://github.com/AhmiDarrow/RemedyPDF/releases",
        "Source": "https://github.com/AhmiDarrow/RemedyPDF",
    },
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    py_modules=["main"],
    package_data={"": ["py.typed"]},
    include_package_data=True,
    install_requires=[
        "PyQt5>=5.15.0",
        "PyMuPDF>=1.23.0",
        "PyPDF2>=3.0.0",
        "Pillow>=9.0.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0", "pyinstaller>=6.0.0"],
    },
    python_requires=">=3.10",
    entry_points={
        "gui_scripts": [
            "remedy-pdf=main:main",
        ],
        "console_scripts": [
            "remedy-pdf-cli=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Android",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
        "Topic :: Multimedia :: Graphics :: Viewers",
    ],
    keywords=[
        "pdf",
        "epub",
        "viewer",
        "editor",
        "remedy",
        "windows-installer",
        "android",
        "book-mode",
    ],
)
