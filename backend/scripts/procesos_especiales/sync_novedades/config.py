import os
import json
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")


@dataclass(frozen=True)
class SyncNovedadesConfig:
    app_url: str
    app_user: str
    app_password: str
    download_dir: Path
    google_service_account_file: str
    google_spreadsheet_id: str
    google_worksheet_name: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    notify_to: str
    fuzzy_threshold: int = 90
    headless: bool = True
    automation_mode: str = "auto"
    viewport_width: int = 1366
    viewport_height: int = 768
    flutter_actions: tuple[dict, ...] = ()
    login_user_selector: str = ""
    login_password_selector: str = ""
    login_submit_selector: str = ""
    export_selector: str = ""


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "y"}


def _json_actions_env(name: str) -> tuple[dict, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} debe ser JSON valido") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError(f"{name} debe ser una lista JSON de objetos")
    return tuple(parsed)


def load_config() -> SyncNovedadesConfig:
    download_dir = Path(os.getenv("SYNC_NOVEDADES_DOWNLOAD_DIR", BASE_DIR / "backend" / "outputs" / "sync_novedades"))
    return SyncNovedadesConfig(
        app_url=os.getenv("LOGISTICA_APP_URL", ""),
        app_user=os.getenv("LOGISTICA_APP_USER", ""),
        app_password=os.getenv("LOGISTICA_APP_PASSWORD", ""),
        download_dir=download_dir,
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
        google_spreadsheet_id=os.getenv("NOVEDADES_SPREADSHEET_ID", ""),
        google_worksheet_name=os.getenv("NOVEDADES_WORKSHEET_NAME", "NOVEDADES"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
        notify_to=os.getenv("SYNC_NOVEDADES_NOTIFY_TO", "danieladiaz@marathon.com.ar"),
        fuzzy_threshold=int(os.getenv("SYNC_NOVEDADES_FUZZY_THRESHOLD", "90")),
        headless=_bool_env("LOGISTICA_APP_HEADLESS", True),
        automation_mode=os.getenv("LOGISTICA_AUTOMATION_MODE", "auto").strip().lower(),
        viewport_width=int(os.getenv("LOGISTICA_VIEWPORT_WIDTH", "1366")),
        viewport_height=int(os.getenv("LOGISTICA_VIEWPORT_HEIGHT", "768")),
        flutter_actions=_json_actions_env("LOGISTICA_FLUTTER_ACTIONS"),
        login_user_selector=os.getenv("LOGISTICA_LOGIN_USER_SELECTOR", ""),
        login_password_selector=os.getenv("LOGISTICA_LOGIN_PASSWORD_SELECTOR", ""),
        login_submit_selector=os.getenv("LOGISTICA_LOGIN_SUBMIT_SELECTOR", ""),
        export_selector=os.getenv("LOGISTICA_EXPORT_SELECTOR", ""),
    )


def validate_config(config: SyncNovedadesConfig, *, need_app: bool, need_sheets: bool, need_email: bool) -> None:
    missing = []
    if need_app:
        for field in ("app_url", "app_user", "app_password"):
            if not getattr(config, field):
                missing.append(field)
    if need_sheets:
        for field in ("google_service_account_file", "google_spreadsheet_id"):
            if not getattr(config, field):
                missing.append(field)
    if need_email:
        for field in ("smtp_host", "smtp_user", "smtp_password", "smtp_from", "notify_to"):
            if not getattr(config, field):
                missing.append(field)
    if missing:
        raise ValueError("Faltan variables de configuracion para sync_novedades: " + ", ".join(missing))
