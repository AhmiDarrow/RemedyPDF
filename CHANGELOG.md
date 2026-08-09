# Changelog

All notable changes to RemedyPDF are documented in this file.

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
