from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Omniproctor API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    database_url: str = "postgresql+psycopg://omniproctor:omniproctor@db:5432/omniproctor"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: list[str] = ["*"]

    # Kiosk-browser installer distribution -------------------------------
    # Two delivery modes - the first one to be configured wins:
    #
    #   1. External URL (e.g. GitHub Releases). Set INSTALLER_WINDOWS_URL
    #      to an absolute https://… URL of the .exe asset. The download
    #      endpoint then 307-redirects there and the manifest exposes the
    #      URL directly so the SPA can offer a one-click download.
    #
    #   2. Local file. The installer EXE is dropped into ``installer_dir``
    #      (bind-mounted into the API container in docker-compose.yml).
    #      The endpoint streams it with a Bearer-auth check.
    installer_dir: str = "/var/lib/omniproctor/installers"
    installer_windows_filename: str = "OmniProctorKioskSetup.exe"
    installer_windows_version: str = "0.1.0"
    # Absolute https:// URL of the Windows installer. When set, takes
    # precedence over the local file. Typically a GitHub Releases asset
    # like:
    #   https://github.com/<org>/<repo>/releases/download/v0.1.0/OmniProctorSetup-0.1.0.exe
    # or the always-latest alias:
    #   https://github.com/<org>/<repo>/releases/latest/download/OmniProctorSetup.exe
    installer_windows_url: str | None = None
    # Optional metadata exposed via /downloads/manifest. Useful when the
    # installer is hosted externally (we can't compute SHA-256 / size
    # without downloading the file ourselves on every request).
    installer_windows_sha256: str | None = None
    installer_windows_size_bytes: int | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
