# RemedyPDF docs

- Product overview and usage: see root [README.md](../README.md)
- Changelog: [CHANGELOG.md](../CHANGELOG.md)
- Contributing / release: [CONTRIBUTING.md](../CONTRIBUTING.md)

## Brand assets

Built by `scripts/build_brand_assets.py` from Remedy icon/logo references + PDF badge.

| File | Role |
|------|------|
| `resources/icon.png` / `icon.ico` | App / window / installer icon |
| `resources/logo.png` / `logo_ui.png` | About + marketing |
| `resources/icons/icon_*.png` | Multi-size PNG set |

## Auto-update

1. CI on push/PR runs `pytest -q`
2. Tag `vX.Y.Z` → Release workflow builds `RemedyPDF.exe` and publishes `latest.json`
3. In-app **About → Check for updates** hits GitHub Releases (+ optional `latest.json`)

Owner: [AhmiDarrow](https://github.com/AhmiDarrow) · Repo: [RemedyPDF](https://github.com/AhmiDarrow/RemedyPDF)
