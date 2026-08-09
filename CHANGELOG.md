# Changelog

All notable changes to RemedyPDF are documented in this file.

## [1.3.6] — 2026-08-09

### Performance — render pipeline is now C-speed
- **Theme ink/paper recolor rewritten as 256-entry LUTs** (`Image.point`) instead of a per-pixel pure-Python loop — the old path ran O(pixels) Python float math on **every** render (seconds on fit-capped pages); a 5.6 MP recolored render now completes in ~0.14 s
- **Grayscale pages (n==1) convert to RGB in C** via MuPDF (`fitz.csRGB`) instead of a Python expansion loop
- **Sepia / Warm / Cool filters use precomputed LUTs** instead of `point(lambda …)` callbacks (pure-Python per pixel)
- **Book-mode spread no longer forces a rescale every frame** — `get_view_size_at_zoom` gutter now matches the renderer's `max(10, int(14*z))` gap, so the logical size equals the rendered pixmap and `render_current` skips the expensive `SmoothTransformation`
- **`MAX_RENDER_ZOOM` raised 4.0 → 6.0** — fit-width on 1080p+ no longer trips the cap and pays a costly Smooth rescale; the 24 MP pixel budget is still the hard memory guard
- **Wheel-zoom debounced (60 ms)** — trackpad bursts collapse into ONE render instead of one rasterization per notch; zoom % label updates live

### Tests
- Added speed-regression guards: theme recolor < 1 s at 5+ MP, gray conversion < 1 s, book-mode logical size == rendered spread (±2 px)

## [1.3.5] — 2026-08-09

### Added — real auto-update
- **Auto-update now actually installs** — "Check for updates" and the background auto-check download the Windows installer and run it silently (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`, per-user), then the app quits so the installer can replace files
- Installer URL resolved from `latest.json` `platforms.windows-x86_64.url`, falling back to GitHub release assets (setup → portable → generic `.exe`)
- Streamed download with progress dialog; update checks and installs run on a worker thread (no UI freeze on slow networks)
- Auto-check ~4 s after launch; update prompt is non-blocking ("Later" defers, offline stays quiet)
- Docs: `docs/AUTOUPDATE.md` rewritten to match the real flow

### Fixed — fit lag / render performance
- **Render zoom is now capped** (`MAX_RENDER_ZOOM = 4.0`, `MAX_RENDER_PIXELS = 24 MP`) so Fit Width/Page/Height never rasterizes a giant buffer on large screens (was up to ~96 MB/page at zoom 8; now ≤ 24 MB)
- View rescales the capped pixmap to the exact logical size — fit still fills the viewport, click-to-edit hit-testing stays pixel-exact; **export** (`render_page`) remains uncapped for full quality
- LRU render cache is now **byte-budgeted (256 MB)** instead of count-based — no more ~900 MB of fit-zoom pages sitting in RAM
- Neighbor prefetch is deferred via `QTimer.singleShot(0, …)` with burst collapsing — the UI thread never blocks on 3 synchronous renders per fit/page-turn
- Removed a redundant `QImage.copy()` per render (one less 14–28 MB full-buffer clone)

## [1.3.4] — 2026-08-09

### Fixed — Android release path (fast + reliable)
- **Zip-first Android CI** by default — no Buildozer/NDK on every tag (was slow and error-filled on free runners)
- Full Buildozer APK is **opt-in**: workflow_dispatch `build_apk=true`
- `latest.json` android-arm64 points at the real asset (APK if present, else `*-android-src.zip`) so autoupdate never 404s
- Release always ships Windows Setup + portable + Android mobile zip

## [1.3.3] — 2026-08-09

### Fixed — Android CI / APK path
- Release `build-android` job no longer installs removed Ubuntu 24.04 packages (`libtinfo5` / `libncurses5`) that caused apt exit 100
- SDK install is best-effort (`continue-on-error`); package step **always** emits `*-android-src.zip`
- `build_android.py` CLI: `--zip-only` / `--prefer-apk`; relative icon paths in `buildozer.spec` for Linux CI
- Longer Android job timeout (180m) for first Buildozer NDK compile

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
