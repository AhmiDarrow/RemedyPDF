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
temp dir (`RemedyPDF-<tag>-setup.exe`) with a progress dialog (Cancel aborts the
download), optionally verifies **SHA-256** when the channel publishes a digest,
then launches the installer silently (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART
/SP- /CURRENTUSER`) and quits the app so the installer can replace files. The
setup installs per-user (no admin needed).

- `find_installer_url(info)` — resolves the installer URL from
  `latest.json` `platforms.windows-x86_64.url`, else GitHub API assets
  (setup → portable → generic `.exe`)
- `find_installer_sha256(info)` — optional digest from the same channel
- `download_update(url, dest, progress=…, cancel_check=…, expected_sha256=…)` —
  streamed download with progress, cancel, and integrity check
- `launch_installer(path)` — detached silent Inno Setup run
- `install_update(info, dest_dir=…, cancel_check=…)` — download + verify +
  launch; raises `UpdateCancelled` or `OSError` with a clear reason on failure
- `check_for_update` keeps `url` / `html_url` as the **release page**; the
  installer binary stays on `platforms` / `find_installer_url`

Version source of truth: `src/__init__.py` → `__version__`.

## Release pipeline

Tag push `v*`:

1. `pytest -q` gate
2. `python build_windows.py` → onedir + Inno setup + portable exe
3. Hash staged assets and generate `latest.json` (digests included when present):
   ```json
   {
     "version": "1.4.3",
     "notes": "…",
     "pub_date": "…",
     "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/tag/v1.4.3",
     "platforms": {
       "windows-x86_64": {
         "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v1.4.3/RemedyPDF-1.4.3-windows-setup.exe",
         "sha256": "…"
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
