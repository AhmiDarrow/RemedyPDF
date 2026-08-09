# Auto-update (GitHub Releases)

Modeled after SecretSticky / SecretFolder: About panel + release channel on GitHub.

## Runtime

- `src/utils/updater.py`
  - `check_for_update(owner, repo, current_version)` → GitHub Releases API
  - Optional fallback: `.../releases/latest/download/latest.json`
  - Soft-fail offline (returns `None`, never crashes UI)
- `src/ui/about.py` — **Check for updates** / **Get update** (opens release URL)
- Help → **Check for Updates…**
- **Auto-check on launch** — ~4s after the window shows, `run()` schedules
  `_auto_check_for_updates` (background `QThread`; silent when offline or up to date)

When a newer version is found, the app offers **Download & install** (not just a
browser link). `install_update()` streams the Windows Inno Setup installer to the
temp dir (`RemedyPDF-<tag>-setup.exe`) with a progress dialog, then launches it
silently (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`) and quits the app so
the installer can replace files. The setup installs per-user (no admin needed).

- `find_installer_url(info)` — resolves the installer URL from
  `latest.json` `platforms.windows-x86_64.url`, else GitHub API assets
  (setup → portable → generic `.exe`)
- `download_update(url, dest, progress=…)` — streamed download with progress
- `launch_installer(path)` — detached silent Inno Setup run
- `install_update(info, dest_dir=…)` — download + launch, soft-fail (never raises)

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
         "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v1.2.0/RemedyPDF-windows-setup.exe"
       }
     }
   }
   ```

## Manual check

```text
Help → Check for Updates…
Help → About → Check for updates
```

## Notes

- Update checks are soft-fail: offline / rate-limited GitHub returns `None` and
  the UI stays quiet (status-bar message only).
- Manual checks run on a worker `QThread` — the UI never blocks on the network.
