# Auto-update (GitHub Releases)

Modeled after SecretSticky / SecretFolder: About panel + release channel on GitHub.

## Runtime

- `src/utils/updater.py`
  - `check_for_update(owner, repo, current_version)` → GitHub Releases API
  - Optional fallback: `…/releases/latest/download/latest.json`
  - Soft-fail offline (returns `None`, never crashes UI)
- `src/ui/about.py` — **Check for updates** / **Get update** (opens release URL)
- Help → **Check for Updates…**

Version source of truth: `src/__init__.py` → `__version__`.

## Release pipeline

Tag push `v*`:

1. `pytest -q` gate
2. `python build_windows.py` → `dist/RemedyPDF.exe`
3. Upload exe + generate `latest.json`:
   ```json
   {
     "version": "1.2.0",
     "notes": "…",
     "pub_date": "…",
     "platforms": {
       "windows-x86_64": {
         "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v1.2.0/RemedyPDF.exe"
       }
     }
   }
   ```

## Manual check

```text
Help → About → Check for updates
```
