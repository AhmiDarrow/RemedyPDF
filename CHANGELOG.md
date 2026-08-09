# Changelog

All notable changes to RemedyPDF are documented in this file.

## [1.3.2] — 2026-08-09

### Fixed — theme text colors
- **Themes now recolor document text + paper** (view-only ink/paper map) so dark/night/sepia/etc. change page text, not only chrome
- **QPalette text roles** (WindowText, Text, ButtonText, PlaceholderText, Link) follow each theme
- Stronger QSS for labels, menus, status bar, search bar, navigator, tabs, checkboxes
- Canvas empty-state placeholder uses themed `canvas_text`
- Page Appearance filters still layer on top of theme recolor; reset keeps theme ink/paper

## [1.3.1] — 2026-08-09

### Added — reading visibility polish
- **8 chrome themes**: Dark, Light, High contrast, Sepia, Night (OLED), Midnight blue, Soft paper, Slate gray
- **Page appearance filters** (view-only): Normal, Invert, Sepia, Grayscale, Warm, Cool
- **Brightness / contrast** sliders via hotkeys (`Ctrl+Shift+↑/↓`, `Ctrl+Alt+↑/↓`)
- **UI Scale** menu: 90% → 150% chrome font size (independent of page zoom)
- Fit width/page/height, full screen, status bar shows theme + filter + B/C
- Android toolchain helper (`scripts/setup_android_toolchain.py`) for next APK push

### Shortcuts
- `Ctrl+Shift+I` invert page · `Ctrl+Shift+0` reset appearance
- `Ctrl+Shift+T` cycle all 8 themes · `Ctrl+Shift+H/S/N` quick themes

## [1.3.0] — 2026-08-09

### Added
- **Windows installer** — Inno Setup 6 (`installer/remedypdf.iss`) producing
  `RemedyPDF-*-windows-setup.exe` with Start Menu + optional Desktop shortcuts
- **Android release path** — `build_android.py` stages APK (Buildozer) or
  `*-android-src.zip` + `ANDROID_BUILD.md` so every release has an Android asset
- **About platform tags** — Windows installer · Android APK · PDF/EPUB · Auto-update · MIT
- **Multi-platform `latest.json`** — `windows-x86_64` + `android-arm64` download URLs
- Docs: `docs/INSTALL.md`

### Fixed
- Release workflow `GITHUB_TOKEN` wiring for `softprops/action-gh-release`
- Release notes now point at Setup installer (not only onefile exe)

## [1.2.0] — 2026-03-22

### Added
- **About** panel modeled on SecretSticky/SecretFolder: “Hi I'm Ahmi, hope this helps!”, brand logo, GitHub profile / repo / Releases / Patreon links
- **Check for updates** (Help menu + About) via GitHub Releases API + optional `latest.json`
- Brand helpers (`src/utils/brand.py`) — window icon (ICO/PNG), About mark, asset inventory
- CI + Release workflows (pytest gate, Windows PyInstaller, `latest.json` on tag `v*`)
- Docs: README auto-update / brand tables, CONTRIBUTING

### Fixed / polished (prior 1.2 work)
- Both-sides book mode (spread not clipped)
- Fine zoom 1% (Ctrl+wheel), zoom reset Ctrl+0
- Double-click (PC) / long-press (mobile) edit
- Dirty open/close prompts, search Enter first-hit, RGB paint + LRU cache

## [1.0.0] — initial

- Core PDF viewer/editor scaffold
