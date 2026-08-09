# Changelog

All notable changes to RemedyPDF are documented in this file.

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
