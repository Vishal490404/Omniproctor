# WebClient kiosk installer drop-in directory

The WebClient backend serves the Windows kiosk installer via the authenticated
endpoint `GET /api/v1/downloads/installer/windows`.

For the endpoint to return the file (rather than 404), drop the installer into
this directory using the exact filename configured in `app/core/config.py`:

```
WebClient/installers/OmniProctorKioskSetup.exe
```

When using Docker Compose, this directory is bind-mounted read-only into the
container at `/var/lib/omniproctor/installers` (see `docker-compose.yml`).

## How to populate it

After building the kiosk on a Windows machine (see `Browser/README.md`):

```powershell
# Inside the Browser/ directory
.\build\build.ps1
Copy-Item .\build\Output\OmniProctorKioskSetup-0.1.0.exe `
          ..\WebClient\installers\OmniProctorKioskSetup.exe -Force
```

If you publish a new build, also bump:

```python
# WebClient/app/core/config.py
installer_windows_version: str = "0.2.0"
```

(or set the `INSTALLER_WINDOWS_VERSION` env var in `.env`).

The backend computes the SHA-256 lazily and caches it by `(path, mtime, size)`,
so simply overwriting the file is enough — the manifest will refresh on the
next request.
