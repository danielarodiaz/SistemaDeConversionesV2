from pathlib import Path
from typing import Any

import pandas as pd

from .config import SyncNovedadesConfig
from .modelos import LOGISTICA_COLUMNS


def read_logistica_excel(path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str)
    df.columns = [str(col).strip() for col in df.columns]
    missing = [col for col in LOGISTICA_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError("El Excel de logistica no tiene las columnas esperadas: " + ", ".join(missing))
    return df[LOGISTICA_COLUMNS].copy()


def filter_logistica_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    estado = df["Estado"].fillna("").astype(str).str.strip()
    transporte = df["Transporte"].fillna("").astype(str).str.strip()
    estados_validos = {"Recibido", "Recibido con observaciones"}
    mask = estado.isin(estados_validos) & (transporte == "Sevillanita")
    return df.loc[mask].copy(), int((~mask).sum())


def export_from_app(config: SyncNovedadesConfig) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright no esta instalado. Ejecuta: python -m playwright install chromium") from exc

    config.download_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.headless)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": config.viewport_width, "height": config.viewport_height},
        )
        page = context.new_page()
        page.goto(config.app_url, wait_until="networkidle")

        if config.automation_mode == "flutter_actions":
            download = _run_flutter_actions_for_download(page, config)
        else:
            try:
                download = _run_semantic_flow_for_download(page, config)
            except Exception:
                if config.automation_mode == "semantic" or not config.flutter_actions:
                    raise
                download = _run_flutter_actions_for_download(page, config)

        output = config.download_dir / download.suggested_filename
        download.save_as(output)
        browser.close()
    return output


def _run_semantic_flow_for_download(page, config: SyncNovedadesConfig):
    if config.login_user_selector:
        page.fill(config.login_user_selector, config.app_user)
    else:
        _fill_first_available(page, ["Usuario", "User", "Email"], config.app_user)

    if config.login_password_selector:
        page.fill(config.login_password_selector, config.app_password)
    else:
        _fill_first_available(page, ["Contrasena", "Contraseña", "Password"], config.app_password)

    if config.login_submit_selector:
        page.click(config.login_submit_selector)
    else:
        _click_first_available(page, ["Ingresar", "Login", "Acceder"])

    page.wait_for_load_state("networkidle")
    _click_first_available(page, ["Logistica", "Logística"])
    _click_first_available(page, ["Listado de despachados", "Despachados"])
    page.wait_for_load_state("networkidle")

    _select_or_click_option(page, "Estado", "Todos")
    _select_or_click_option(page, "Transporte", "Sevillanita")

    with page.expect_download(timeout=120000) as download_info:
        if config.export_selector:
            page.click(config.export_selector)
        else:
            _click_first_available(page, ["Exportar", "Excel", "Descargar"])
    return download_info.value


def _run_flutter_actions_for_download(page, config: SyncNovedadesConfig):
    if not config.flutter_actions:
        raise ValueError("LOGISTICA_FLUTTER_ACTIONS esta vacio; no hay secuencia para automatizar Flutter")

    page.locator("flutter-view").wait_for(state="visible", timeout=30000)
    with page.expect_download(timeout=120000) as download_info:
        for action in config.flutter_actions:
            _run_flutter_action(page, action, config)
    return download_info.value


def _run_flutter_action(page, action: dict[str, Any], config: SyncNovedadesConfig) -> None:
    action_type = str(action.get("type", "")).strip().lower()
    delay = int(action.get("delay_ms", 0) or 0)

    if action_type == "click":
        x, y = _required_xy(action)
        page.mouse.click(x, y)
    elif action_type == "dblclick":
        x, y = _required_xy(action)
        page.mouse.dblclick(x, y)
    elif action_type == "fill":
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(_resolve_text(action.get("text", ""), config))
    elif action_type == "type":
        page.keyboard.insert_text(_resolve_text(action.get("text", ""), config))
    elif action_type == "press":
        page.keyboard.press(str(action["key"]))
    elif action_type == "wait":
        page.wait_for_timeout(int(action.get("ms", 1000)))
    elif action_type == "wait_network":
        page.wait_for_load_state("networkidle")
    elif action_type == "scroll":
        page.mouse.wheel(int(action.get("dx", 0)), int(action.get("dy", 0)))
    else:
        raise ValueError(f"Accion Flutter no soportada: {action_type}")

    if delay:
        page.wait_for_timeout(delay)


def _fill_first_available(page, labels: list[str], value: str) -> None:
    last_error = None
    for label in labels:
        try:
            page.get_by_label(label).fill(value, timeout=3000)
            return
        except Exception as exc:
            last_error = exc
    raise last_error


def _click_first_available(page, names: list[str]) -> None:
    last_error = None
    for name in names:
        try:
            page.get_by_role("button", name=name).click(timeout=3000)
            return
        except Exception as exc:
            last_error = exc
        try:
            page.get_by_text(name, exact=False).click(timeout=3000)
            return
        except Exception as exc:
            last_error = exc
    raise last_error


def _select_or_click_option(page, label: str, option: str) -> None:
    try:
        page.get_by_label(label).select_option(label=option, timeout=3000)
        return
    except Exception:
        pass
    _click_first_available(page, [label])
    _click_first_available(page, [option])


def _required_xy(action: dict[str, Any]) -> tuple[int, int]:
    if "x" not in action or "y" not in action:
        raise ValueError("La accion click/dblclick requiere x e y")
    return int(action["x"]), int(action["y"])


def _resolve_text(text: Any, config: SyncNovedadesConfig) -> str:
    value = str(text)
    return (
        value.replace("${LOGISTICA_APP_USER}", config.app_user)
        .replace("${LOGISTICA_APP_PASSWORD}", config.app_password)
    )
