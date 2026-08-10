# Changelog

All notable changes to RemedyPDF are documented in this file.

## [1.4.1] — 2026-08-10

### Fixed — Windows installer now ships `--onedir` (kills the auto-update crash)

- **Root cause**: the released installer bundled a PyInstaller `--onefile`
  exe (~97 MB) that re-extracts 2646 files to `%TEMP%\_MEIxxxxx` on *every*
  launch and loads `python312.dll` from there. During the auto-update
  relaunch (old process killed + fresh extraction + AV scan of a brand-new
  binary) the bootloader can hit "Failed to load Python DLL 'python312.dll'.
  LoadLibrary: The specified module could not be found." — a transient
  onefile bootloader race, not a corrupt download (the archive itself
  contains python312.dll + all VC runtimes, verified).
- **Fix**: `build_windows.py` now builds the app as **onedir**
  (`dist/RemedyPDF/` with `python312.dll` and every runtime DLL as real
  files next to the exe) and `installer/remedypdf.iss` installs the whole
  folder. Zero `%TEMP%` extraction, no bootloader race, faster startup.
  The portable single-file exe asset is still built (onefile is fine for
  manual download; the *installed* app is what auto-update replaces).
- Portable `RemedyPDF-<ver>-windows.exe` and the setup installer are still
  both published to the release.

### Polish
- `updater.py` cleanup helpers ignore stale `_MEI*` extraction dirs left by
  older onefile builds (they accumulate in `%TEMP%`; onedir won't create them).

### Tests
- `tests/test_installer_onedir.py` — pins the build contract: the installer
  must reference the onedir folder, `build_windows.py` must pass `--onedir`,
  and the iss must install recursively.

## [1.4.0] — 2026-08-10

### Added — mobile QoL & polish pass (Android APK)

- **Tap zones flip pages** — in touch mode a quick tap on the right third of
  the screen goes to the next page, the left third to the previous (classic
  reader UX). Long-press-to-edit and pan are untouched: a drag or a held
  finger never flips a page.
- **Pinch-to-zoom** — native `QPinchGesture` on the canvas zooms around the
  pinch center and reuses the debounced zoom-to-point render pipeline, so
  pinching is smooth and never snaps the view to top-left.
- **Reader mode** — new toolbar toggle hides the toolbar, navigator, search
  bar and status bar and goes fullscreen for distraction-free reading;
  Esc (or tapping the toggle again) restores the chrome. F11 fullscreen
  still works on desktop.
- **Buildozer config polish**: `orientation = sensor` (auto-rotate — PDFs
  read naturally in landscape), `fullscreen = 1` (immersive APK reading),
  `version` synced to 1.4.0.

### Polish
- `utils.mobile.tap_zone_for()` — pure, tested tap-zone classifier.
- All version fallbacks (app, updater, about, main) unified on 1.4.0.

### Tests
- Tap-zone classifier (edges / middle / degenerate width)
- Canvas pinch gesture registered; touch-mode tap emits ±1; drag and
  desktop-mode taps never emit
- Tap zones flip pages through the app; pinch changes engine zoom
- Reader mode hides chrome and exits on Esc
- buildozer.spec version matches `__version__`, orientation sensor,
  immersive fullscreen

### Verification — auto-update chain proven working end-to-end (live)
- Ran the real chain against GitHub on 2026-08-10: `latest.json` channel
  resolves, an old version (1.2.0) is offered v1.3.7 via the `latest.json`
  channel, up-to-date detection is correct at 1.4.0, the Windows installer
  URL resolves, and the 98 MB setup.exe streams down with a valid `MZ`
  header. **ALL PASS.**
- New hermetic `tests/test_updater_schema.py` — pins the contract between
  the release workflow's `scripts/write_latest_json.py` output and
  `utils.updater.check_for_update` / `find_installer_url` (no network),
  including the workflow's android src-zip fallback rewrite.
- New opt-in `tests/test_updater_live.py` — re-proves the live chain after
  any release (`REMEDYPDF_LIVE=1 pytest -q tests/test_updater_live.py`).
- Inno fallback version in `installer/remedypdf.iss` synced to 1.4.0
  (build_windows.py already passes the real version via `/DMyAppVersion`).

## [1.3.9] — 2026-08-10

### Added — QoL navigation (mouse + hotkeys)
- **Mouse wheel flips pages** — in fit view (or at the scroll edge when zoomed)
  the wheel turns the page like a book; inside a zoomed page it still scrolls.
  Horizontal wheel / two-finger trackpad swipe flips pages directly.
- **Mouse side buttons** (back / forward) flip to previous / next page.
- **View rotation**: Ctrl+R / Ctrl+Shift+R (and View → Rotate Right/Left) rotate
  the view 90° — great for scanned portrait PDFs. Rotation is view-only (never
  baked into saved output) and click-to-edit hit-testing stays exact after
  rotating (engine `set_rotation` / `rotate_right` / `rotate_left`).
- **New hotkeys**: Ctrl+G go to page, Ctrl+W close document, Alt+←/→ pages,
  Ctrl+Home/End first/last, Ctrl+PgUp/PgDn pages, F5 re-render.
- **More readable formats, no rebuild** — the open dialog and engine now
  recognize SVG, DOCX (MuPDF office input), MOBI and plain images
  (PNG/JPG/BMP/GIF/TIFF/WEBP) as page-based documents, on top of
  PDF/EPUB/XPS/CBZ/CBR/FB2/HTML/TXT. All still save-as-PDF.

### Fixed
- Version source of truth (`src/__init__.py`) now matches the UI fallbacks (1.3.9).

### Tests
- Wheel page-flip (fit + zoomed-edge + Ctrl-zoom exclusion + horizontal swipe)
- Mouse side-button navigation via eventFilter
- `close_document` lifecycle (close → reopen)
- Rotation: view-size swap, edit-coordinate round-trip, clockwise render direction
- Extra formats present in `SUPPORTED_EXTENSIONS` / `OPEN_FILTER`

## [1.3.8] — 2026-08-10

### Fixed
- **Cache could blow past its byte budget**: `_cache_put` now re-runs LRU
  eviction after updates too, so a single oversized render (e.g. one capped
  page bigger than the whole budget) is dropped instead of silently wedging
  `MAX_CACHE_BYTES`
- **Book-spread fallback board fill allocated a giant Python int list**
  (`[36, 40, 48] * pixels`) before the `bytearray` — now a C-speed
  `bytes` multiply, no multi-GB transient on large spreads

### Polish
- **Ctrl+wheel zoom now zooms to the point under the cursor** — the scroll
  anchor is captured before the zoom and restored after the debounced render,
  so the content under the pointer stays fixed instead of snapping to top-left
  on every wheel burst

### Tests
- `test_cache_drops_oversized_render` — a render larger than the whole cache
  budget must evict itself and leave `_cache_bytes` under the cap

## [1.3.7] — 2026-08-10

### Fixed
- Auto-update actually installs and relaunches now:
  - Removed `skipifsilent` from the Inno `[Run]` step, so silent updates launch the new version.
  - Forced `/CURRENTUSER` per-user silent install — no UAC stall mid-update.
  - The app now exits the process for real after launching the installer; a dirty-document
    save prompt could previously keep it alive and block the exe replacement.

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
