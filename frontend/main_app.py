import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import base64
import html
import pandas as pd
import logging
import math
import platform
import re
import sys
import traceback
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.utils.abm_articulos_reglas import (
    filtrar_descripciones_talle,
    filtrar_edades,
    filtrar_siluetas,
    tipo_prefijo,
    tipo_texto_talle,
    valor_sugerido,
)

# Carga variables de entorno desde .env si existe
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# BACKEND_URL: prioridad → .env local > Streamlit Secrets > default localhost
# Orden de resolución:
#   1. Variable de entorno / archivo .env  (dev local, servidor)
#   2. st.secrets                          (Streamlit Cloud)
#   3. http://localhost:5000               (fallback)
_backend_from_env = os.getenv("BACKEND_URL")
try:
    _backend_from_secrets = st.secrets.get("BACKEND_URL", None)
except Exception:
    # No hay secrets.toml (entorno local sin Streamlit Cloud)
    _backend_from_secrets = None
BACKEND_URL = (_backend_from_env or _backend_from_secrets or "http://localhost:5000").rstrip("/")
LOGGER = logging.getLogger("frontend.main_app")

# Header requerido por ngrok para que no bloquee requests automáticas
# (se ignora silenciosamente si el backend no usa ngrok)
NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(page_title="Sistema Conversor V2", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "static", "img")


def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


local_css(os.path.join(BASE_DIR, "static", "css", "custom_style.css"))


def get_img(name):
    return os.path.join(IMG_DIR, name)


def _render_error_details(error: Exception) -> None:
    """Muestra detalles utiles cuando Streamlit captura un error no manejado."""
    st.error("El frontend no pudo renderizarse correctamente.")
    st.exception(error)

    with st.expander("Detalles tecnicos", expanded=True):
        st.code("".join(traceback.format_exception(type(error), error, error.__traceback__)), language="python")
        st.write(
            {
                "backend_url": BACKEND_URL,
                "python": sys.version,
                "platform": platform.platform(),
                "working_directory": os.getcwd(),
                "frontend_directory": BASE_DIR,
            }
        )


# ── Catálogo de proveedores ───────────────────────────────────────────────────
# Para agregar un nuevo proveedor: una sola línea aquí y está listo.
PROVIDERS = {
    # Pedido Proveedor
    "adidas":           {"name": "Adidas",      "logo": "logo_adida.png",       "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "bestsox":          {"name": "Best Sox",    "logo": "logo_bestsox.png",     "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "braku":            {"name": "Braku",       "logo": "logo_braku.png",       "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "diadora":          {"name": "Diadora",     "logo": "logo_G7.png",          "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "johnfoos":         {"name": "John Foos",   "logo": "logo_johnfoos.png",    "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "kdy":              {"name": "Kdy",         "logo": "logo_kdy.png",         "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "kosiuko":          {"name": "Kosiuko",     "logo": "logo_kosiuko.png",     "cat": "Pedido Proveedor",   "ext": ".txt"},
    "leuru":            {"name": "Leuru",       "logo": "logo_leuru.png",       "cat": "Pedido Proveedor",   "ext": ".txt"},
    "procer":           {"name": "Procer",      "logo": "logo_procer.png",      "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "proyec":           {"name": "Proyec",      "logo": "logo_proyec.png",      "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "puma":             {"name": "Puma",        "logo": "logo_puma.png",        "cat": "Pedido Proveedor",   "ext": ".csv"},
    "saucony":          {"name": "Saucony",     "logo": "logo_saucony.png",     "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    "topper":           {"name": "Topper",      "logo": "logo_topper.png",      "cat": "Pedido Proveedor",   "ext": ".txt"},
    "winar":            {"name": "Winar",       "logo": "logo_winar.png",       "cat": "Pedido Proveedor",   "ext": ".xlsx"},
    # Propuesta de Compra
    "adidas_propuesta": {"name": "Adidas",      "logo": "logo_adida.png",       "cat": "Propuesta de Compra","ext": ".xlsx"},
    "nike":             {"name": "Nike",        "logo": "logo_nike.png",        "cat": "Propuesta de Compra","ext": ".xlsx"},
    "puma_propuesta":   {"name": "Puma",        "logo": "logo_puma.png",        "cat": "Propuesta de Compra","ext": ".xlsx"},
    "topper_propuesta": {"name": "Topper",      "logo": "logo_topper.png",      "cat": "Propuesta de Compra","ext": ".xlsx"},
    # Procesos Especiales
    "arca":             {"name": "ARCA",        "logo": "logo_arca.png",        "cat": "Procesos Especiales","ext": ".xlsx"},
    "gastos":           {"name": "Gastos",      "logo": "logo_gastos.png",      "cat": "Procesos Especiales","ext": ".xlsx"},
    "mayorista":        {"name": "Mayorista",   "logo": "logo_mayorista.png",   "cat": "Procesos Especiales","ext": ".xlsx"},
    "sevillanita":      {"name": "Sevillanita", "logo": "logo_sevillanita.png", "cat": "Procesos Especiales","ext": ".xlsx"},
}

def _api_get(path: str, params=None) -> dict:
    res = requests.get(f"{BACKEND_URL}{path}", params=params, headers=NGROK_HEADERS, timeout=20)
    res.raise_for_status()
    return res.json()


def _api_post(path: str, payload=None) -> dict:
    res = requests.post(f"{BACKEND_URL}{path}", json=payload or {}, headers=NGROK_HEADERS, timeout=300)
    if res.status_code >= 400:
        try:
            detail = res.json()
            message = detail.get("error") or res.text
        except Exception:
            message = res.text
        raise RuntimeError(f"{res.status_code} {res.reason}: {message}")
    return res.json()


def _api_delete(path: str) -> dict:
    res = requests.delete(f"{BACKEND_URL}{path}", headers=NGROK_HEADERS, timeout=60)
    if res.status_code >= 400:
        try:
            detail = res.json()
            message = detail.get("error") or res.text
        except Exception:
            message = res.text
        raise RuntimeError(f"{res.status_code} {res.reason}: {message}")
    return res.json()


def _api_delete_json(path: str, payload=None) -> dict:
    res = requests.delete(f"{BACKEND_URL}{path}", json=payload or {}, headers=NGROK_HEADERS, timeout=60)
    if res.status_code >= 400:
        try:
            detail = res.json()
            message = detail.get("error") or res.text
        except Exception:
            message = res.text
        raise RuntimeError(f"{res.status_code} {res.reason}: {message}")
    return res.json()


def _api_put(path: str, payload=None) -> dict:
    res = requests.put(f"{BACKEND_URL}{path}", json=payload or {}, headers=NGROK_HEADERS, timeout=60)
    if res.status_code >= 400:
        try:
            detail = res.json()
            message = detail.get("error") or res.text
        except Exception:
            message = res.text
        raise RuntimeError(f"{res.status_code} {res.reason}: {message}")
    return res.json()


@st.cache_data(ttl=60, show_spinner=False)
def _load_abm_catalogos() -> dict:
    return _api_get("/api/abm-articulos/catalogos")


def _get_abm_lote_uuid():
    try:
        query_lote = st.query_params.get("abm_lote")
    except Exception:
        query_lote = None
    if query_lote:
        st.session_state["abm_lote_uuid"] = str(query_lote)
    if "abm_lote_uuid" not in st.session_state:
        st.session_state["abm_lote_uuid"] = str(uuid.uuid4())
        try:
            st.query_params["abm_lote"] = st.session_state["abm_lote_uuid"]
        except Exception:
            pass
    return st.session_state["abm_lote_uuid"]


def _reset_abm_lote_uuid():
    st.session_state["abm_lote_uuid"] = str(uuid.uuid4())
    try:
        st.query_params["abm_lote"] = st.session_state["abm_lote_uuid"]
    except Exception:
        pass


def _with_abm_lote(payload=None):
    data = dict(payload or {})
    data["lote_uuid"] = _get_abm_lote_uuid()
    return data


@st.cache_data(ttl=15, show_spinner=False)
def _load_abm_borradores(lote_uuid: str) -> list:
    return _api_get("/api/abm-articulos/borradores", params={"lote_uuid": lote_uuid}).get("items", [])


@st.cache_data(ttl=15, show_spinner=False)
def _load_abm_complementarios(lote_uuid: str) -> list:
    return _api_get("/api/abm-articulos/complementarios", params={"lote_uuid": lote_uuid}).get("items", [])


@st.cache_data(ttl=300, show_spinner=False)
def _load_abm_config(modulo: str) -> list:
    return _api_get(f"/api/abm-articulos/config/{modulo}").get("items", [])


def _refresh_abm_config(modulo: str):
    _load_abm_config.clear()
    _load_abm_catalogos.clear()
    st.session_state.pop(f"abm_config_{modulo}_edit", None)
    st.session_state.pop(f"abm_config_{modulo}_confirm", None)
    st.session_state.pop(f"abm_config_{modulo}_dialog", None)
    st.session_state.pop(f"abm_config_{modulo}_modal_payload", None)


def _reload_abm_listados():
    _load_abm_borradores.clear()
    _load_abm_complementarios.clear()
    lote_uuid = _get_abm_lote_uuid()
    st.session_state["abm_borradores_items"] = _load_abm_borradores(lote_uuid)
    st.session_state["abm_complementarios_items"] = _load_abm_complementarios(lote_uuid)


def _ensure_abm_listados_loaded():
    if "abm_borradores_items" not in st.session_state or "abm_complementarios_items" not in st.session_state:
        _reload_abm_listados()


def _refresh_abm_listados():
    _reload_abm_listados()


def _abm_selected_id(item):
    return (item or {}).get("id") if isinstance(item, dict) else item


def _clear_session_keys(*keys):
    for key in keys:
        st.session_state.pop(key, None)


def _auto_download(content, filename, mime):
    data = base64.b64encode(content).decode("ascii")
    filename_safe = html.escape(filename or "download", quote=True)
    mime_safe = html.escape(mime or "application/octet-stream", quote=True)
    components.html(
        f"""
        <html>
          <body>
            <a id="download-link" download="{filename_safe}" href="data:{mime_safe};base64,{data}"></a>
            <script>
              document.getElementById("download-link").click();
            </script>
          </body>
        </html>
        """,
        height=0,
    )


def _api_post_file(path: str, file, data=None) -> dict:
    res = requests.post(
        f"{BACKEND_URL}{path}",
        files={"file": (file.name, file.getvalue())},
        data=data or {},
        headers=NGROK_HEADERS,
        timeout=300,
    )
    if res.status_code >= 400:
        try:
            detail = res.json()
            message = detail.get("error") or res.text
        except Exception:
            message = res.text
        raise RuntimeError(f"{res.status_code} {res.reason}: {message}")
    return res.json()


def _render_auditoria_logistica() -> None:
    st.subheader("Control de Cumplimiento Logístico")

    # Diccionario de mapeo UX/UI para nombres humanos de meses
    MAPEO_MESES = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }
    
    anios_lista = [2025, 2026, 2027]
    mes_actual_num = datetime.now().strftime("%m")
    anio_actual = datetime.now().year

    if st.button("Limpiar filtros"):
        st.session_state["aud_empresa"] = ""
        st.session_state["aud_mes_nombre"] = MAPEO_MESES[mes_actual_num]
        st.session_state["aud_anio_sel"] = anio_actual
        st.session_state["aud_proveedor"] = ""
        st.session_state["aud_marca"] = ""
        st.session_state["aud_estado"] = ""
        st.session_state["aud_show_results"] = False
        st.rerun()

    # ── Horizonte Global de Control ───────────────────────────────────────────
    st.markdown("### 🗓️ Horizonte Global de Análisis")
    top_col1, top_col2, top_col3, top_col4 = st.columns([1, 1, 1, 1.5])
    
    empresa = top_col1.selectbox(
        "Empresa",
        ["", "002", "001"],
        format_func=lambda value: {"": "Ambas", "002": "Marathon", "001": "Blanco"}.get(value, value),
        key="aud_empresa",
    )
    
    # Cambio UX/UI: Muestra nombres de meses, pero guarda la selección amigable
    lista_nombres_meses = list(MAPEO_MESES.values())
    mes_nombre_sel = top_col2.selectbox(
        "Mes Planificado", 
        lista_nombres_meses, 
        index=lista_nombres_meses.index(MAPEO_MESES[mes_actual_num]),
        key="aud_mes_nombre"
    )
    
    anio_sel = top_col3.selectbox(
        "Año Planificado", 
        anios_lista, 
        index=anios_lista.index(anio_actual) if anio_actual in anios_lista else 1,
        key="aud_anio_sel"
    )

    # Recuperamos el número del mes a partir de su nombre para armar las llaves de la API
    mes_num_clave = [k for k, v in MAPEO_MESES.items() if v == mes_nombre_sel][0]
    mes_api = f"{anio_sel}-{mes_num_clave}"       # "2026-03" -> Entiende el backend
    mes_pantalla = f"{mes_nombre_sel} {anio_sel}" # "Marzo 2026" -> Entiende el humano

    with top_col4:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("Sincronizar CEGID", type="primary", width="stretch"):
            with st.spinner(f"Sincronizando {mes_pantalla} desde el ERP..."):
                try:
                    # FIX: Enviamos la clave exacta 'mes_target' esperada por la API corregida
                    result = _api_post(
                        "/api/auditoria/sync/cegid",
                        {
                            "mes_target": mes_api,
                            "souche": empresa or None
                        },
                    )
                    st.success(f"Sincronización Exitosa: {result.get('documentos', 0)} documentos y {result.get('lineas', 0)} líneas impactadas.")
                    st.session_state["aud_show_results"] = False
                except Exception as e:
                    st.error(f"No se pudo sincronizar con el ERP: {e}")

    st.divider()
    
    # ── Filtros Secundarios de Búsqueda ───────────────────────────────────────
    st.markdown("### 🔍 Filtros de Búsqueda")
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
    proveedor = f1.text_input("Proveedor", placeholder="Ej: ADIDA", key="aud_proveedor").strip() or None
    marca = f2.text_input("Marca", placeholder="Ej: ADIDAS", key="aud_marca").strip() or None
    estado = f3.selectbox(
        "Estado Logístico",
        ["", "OK_COMPLETO", "PARCIAL", "NO_RECIBIDO", "DEMORADO_COMPLETO"],
        format_func=lambda value: "Todos" if value == "" else value,
        key="aud_estado",
    ) or None
    
    with f4:
        st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("Consultar Plan vs Realidad", type="secondary", width="stretch"):
            st.session_state["aud_show_results"] = True

    if not st.session_state.get("aud_show_results", False):
        st.info(f"Seleccioná el Horizonte Temporal superior y aplicá los filtros para auditar la mercadería.")
        return

    # ── Ingesta de Datos desde el Backend ─────────────────────────────────────
    try:
        plan_data = _api_get(
            "/api/auditoria/plan-vs-recepcion",
            params={
                "proveedor": proveedor,
                "marca": marca,
                "mes": mes_api,
                "souche": empresa or None,
            },
        )
        plan_items = plan_data.get("items", [])
    except Exception as e:
        st.error(f"Error al conectar con el motor de conciliación: {e}")
        return

    if not plan_items:
        st.warning(f"No se registran datos de planificación para {mes_pantalla}.")
        return

    df_plan = pd.DataFrame(plan_items)
    if estado:
        df_plan = df_plan[df_plan["estado"] == estado]

    if df_plan.empty:
        st.warning("No se encontraron registros que coincidan con el Estado Logístico seleccionado.")
        return

    # ── KPIs de Abastecimiento ────────────────────────────────────────────────
    total_pedido = df_plan["cantidad_pedida"].sum()
    total_recibido = df_plan["cantidad_recibida"].sum()
    unidades_pendientes = max(total_pedido - total_recibido, 0)
    
    concluidos = int(df_plan["estado"].isin(["OK_COMPLETO", "DEMORADO_COMPLETO"]).sum())
    fill_rate_items = round((concluidos / len(df_plan) * 100), 2) if len(df_plan) else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Items Concluidos (SLA)", f"{fill_rate_items}%")
    k2.metric("Total Pedido (DEF)", f"{total_pedido:,.0f} u.")
    k3.metric("Total Entrado (BLF)", f"{total_recibido:,.0f} u.")
    k4.metric("Unidades Pendientes", f"{unidades_pendientes:,.0f} u.")

    st.divider()

    # ── Estructuración de Vistas Logísticas ────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📊 Comparativo DEF vs BLF", 
        "🚚 Línea de Tiempo por Artículo", 
        "🗓️ Análisis de Recepciones Posteriores"
    ])

    # PESTAÑA 1: Grilla General
    with tab1:
        st.markdown(f"### Cumplimiento de Stock — {mes_pantalla}")
        columnas_plan = [
            "mes_planificado", "proveedor", "marca", "codigo_articulo", "descripcion", 
            "talle", "cantidad_pedida", "cantidad_recibida", "diferencia", "cumplimiento", "estado"
        ]
        st.dataframe(
            df_plan[columnas_plan],
            width="stretch",
            hide_index=True,
            column_config={
                "mes_planificado": st.column_config.TextColumn("Horizonte"),
                "descripcion": st.column_config.TextColumn("Descripción del Artículo"),
                "cantidad_pedida": st.column_config.NumberColumn("Pedida (DEF)", format="%d u."),
                "cantidad_recibida": st.column_config.NumberColumn("Recibida (BLF)", format="%d u."),
                "diferencia": st.column_config.NumberColumn("Diferencia", format="%d u."),
                "cumplimiento": st.column_config.NumberColumn("Cumplimiento", format="%.2f %%"),
                "estado": st.column_config.TextColumn("Estado")
            }
        )

    # PESTAÑA 2: Curva Completa de Talles
    with tab2:
        st.markdown("### Historial de Entregas por Artículo")
        articulos_disponibles = sorted(df_plan["codigo_articulo"].unique())
        articulo_sel = st.selectbox("Seleccionar Código de Artículo para ver su curva", [""] + list(articulos_disponibles), key="sel_art_timeline")

        if articulo_sel:
            df_curva = df_plan[df_plan["codigo_articulo"] == articulo_sel]
            desc_articulo = df_curva["descripcion"].iloc[0] if not df_curva.empty else ""

            st.markdown(f"**Trazabilidad de Remitos para:** `{articulo_sel}` — *{desc_articulo}*")
            
            historial_consolidado = []
            for _, fila_talle in df_curva.iterrows():
                talle_actual = fila_talle["talle"]
                historial_lote = fila_talle.get("historial_detalle", [])
                for ingreso in historial_lote:
                    ingreso_con_talle = ingreso.copy()
                    ingreso_con_talle["talle"] = talle_actual
                    historial_consolidado.append(ingreso_con_talle)

            if not historial_consolidado:
                st.error("❌ Faltante Absoluto: Este artículo no registra ningún ingreso físico en el depósito para ninguno de sus talles.")
            else:
                df_historial = pd.DataFrame(historial_consolidado)
                df_historial = df_historial.sort_values(by=["talle", "fecha_ingreso"])
                
                # REFACTOR: Seleccionamos estrictamente las columnas esenciales eliminando la redundancia numérica
                columnas_curva_limpia = [
                    "talle", "comprobante", "fecha_ingreso", "cantidad_ingresada", "etiqueta_tiempo"
                ]
                
                st.dataframe(
                    df_historial[columnas_curva_limpia],
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "talle": st.column_config.TextColumn("Talle"),
                        "comprobante": st.column_config.TextColumn("Remito (BLF)"),
                        "fecha_ingreso": st.column_config.TextColumn("Fecha Entrada"),
                        "cantidad_ingresada": st.column_config.NumberColumn("Cantidad Recibida", format="%d u."),
                        # "dias_desvio": st.column_config.NumberColumn("Desfase (Meses)"),
                        "etiqueta_tiempo": st.column_config.TextColumn("Estado SLA")
                    }
                )

    # PESTAÑA 3: Rezagos
    with tab3:
        st.markdown(f"### Mercadería Planificada para {mes_pantalla} que llegó en meses posteriores")
        try:
            posteriores_data = _api_get(
                "/api/auditoria/def/recepciones-posteriores",
                params={
                    "proveedor": proveedor,
                    "marca": marca,
                    "mes": mes_api,
                    "souche": empresa or None,
                },
            )
            posteriores_items = posteriores_data.get("items", [])
        except Exception as e:
            st.error(f"No se pudo consultar el reporte de entregas tardías: {e}")
            return

        if not posteriores_items:
            st.success(f"✨ ¡Operación Limpia! No se registran ingresos fuera de término para las propuestas de {mes_pantalla}.")
        else:
            df_post = pd.DataFrame(posteriores_items)
            columnas_post = [
                "codigo_articulo", "descripcion", "talle", "mes_planificado", 
                "cantidad_pedida_def", "comprobante_blf", "fecha_recepcion_real", 
                "cantidad_recibida_blf", "meses_desvio", "estado_entrega"
            ]
            st.dataframe(
                df_post[columnas_post],
                width="stretch",
                hide_index=True,
                column_config={
                    "mes_planificado": st.column_config.TextColumn("Horizonte Orig."),
                    "descripcion": st.column_config.TextColumn("Descripción del Artículo"),
                    "cantidad_pedida_def": st.column_config.NumberColumn("Pedida Original", format="%d u."),
                    "cantidad_recibida_blf": st.column_config.NumberColumn("Ingresado en Lote", format="%d u."),
                    "fecha_recepcion_real": st.column_config.TextColumn("Fecha de Llegada"),
                    "estado_entrega": st.column_config.TextColumn("Estado Recibo")
                }
            )
# ── Función reutilizable para mostrar resultados de auditoría ─────────────────
def _render_audit_results(data: dict) -> None:
    """Muestra los resultados de auditoría y el botón de descarga."""
    if data.get("status") != "success" or not data.get("download_url") or not data.get("filename"):
        st.error(data.get("message") or data.get("error") or "No se pudo generar un archivo descargable.")
        return

    audit = data.get("audit", {})
    has_audit = data.get("has_audit", False)

    st.toast("¡Archivo procesado!", icon="✅")

    if data.get("message"):
        st.info(data["message"])

    if has_audit:
        # Faltantes en CEGID
        if audit.get('faltantes'):
            df_faltantes = pd.DataFrame(audit['faltantes'])
            modelos_unicos = df_faltantes['Material'].nunique()
            st.error(f"🚨 Debes crear {modelos_unicos} Modelo(s) nuevo(s) en CEGID")
            with st.expander("Ver detalle de talles a crear", expanded=True):
                st.dataframe(df_faltantes.sort_values(by=["Material", "Size"]), width="stretch")

        # EANs nuevos a vincular
        if audit.get("actualizar_ean"):
            modelos_ean = pd.DataFrame(audit["actualizar_ean"])['articulo'].nunique()
            st.info(f"⚠️ Hay {modelos_ean} Modelo(s) con EANs nuevos.")
            with st.expander("Ver talles a vincular"):
                st.dataframe(pd.DataFrame(audit["actualizar_ean"]), width="stretch")

        # Variaciones de precio
        if audit.get('cambios_precio'):
            st.warning(f"📊 Se detectaron {len(audit['cambios_precio'])} variaciones de precio.")
            with st.expander("🔍 Revisar Resumen de Precios por Modelo"):
                df_precios = pd.DataFrame(audit['cambios_precio']).copy()
                columnas = [
                    "articulo_cegid",
                    "descripcion",
                    "precio_cegid",
                    "precio_prov",
                    "variacion_porcentaje",
                ]
                df_precios = df_precios[[c for c in columnas if c in df_precios.columns]]
                df_precios = df_precios.rename(columns={"articulo_cegid": "Articulo_cegid"})
                df_precios["precio_cegid"] = df_precios["precio_cegid"].map("${:,.2f}".format)
                df_precios["precio_prov"] = df_precios["precio_prov"].map("${:,.2f}".format)
                df_precios["variacion_porcentaje"] = df_precios["variacion_porcentaje"].map("{:.2f}%".format)
                st.dataframe(df_precios, width="stretch")
        elif not audit.get("sevillanita"):
            st.success("No hay variaciones de precio respecto a CEGID.")

        if audit.get("alertas_promos"):
            df_promos = pd.DataFrame(audit["alertas_promos"])
            articulos_promo = df_promos["Articulo"].nunique() if "Articulo" in df_promos.columns else len(df_promos)
            st.warning(f"Se detectaron {articulos_promo} artículo(s) con promo activa en CEGID.")
            with st.expander("Ver artículos con promo activa", expanded=True):
                st.dataframe(df_promos, width="stretch")
        elif audit.get("articulos_promos_chequeados"):
            df_promos_ok = pd.DataFrame(audit["articulos_promos_chequeados"])
            st.info("Todos los articulos chequeados tienen promo N/A.")
            with st.expander("Ver articulos chequeados por promo"):
                st.dataframe(df_promos_ok.drop_duplicates(subset=["Articulo"]), width="stretch")

    if audit.get("campos_requeridos_vacios"):
        df_requeridos = pd.DataFrame(audit["campos_requeridos_vacios"])
        st.warning(f"⚠️ Se encontraron {len(df_requeridos)} fila(s) con campos requeridos vacíos.")
        with st.expander("Ver campos requeridos vacíos", expanded=True):
            st.dataframe(df_requeridos, width="stretch")

    if audit.get("codigos_barras_no_encontrados"):
        df_sin_barras = pd.DataFrame(audit["codigos_barras_no_encontrados"])
        st.error(f"🚨 No se pudo encontrar código de barras para {len(df_sin_barras)} artículo(s).")
        with st.expander("Ver artículos sin código de barras en CEGID", expanded=True):
            st.dataframe(df_sin_barras, width="stretch")

    if audit.get("codigos_barras_completados"):
        df_barras_completadas = pd.DataFrame(audit["codigos_barras_completados"])
        st.info(f"Se completaron {len(df_barras_completadas)} EAN único(s) desde CEGID.")
        with st.expander("Ver EAN completados desde CEGID"):
            st.dataframe(df_barras_completadas, width="stretch")

    # Conflictos de Suc (común a todos)
    if audit.get('conflictos_suc'):
        df_conflictos = pd.DataFrame(audit['conflictos_suc'])
        remitos = df_conflictos['Remito'].nunique() if 'Remito' in df_conflictos.columns else '?'
        st.error(f"🚨 ¡ATENCIÓN! {remitos} remito(s) tienen líneas con distinto valor de **Suc**.")
        with st.expander("🔍 Ver líneas con Suc inconsistente", expanded=True):
            if 'Remito' in df_conflictos.columns:
                df_conflictos = df_conflictos.sort_values(by='Remito')
            st.dataframe(df_conflictos, width="stretch")

    if audit.get("alertas_sucursales"):
        df_alertas = pd.DataFrame(audit["alertas_sucursales"])
        st.error(
            f"🚨 Se detectaron {df_alertas['Suc'].nunique() if 'Suc' in df_alertas.columns else len(df_alertas)} "
            "sucursal(es) que no existen en la base de datos."
        )
        with st.expander("🔍 Ver sucursales inexistentes", expanded=True):
            st.dataframe(df_alertas, width="stretch")

    if audit.get("avisos_sucursales"):
        df_avisos = pd.DataFrame(audit["avisos_sucursales"])
        st.info(
            f"ℹ️ Se encontraron {df_avisos['Suc'].nunique() if 'Suc' in df_avisos.columns else len(df_avisos)} "
            "línea(s) con sucursal por defecto (240001)."
        )
        with st.expander("🔍 Ver líneas con sucursal por defecto"):
            st.dataframe(df_avisos, width="stretch")

    # Botón de descarga (común a todos)
    for aviso in audit.get("avisos_generales", []):
        if aviso != data.get("message"):
            if aviso == "Todos los articulos chequeados tienen promo N/A." and audit.get("articulos_promos_chequeados"):
                continue
            st.info(aviso)

    sevillanita = audit.get("sevillanita", {})
    if sevillanita:
        resumen = sevillanita.get("resumen", {})
        st.warning(
            "Alertas Sevillanita: "
            f"{resumen.get('sin_match', 0)} sin match, "
            f"{resumen.get('mas_1000kg', 0)} con +1000kg, "
            f"{resumen.get('sin_valor_declarado', 0)} sin valor declarado, "
            f"{resumen.get('diferencias_importe', 0)} con diferencias de importe."
        )
        filas = sevillanita.get("filas", [])
        if filas:
            df_sevillanita = pd.DataFrame(filas)
            st.dataframe(df_sevillanita, width="stretch")

    download_res = requests.get(data["download_url"], stream=True, headers=NGROK_HEADERS)
    if download_res.status_code == 200:
        filename = data["filename"]
        if filename.endswith(".zip"):
            mime = "application/zip"
        elif filename.endswith(".xlsx"):
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            mime = "text/csv"
        st.download_button(
            label="⬇️ Descargar Archivo",
            data=download_res.content,
            file_name=filename,
            mime=mime,
            width="stretch",
        )
    else:
        try:
            payload = download_res.json()
        except ValueError:
            payload = {}
        mensaje = payload.get("message") or payload.get("error")
        if mensaje:
            st.error(mensaje)
        else:
            st.error(
                "No se pudo preparar la descarga porque el archivo generado no está disponible. "
                "Probá procesarlo nuevamente o avisá a sistemas para revisar la carpeta de salida."
            )


def _render_process_error(res: requests.Response) -> None:
    try:
        payload = res.json()
    except ValueError:
        payload = {}

    mensaje = payload.get("message") or payload.get("error")
    if mensaje:
        st.error(mensaje)
    else:
        st.error("No se pudo procesar el archivo. Revisá que sea el archivo correcto para este proveedor.")


def _render_provider_card(id_p: str, info: dict) -> None:
    """Renderiza la tarjeta de un proveedor con uploader y lógica de procesamiento."""
    with st.container(border=True):
        st.image(get_img(info["logo"]), width='stretch')
        st.subheader(info["name"], divider="blue")

        if id_p == "sevillanita":
            with st.expander(f"Utilizar {info['name']}"):
                st.caption("Tipo de archivo: dos .xlsx")
                files = st.file_uploader(
                    "Seleccionar archivos",
                    type=["xlsx"],
                    accept_multiple_files=True,
                    key=id_p,
                    label_visibility="collapsed",
                )
                st.caption("Subí el archivo de despachos y el Excel de facturación Sevillanita.")

            if files and st.button(f"Procesar {info['name']}", key=f"btn_{id_p}", type="primary", width="stretch"):
                if len(files) != 2:
                    st.warning("Seleccioná exactamente dos archivos .xlsx para Sevillanita.")
                    return
                with st.spinner("Trabajando..."):
                    try:
                        upload_files = [
                            ("files", (uploaded.name, uploaded.getvalue()))
                            for uploaded in files
                        ]
                        res = requests.post(
                            f"{BACKEND_URL}/api/process/{id_p}",
                            files=upload_files,
                            headers=NGROK_HEADERS,
                        )
                        if res.status_code == 200:
                            _render_audit_results(res.json())
                        else:
                            _render_process_error(res)
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")
            return

        with st.expander(f"Utilizar {info['name']}"):
            st.caption(f"Tipo de archivo: {info['ext']}")
            file = st.file_uploader(
                "⬆️ Seleccionar archivo",
                key=id_p,
                label_visibility="collapsed",
            )

        if file:
            if st.button(f"Procesar {info['name']}", key=f"btn_{id_p}", type="primary", width="stretch"):
                with st.spinner("⏳ Trabajando..."):
                    try:
                        res = requests.post(
                            f"{BACKEND_URL}/api/process/{id_p}",
                            files={"file": (file.name, file.getvalue())},
                            headers=NGROK_HEADERS,
                        )
                        if res.status_code == 200:
                            _render_audit_results(res.json())
                        else:
                            _render_process_error(res)
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")


def _render_sync_novedades_panel() -> None:
    with st.container(border=True):
        st.subheader("Sync NOVEDADES - Logistica", divider="blue")
        c1, c2 = st.columns([3, 1])
        novedades_file = c1.file_uploader(
            "Seleccionar archivo",
            type=["xlsx", "xls"],
            key="sync_novedades_file",
            label_visibility="collapsed",
        )
        dry_run = c2.toggle("Run-simulation", value=True, help="Simula la corrida sin escribir en Google Sheets.")

        if st.button("Ejecutar sync NOVEDADES", type="primary", width="stretch"):
            if not novedades_file:
                st.warning("Seleccioná el Excel exportado de la app logística para continuar.")
                return
            with st.spinner("Sincronizando NOVEDADES..."):
                try:
                    result = _api_post_file(
                        "/api/procesos-especiales/sync-novedades",
                        novedades_file,
                        data={"dry_run": str(dry_run).lower()},
                    )
                    st.success(
                        f"Corrida finalizada: {result.get('matched_rows', 0)} matches, "
                        f"{result.get('completed_ok', 0)} filas OK, {len(result.get('conflicts', []))} conflictos."
                    )
                    if result.get("updates"):
                        title = "Celdas que se escribirian" if dry_run else "Celdas actualizadas"
                        st.info(f"{title}: {len(result['updates'])}")
                        st.dataframe(pd.DataFrame(result["updates"]), width="stretch")
                    if result.get("unresolved_providers"):
                        st.warning("Hay proveedores sin resolver.")
                        st.dataframe(pd.DataFrame(result["unresolved_providers"]), width="stretch")
                    if result.get("conflicts"):
                        st.warning("Hay datos previos distintos no sobreescritos.")
                        st.dataframe(pd.DataFrame(result["conflicts"]), width="stretch")
                    if result.get("inconsistencies"):
                        st.warning("Hay inconsistencias de cruce.")
                        st.dataframe(pd.DataFrame(result["inconsistencies"]), width="stretch")
                    if result.get("fuzzy_matches"):
                        st.info("Matches fuzzy auditados para revision.")
                        st.dataframe(pd.DataFrame(result["fuzzy_matches"]), width="stretch")
                    if result.get("technical_errors"):
                        st.error("Hubo errores tecnicos.")
                        st.dataframe(pd.DataFrame({"error": result["technical_errors"]}), width="stretch")
                except Exception as e:
                    st.error(f"No se pudo ejecutar la sincronizacion: {e}")


def _label(item):
    if not item:
        return ""
    return item.get("descripcion") or item.get("label") or ""


def _label_codigo(item):
    if not item:
        return ""
    return item.get("codigo") or ""


def _selected_payload(item, codigo_key, descripcion_key):
    item = item or {}
    return {codigo_key: item.get("codigo", ""), descripcion_key: item.get("descripcion", "")}


def _dedupe_descripciones(items):
    seen = set()
    values = []
    for item in items:
        descripcion = (item.get("descripcion") or "").strip()
        if descripcion and descripcion not in seen:
            values.append(descripcion)
            seen.add(descripcion)
    return sorted(values)


def _tipo_prefijo(tipo_sel):
    return tipo_prefijo(tipo_sel)


def _tipo_texto_talle(tipo_sel):
    return tipo_texto_talle(tipo_sel)


def _default_index(items, terms, allow_none=True):
    options = ([None] if allow_none else []) + list(items)
    terms_norm = [t.upper() for t in terms]
    for idx, item in enumerate(options):
        if not item:
            continue
        text = f"{item.get('codigo', '')} {item.get('descripcion', '')} {item.get('label', '')}".upper()
        if any(term in text for term in terms_norm):
            return idx
    return 0


def _default_index_descripcion_exacta(items, descripcion, allow_none=True):
    options = ([None] if allow_none else []) + list(items)
    descripcion_norm = str(descripcion or "").strip().upper()
    for idx, item in enumerate(options):
        if item and str(item.get("descripcion", "")).strip().upper() == descripcion_norm:
            return idx
    return 0


def _clear_abm_form_state(preserve=None):
    preserve = set(preserve or [])
    prefixes = ("abm_",)
    for key in list(st.session_state.keys()):
        if key.startswith(prefixes) and key not in preserve:
            st.session_state.pop(key, None)


def _finalizar_descarga_complementario(comp_ids):
    try:
        ids = [int(comp_id) for comp_id in (comp_ids or []) if comp_id is not None]
        if ids:
            _api_delete_json("/api/abm-articulos/complementarios", _with_abm_lote({"ids": ids}))
    except Exception as exc:
        st.session_state["abm_complementario_cleanup_error"] = str(exc)
    finally:
        _load_abm_complementarios.clear()
        _clear_abm_form_state(preserve={"abm_complementario_cleanup_error"})
        _reset_abm_lote_uuid()


def _color_talle_para_tipo(tipo_codigo, colores):
    mapping = {
        "ACC": "C01",
        "CAL": "C02",
        "IND": "C03",
        "MED": "C04",
        "BIC": "C05",
    }
    codigo_color = mapping.get((tipo_codigo or "").upper(), "C06")
    return next((c for c in colores if c.get("codigo") == codigo_color), None)


def _markup_para(marca_sel, tipo_sel, markups):
    marca_id = (marca_sel or {}).get("id")
    tipo_codigo = ((tipo_sel or {}).get("codigo") or "").lower()
    tipo_markup = "cal" if tipo_codigo == "cal" else "ind" if tipo_codigo == "ind" else "resto"
    candidatos = [m for m in markups if m.get("marca_id") == marca_id]
    exacto = next((m for m in candidatos if m.get("tipo") == tipo_markup), None)
    todo = next((m for m in candidatos if m.get("tipo") == "todo"), None)
    resto = next((m for m in candidatos if m.get("tipo") == "resto"), None)
    elegido = exacto or todo or resto
    return float((elegido or {}).get("markup") or 0)


def _redondear_a_999(valor):
    if not valor:
        return 0
    return int(math.ceil((float(valor) + 1) / 1000) * 1000 - 1)


def _siluetas_para_tipo(tipo_sel, siluetas):
    return filtrar_siluetas(tipo_sel, siluetas)


def _edades_para_tipo_genero(tipo_sel, genero_sel, edades):
    return filtrar_edades(tipo_sel, genero_sel, edades)


def _objetivos_para_tipo(tipo_sel, objetivos):
    prefijo = _tipo_prefijo(tipo_sel)
    if prefijo:
        filtrados = [
            o for o in objetivos
            if (o.get("descripcion") or "").upper().startswith(prefijo)
            or (o.get("codigo") or "").upper().startswith(prefijo)
        ]
        return filtrados or objetivos
    n_a = [o for o in objetivos if "N/A" in f"{o.get('codigo', '')} {o.get('descripcion', '')}".upper()]
    return n_a or objetivos[:1]


def _descripciones_talle_para_reglas(tipo_sel, edad_sel, genero_sel, marca_sel, talles):
    return filtrar_descripciones_talle(tipo_sel, edad_sel, genero_sel, marca_sel, talles)


def _dedupe_talles(talles):
    vistos = set()
    resultado = []
    for talle in talles:
        clave = (
            talle.get("descripcion") or "",
            talle.get("valorTalle") or "",
            talle.get("descripcionValorTalle") or "",
        )
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(talle)
    return resultado


def _talle_sort_key(talle):
    valor = str(talle.get("valorTalle") or "").strip().replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", valor)
    if match:
        return (0, float(match.group()), valor)
    return (1, valor.upper())


@st.fragment
def _render_abm_articulos() -> None:
    st.subheader("Alta de Articulos")
    try:
        catalogos = _load_abm_catalogos()
    except Exception as e:
        st.error(f"No se pudieron cargar los catalogos: {e}")
        return

    if st.session_state.pop("abm_limpiar_alta_basica", False):
        st.session_state["abm_codigo"] = ""
        st.session_state["abm_descripcion"] = ""
        st.session_state["abm_desc_talle"] = ""
        st.session_state["abm_codigos_pegados"] = ""
        _clear_session_keys(
            "abm_desc_talle_actual",
            "abm_talles_df",
            "abm_talles_editor_widget",
        )

    tipos = catalogos.get("tipos_producto", [])
    talles = catalogos.get("talles", [])
    colores = catalogos.get("colores", [])
    valores_genero = [
        {"codigo": "BEB", "descripcion": "BEBE"},
        {"codigo": "HOM", "descripcion": "HOMBRE"},
        {"codigo": "MUJ", "descripcion": "MUJER"},
        {"codigo": "NIÑ", "descripcion": "NIÑO"},
        {"codigo": "UNI", "descripcion": "UNISEX"},
    ]

    st.markdown("### Datos base")
    c1, c2 = st.columns(2)
    codigo = c1.text_input("Codigo", key="abm_codigo")
    descripcion = c2.text_input("Descripcion", key="abm_descripcion")

    c3, c4, c5 = st.columns(3)
    tipo_sel = c3.selectbox("Desc. Tipo de Producto", [None] + tipos, format_func=_label, key="abm_tipo")
    tipo_actual = _abm_selected_id(tipo_sel)
    if st.session_state.get("abm_tipo_actual") != tipo_actual:
        st.session_state["abm_tipo_actual"] = tipo_actual
        _clear_session_keys(
            "abm_edad",
            "abm_valor_genero",
            "abm_silueta",
            "abm_objetivo",
            "abm_valor_color",
            "abm_desc_talle",
            "abm_desc_talle_actual",
            "abm_talles_df",
            "abm_markup_source",
        )
    proveedor_sel = c4.selectbox("Proveedor Habitual", [None] + catalogos.get("proveedores", []), format_func=_label_codigo, key="abm_proveedor")
    proveedor_actual = _abm_selected_id(proveedor_sel)
    if st.session_state.get("abm_proveedor_actual") != proveedor_actual:
        st.session_state["abm_proveedor_actual"] = proveedor_actual
        _clear_session_keys("abm_marca", "abm_desc_talle", "abm_desc_talle_actual", "abm_talles_df")
    marcas_por_proveedor = catalogos.get("marcas_por_proveedor", {})
    proveedor_id = str((proveedor_sel or {}).get("id") or "")
    marcas_filtradas = marcas_por_proveedor.get(proveedor_id, []) if proveedor_id else []
    if st.session_state.get("abm_marca") not in ([None] + marcas_filtradas):
        st.session_state.pop("abm_marca", None)
    marca_sel = c5.selectbox("Desc. Marca", [None] + marcas_filtradas, format_func=_label, key="abm_marca")
    marca_actual = _abm_selected_id(marca_sel)
    if st.session_state.get("abm_marca_actual") != marca_actual:
        st.session_state["abm_marca_actual"] = marca_actual
        _clear_session_keys("abm_desc_talle", "abm_desc_talle_actual", "abm_talles_df", "abm_markup_source")
    if proveedor_sel and not marcas_filtradas:
        st.caption("Este proveedor no tiene marcas relacionadas cargadas.")

    capsulas = catalogos.get("capsulas", [])
    temporadas = catalogos.get("temporadas", [])
    materiales = catalogos.get("materiales", [])
    seg_proveedores = catalogos.get("segmentaciones_proveedor", [])
    seg_marathon = catalogos.get("segmentaciones_marathon", [])
    vidrieras = catalogos.get("vidrieras", [])
    divisiones = catalogos.get("divisiones", [])
    objetivos_filtrados = _objetivos_para_tipo(tipo_sel, catalogos.get("objetivos", []))

    c6, c7, c8 = st.columns(3)
    genero_sel = c6.selectbox("Desc. Genero", [None] + catalogos.get("generos", []), format_func=_label, key="abm_genero")
    genero_actual = _abm_selected_id(genero_sel)
    if st.session_state.get("abm_genero_actual") != genero_actual:
        st.session_state["abm_genero_actual"] = genero_actual
        _clear_session_keys("abm_edad", "abm_valor_genero", "abm_desc_talle", "abm_desc_talle_actual", "abm_talles_df")
    edades_filtradas = _edades_para_tipo_genero(tipo_sel, genero_sel, catalogos.get("edades", []))
    if st.session_state.get("abm_edad") not in ([None] + edades_filtradas):
        st.session_state.pop("abm_edad", None)
    edad_sel = c7.selectbox("Desc. Edad", [None] + edades_filtradas, format_func=_label, key="abm_edad")
    edad_actual = _abm_selected_id(edad_sel)
    if st.session_state.get("abm_edad_actual") != edad_actual:
        st.session_state["abm_edad_actual"] = edad_actual
        _clear_session_keys("abm_valor_genero", "abm_desc_talle", "abm_desc_talle_actual", "abm_talles_df")
    valor_sugerido_sel = valor_sugerido(genero_sel, edad_sel, valores_genero)
    if valor_sugerido_sel and st.session_state.get("abm_valor_genero") != valor_sugerido_sel:
        st.session_state["abm_valor_genero"] = valor_sugerido_sel
    valor_genero_sel = c8.selectbox("VALOR", [None] + valores_genero, format_func=_label, key="abm_valor_genero")

    c8a, c8b, c8c = st.columns(3)
    siluetas_filtradas = _siluetas_para_tipo(tipo_sel, catalogos.get("siluetas", []))
    silueta_sel = c8a.selectbox("Desc. Silueta", [None] + siluetas_filtradas, format_func=_label, key="abm_silueta")
    uso_sel = c8b.selectbox("Desc. Uso", [None] + catalogos.get("usos", []), format_func=_label, key="abm_uso")
    capsula_sel = c8c.selectbox("Desc. Capsula", [None] + capsulas, index=_default_index(capsulas, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_capsula")

    c9, c10, c11 = st.columns(3)
    division_sel = c9.selectbox(
        "Desc. Division",
        [None] + divisiones,
        index=_default_index_descripcion_exacta(divisiones, "MARATHON"),
        format_func=_label,
        key="abm_division",
    )
    temporada_sel = c10.selectbox("Desc. Temporada", [None] + temporadas, index=_default_index(temporadas, ["TODO EL AÑO"]), format_func=_label, key="abm_temporada")
    material_sel = c11.selectbox("Desc. Material", [None] + materiales, index=_default_index(materiales, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_material")

    c12, c13, c14 = st.columns(3)
    seg_prov_sel = c12.selectbox("Desc. Segmentacion Proveedor", [None] + seg_proveedores, index=_default_index(seg_proveedores, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_seg_prov")
    seg_marathon_sel = c13.selectbox("Desc. Segmentacion", [None] + seg_marathon, index=_default_index(seg_marathon, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_seg_marathon")
    vidriera_sel = c14.selectbox("Desc. Exhibicion", [None] + vidrieras, index=_default_index(vidrieras, ["N/A"]), format_func=_label, key="abm_vidriera")

    c15, c16, c17, c18 = st.columns(4)
    anio_sel = c15.selectbox("Desc. Año", [None] + catalogos.get("anios", []), format_func=_label, key="abm_anio")
    if st.session_state.get("abm_objetivo") not in ([None] + objetivos_filtrados):
        st.session_state.pop("abm_objetivo", None)
    objetivo_sel = c16.selectbox("Desc. Objetivo General", [None] + objetivos_filtrados, format_func=_label, key="abm_objetivo")
    color_talle = _color_talle_para_tipo((tipo_sel or {}).get("codigo"), colores)
    valores_color = [c for c in colores if not color_talle or c.get("codigo") == color_talle.get("codigo")]
    valor_color_sel = c17.selectbox("Desc. Color", [None] + valores_color, format_func=lambda item: "" if not item else item.get("descripcionValor", ""), key="abm_valor_color")
    c18.text_input("Desc. Color Talle", value=(color_talle or {}).get("descripcion", ""), disabled=True)

    p1, p2, p3 = st.columns(3)
    precio_compra = p1.number_input("Precio compra", min_value=0.0, step=0.01, format="%.2f", key="abm_precio_compra")
    markup_default = _markup_para(marca_sel, tipo_sel, catalogos.get("markups", []))
    markup_source = (marca_actual, tipo_actual)
    if st.session_state.get("abm_markup_source") != markup_source:
        st.session_state["abm_markup_source"] = markup_source
        st.session_state["abm_markup"] = float(markup_default or 0)
        st.session_state.pop("abm_precio_venta_source", None)
    markup_valor = p2.number_input("Markup", min_value=0.0, step=0.01, format="%.4f", key="abm_markup")
    precio_sugerido = round(precio_compra * markup_valor, 2) if markup_valor else 0.0
    precio_venta_default = _redondear_a_999(max(precio_sugerido, precio_compra + 1)) if precio_compra else 0
    precio_source = (float(precio_compra or 0), float(markup_valor or 0))
    if st.session_state.get("abm_precio_venta_source") != precio_source:
        st.session_state["abm_precio_venta_source"] = precio_source
        st.session_state["abm_precio_venta"] = int(precio_venta_default)
    precio_venta = p3.number_input(
        "Precio venta",
        min_value=0,
        step=1,
        format="%d",
        key="abm_precio_venta",
    )
    st.caption(f"Precio sugerido: {precio_sugerido:.2f}. Precio venta redondeado a 999: {precio_venta_default}.")
    if precio_compra and precio_venta <= precio_compra:
        st.warning("El precio de venta debe ser mayor al precio de compra.")

    campos_requeridos = {
        "Codigo": codigo,
        "Descripcion": descripcion,
        "Desc. Tipo de Producto": tipo_sel,
        "Desc. Marca": marca_sel,
        "Desc. Genero": genero_sel,
        "Desc. Edad": edad_sel,
        "VALOR": valor_genero_sel,
        "Desc. Silueta": silueta_sel,
        "Desc. Uso": uso_sel,
        "Desc. Capsula": capsula_sel,
        "Desc. Division": division_sel,
        "Desc. Temporada": temporada_sel,
        "Desc. Material": material_sel,
        "Desc. Segmentacion Proveedor": seg_prov_sel,
        "Desc. Segmentacion Marathon": seg_marathon_sel,
        "Desc. Exhibicion": vidriera_sel,
        "Desc. Anio": anio_sel,
        "Desc. Objetivo General": objetivo_sel,
        "Desc. Color Talle": color_talle,
        "Desc. Valor Color": valor_color_sel,
        "Proveedor Habitual": proveedor_sel,
        "Precio compra": precio_compra,
        "Precio venta": precio_venta,
    }
    campos_faltantes = [
        nombre for nombre, valor in campos_requeridos.items()
        if valor is None or (isinstance(valor, str) and not valor.strip()) or valor == 0
    ]
    guardar_deshabilitado = bool(campos_faltantes) or bool(precio_compra and precio_venta <= precio_compra)
    if campos_faltantes:
        st.caption("Completá todos los campos para habilitar Guardar borrador.")

    st.markdown("### Talles")
    descripciones_talle = _descripciones_talle_para_reglas(tipo_sel, edad_sel, genero_sel, marca_sel, talles)
    if st.session_state.get("abm_desc_talle") not in ([""] + descripciones_talle):
        st.session_state.pop("abm_desc_talle", None)
    desc_talle_sel = st.selectbox("Desc. Talle", [""] + descripciones_talle, key="abm_desc_talle")
    if st.session_state.get("abm_desc_talle_actual") != desc_talle_sel:
        st.session_state["abm_desc_talle_actual"] = desc_talle_sel
        st.session_state.pop("abm_talles_df", None)
    talles_filtrados = sorted(
        _dedupe_talles([t for t in talles if t.get("descripcion") == desc_talle_sel]),
        key=_talle_sort_key,
    )

    guardar_borrador_pressed = False
    if desc_talle_sel:
        rows = []
        for talle in talles_filtrados:
            rows.append({
                "id": talle.get("id"),
                "Seleccionar": False,
                "Descripcion": talle.get("descripcion", ""),
                "Talle": talle.get("valorTalle", ""),
                "Equiv": talle.get("descripcionValorTalle") or talle.get("valorTalle", ""),
                "codigoBarra": talle.get("codigoBarra", ""),
            })

        if "abm_talles_df" not in st.session_state:
            st.session_state["abm_talles_df"] = pd.DataFrame(rows)

        editor_source = st.session_state.get("abm_talles_df", pd.DataFrame(rows))
        editor_display = editor_source.set_index("id", drop=True) if "id" in editor_source.columns else editor_source
        with st.form("abm_talles_form"):
            codigos_pegados = st.text_area(
                "Pegar codigos de barra para talles seleccionados",
                key="abm_codigos_pegados",
                height=90,
                placeholder="Un codigo por linea. Se aplican solo a los talles seleccionados.",
            )
            ean_df = st.data_editor(
                editor_display,
                hide_index=True,
                width="stretch",
                disabled=["Descripcion", "Talle", "Equiv"],
                key="abm_talles_editor_widget",
            )
            tb1, tb2, tb3, tb4, tb5 = st.columns([1, 1, 1, 1, 1])
            with tb1:
                toggle_talles = st.form_submit_button("Seleccionar / deseleccionar", width="stretch", key="abm_talles_toggle_submit")
            with tb2:
                pegar_talles = st.form_submit_button("Pegar en seleccionados", width="stretch", key="abm_talles_paste_submit")
            with tb3:
                generar_talles = st.form_submit_button("Generar codigos temporales", width="stretch", key="abm_talles_generate_submit")
            with tb4:
                limpiar_talles = st.form_submit_button("Limpiar codigos de barras", width="stretch", key="abm_talles_clear_submit")
            with tb5:
                guardar_borrador_pressed = st.form_submit_button(
                    "Guardar borrador",
                    type="primary",
                    width="stretch",
                    disabled=guardar_deshabilitado,
                    key="abm_talles_save_draft_submit",
                )

        if "id" not in ean_df.columns:
            ean_df = ean_df.reset_index()
        if toggle_talles:
            nuevo_valor = not bool(ean_df["Seleccionar"].fillna(False).all()) if not ean_df.empty else True
            ean_df["Seleccionar"] = nuevo_valor
            st.session_state["abm_talles_df"] = ean_df
            st.rerun()
        if pegar_talles:
            mask = ean_df["Seleccionar"].fillna(False)
            codigos = [line.strip() for line in codigos_pegados.splitlines() if line.strip()]
            if not codigos:
                st.warning("Pegá al menos un codigo de barra.")
            elif not mask.any():
                st.warning("Selecciona al menos un talle para pegar codigos.")
            else:
                indices = ean_df.index[mask].tolist()
                for idx, codigo_barra in zip(indices, codigos):
                    ean_df.at[idx, "codigoBarra"] = codigo_barra
                st.session_state["abm_talles_df"] = ean_df
                st.rerun()
        if generar_talles:
            mask = ean_df["Seleccionar"].fillna(False)
            if not codigo:
                st.warning("Completa el codigo del articulo antes de generar codigos temporales.")
            elif not mask.any():
                st.warning("Selecciona al menos un talle para generar codigos temporales.")
            else:
                ean_df.loc[mask, "codigoBarra"] = ean_df.loc[mask, "Talle"].apply(lambda talle: f"T{codigo}{talle}")
                st.session_state["abm_talles_df"] = ean_df
                st.rerun()
        if limpiar_talles:
            mask = ean_df["Seleccionar"].fillna(False)
            if not mask.any():
                st.warning("Selecciona al menos un talle para limpiar codigos.")
            else:
                ean_df.loc[mask, "codigoBarra"] = ""
                st.session_state["abm_talles_df"] = ean_df
                st.rerun()
        if guardar_borrador_pressed:
            st.session_state["abm_talles_df"] = ean_df
    else:
        ean_df = pd.DataFrame()

    if guardar_borrador_pressed:
        if campos_faltantes:
            st.warning("Completá todos los campos antes de guardar el borrador.")
            return
        if not desc_talle_sel:
            st.warning("Selecciona una descripcion de talle.")
            return
        if precio_compra and precio_venta <= precio_compra:
            st.warning("El precio de venta debe ser mayor al precio de compra.")
            return

        talles_por_id = {t.get("id"): t for t in talles_filtrados}
        talles_payload = []
        for row in ean_df.to_dict(orient="records"):
            if not row.get("Seleccionar"):
                continue
            talle = dict(talles_por_id.get(row.get("id"), {}))
            talle["codigoBarra"] = row.get("codigoBarra", "")
            talles_payload.append(talle)
        if not talles_payload:
            st.warning("Selecciona al menos un talle para crear.")
            return
        if any(not str(talle.get("codigoBarra") or "").strip() for talle in talles_payload):
            st.warning("Todos los talles seleccionados tienen que tener codigo de barra.")
            return

        canal_default = next((c for c in catalogos.get("canales", []) if c.get("codigo") == "C0"), None) or (catalogos.get("canales") or [{}])[0]
        sap_default = next(
            (s for s in catalogos.get("sap", []) if s.get("descripcion") == (tipo_sel or {}).get("codigo")),
            None,
        ) or (catalogos.get("sap") or [{}])[0]
        color_data = color_talle or {}
        valor_color_data = valor_color_sel or {}
        base = {
            "codigo": codigo,
            "descripcion": descripcion,
            "grupo": (tipo_sel or {}).get("codigo", ""),
            "descripcionGrupo": (tipo_sel or {}).get("descripcion", ""),
            **_selected_payload(tipo_sel, "tipoProducto", "descripcionProducto"),
            **_selected_payload(sap_default, "grupoSAP", "descripcionGrupoSAP"),
            **_selected_payload(marca_sel, "marca", "descripcionMarca"),
            **_selected_payload(genero_sel, "genero", "descripcionGenero"),
            **_selected_payload(silueta_sel, "silueta", "descripcionSilueta"),
            **_selected_payload(uso_sel, "uso", "descripcionUso"),
            "promo": "",
            "descripcionPromo": "",
            "canal": canal_default.get("codigo", ""),
            **_selected_payload(capsula_sel, "codigoCapsula", "descripcionCapsula"),
            **_selected_payload(division_sel, "codigoDivision", "descripcionDivision"),
            **_selected_payload(temporada_sel, "codigoTemporada", "descripcionTemporada"),
            "color": color_data.get("codigo", ""),
            "descripcionColor": color_data.get("descripcion", ""),
            "valorColor": valor_color_data.get("valor", ""),
            "descripcionValorColor": valor_color_data.get("descripcionValor", ""),
            "nombreProveedor": (proveedor_sel or {}).get("codigo", ""),
            "codigoGen": (valor_genero_sel or {}).get("codigo", ""),
            "genero2": (valor_genero_sel or {}).get("descripcion", ""),
        }
        complementario = {
            "codigoEdad": (edad_sel or {}).get("codigo", ""),
            "codigoMaterial": (material_sel or {}).get("codigo", ""),
            "codigoSegmentacionProveedor": (seg_prov_sel or {}).get("codigo", ""),
            "codigoSegmentacionMarathon": (seg_marathon_sel or {}).get("codigo", ""),
            "codigoVidriera": (vidriera_sel or {}).get("codigo", ""),
            "codigoAnio": (anio_sel or {}).get("codigo", ""),
            "objetivoGeneral": (objetivo_sel or {}).get("codigo", ""),
        }
        try:
            result = _api_post(
                "/api/abm-articulos/borradores",
                _with_abm_lote({
                    "base": base,
                    "complementario": complementario,
                    "talles": talles_payload,
                    "precios": {"precioCompra": precio_compra, "precioVenta": precio_venta},
                }),
            )
            st.success(f"Borrador guardado: {result.get('created', 0)} fila(s).")
            st.session_state["abm_limpiar_alta_basica"] = True
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo guardar el borrador: {e}")

    st.divider()
    st.subheader("Borradores pendientes")
    try:
        _ensure_abm_listados_loaded()
        borradores = st.session_state.get("abm_borradores_items", [])
    except Exception as e:
        st.error(f"No se pudieron cargar los borradores: {e}")
        borradores = []

    if not borradores:
        st.info("No hay borradores pendientes.")
    else:
        borradores_slot = st.empty()
        with borradores_slot.container():
            borradores_df = pd.DataFrame(borradores)
            if "abm_borradores_df" not in st.session_state or set(st.session_state["abm_borradores_df"].get("id", [])) != set(borradores_df.get("id", [])):
                borradores_df.insert(0, "Seleccionar", True)
                st.session_state["abm_borradores_df"] = borradores_df

            bb1 = st.columns([1, 3])[0]
            if bb1.button("Seleccionar / deseleccionar", width="stretch", key="abm_borradores_toggle_btn"):
                df_tmp = st.session_state["abm_borradores_df"].copy()
                nuevo_valor = not bool(df_tmp["Seleccionar"].all()) if not df_tmp.empty else True
                df_tmp["Seleccionar"] = nuevo_valor
                st.session_state["abm_borradores_df"] = df_tmp
                st.rerun()

            with st.form("abm_borradores_form"):
                borradores_editor = st.data_editor(
                    st.session_state["abm_borradores_df"].drop(columns=["id"], errors="ignore"),
                    hide_index=True,
                    width="stretch",
                    disabled=[c for c in st.session_state["abm_borradores_df"].drop(columns=["id"], errors="ignore").columns if c != "Seleccionar"],
                    key="abm_borradores_editor_widget",
                )
                bb2, bb3 = st.columns([1, 2])
                with bb2:
                    borrar_borradores = st.form_submit_button("Eliminar seleccionados", width="stretch", key="abm_borradores_delete_submit")
                with bb3:
                    exportar_borradores = st.form_submit_button("Exportar borradores", type="primary", width="stretch", key="abm_borradores_export_submit")
            borradores_editor.insert(1, "id", st.session_state["abm_borradores_df"]["id"].values)
            ids_seleccionados = borradores_editor.loc[borradores_editor["Seleccionar"].fillna(False), "id"].tolist()

        if borrar_borradores:
            if not ids_seleccionados:
                st.warning("Selecciona al menos un borrador para eliminar.")
                return
            try:
                result = _api_delete_json("/api/abm-articulos/borradores", _with_abm_lote({"ids": ids_seleccionados}))
                st.success(f"Borradores eliminados: {result.get('deleted', 0)}.")
                st.session_state.pop("abm_borradores_df", None)
                _refresh_abm_listados()
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar: {e}")

        if exportar_borradores:
            if not ids_seleccionados:
                st.warning("Selecciona al menos un borrador para exportar.")
                return
            try:
                data = _api_post("/api/abm-articulos/exportar", _with_abm_lote({"ids": ids_seleccionados}))
                download_res = requests.get(data["download_url"], stream=True, headers=NGROK_HEADERS)
                if download_res.status_code == 200:
                    _auto_download(download_res.content, data["filename"], "application/zip")
                    st.success(f"Exportados {data.get('exported', 0)} articulo(s). La descarga ART/PV/PC se inicio automaticamente.")
                    _refresh_abm_listados()
                    _clear_abm_form_state(preserve={"abm_lote_uuid"})
                    borradores_slot.empty()
                else:
                    st.error("El ZIP se genero, pero no se pudo descargar.")
            except Exception as e:
                st.error(f"No se pudo exportar: {e}")

    st.divider()
    st.subheader("Listado complementario")
    try:
        _ensure_abm_listados_loaded()
        complementarios = st.session_state.get("abm_complementarios_items", [])
    except Exception as e:
        st.error(f"No se pudieron cargar los complementarios: {e}")
        complementarios = []

    if not complementarios:
        st.info("No hay articulos complementarios pendientes de descarga.")
        return

    complementarios_slot = st.empty()
    with complementarios_slot.container():
        comp_df = pd.DataFrame(complementarios)
        if "abm_complementarios_df" not in st.session_state or set(st.session_state["abm_complementarios_df"].get("id", [])) != set(comp_df.get("id", [])):
            comp_df.insert(0, "Seleccionar", True)
            st.session_state["abm_complementarios_df"] = comp_df

        cb1 = st.columns([1, 4])[0]
        if cb1.button("Seleccionar / deseleccionar", width="stretch", key="abm_complementarios_toggle_btn"):
            df_tmp = st.session_state["abm_complementarios_df"].copy()
            nuevo_valor = not bool(df_tmp["Seleccionar"].all()) if not df_tmp.empty else True
            df_tmp["Seleccionar"] = nuevo_valor
            st.session_state["abm_complementarios_df"] = df_tmp
            st.rerun()

        editable_comp_cols = {
            "Seleccionar",
            "Edad",
            "Material",
            "Segmentacion Proveedor",
            "Segmentacion Marathon",
            "Vidriera",
            "Año",
            "Objetivo Gen",
        }
        with st.form("abm_complementarios_form"):
            comp_editor = st.data_editor(
                st.session_state["abm_complementarios_df"].drop(columns=["id"], errors="ignore"),
                hide_index=True,
                width="stretch",
                disabled=[
                    c for c in st.session_state["abm_complementarios_df"].drop(columns=["id"], errors="ignore").columns
                    if c not in editable_comp_cols
                ],
                key="abm_complementarios_editor_widget",
            )
            cb2, cb3, cb4 = st.columns([1, 1, 2])
            with cb2:
                guardar_complementarios = st.form_submit_button("Guardar cambios", width="stretch", key="abm_complementarios_save_submit")
            with cb3:
                borrar_complementarios = st.form_submit_button("Borrar seleccionados", width="stretch", key="abm_complementarios_delete_submit")
            with cb4:
                exportar_complementarios = st.form_submit_button("Descargar complementario", type="primary", width="stretch", key="abm_complementarios_export_submit")
        comp_editor.insert(1, "id", st.session_state["abm_complementarios_df"]["id"].values)
        comp_ids_seleccionados = comp_editor.loc[comp_editor["Seleccionar"].fillna(False), "id"].tolist()

    if guardar_complementarios:
        try:
            originales = pd.DataFrame(complementarios).set_index("id")
            cambios = comp_editor.set_index("id")
            campos_editables = ["Edad", "Material", "Segmentacion Proveedor", "Segmentacion Marathon", "Vidriera", "Año", "Objetivo Gen"]
            guardados = 0
            for comp_id, row in cambios.iterrows():
                if comp_id not in originales.index:
                    continue
                payload = {}
                for campo in campos_editables:
                    nuevo = "" if pd.isna(row.get(campo)) else str(row.get(campo) or "")
                    anterior = "" if pd.isna(originales.at[comp_id, campo]) else str(originales.at[comp_id, campo] or "")
                    if nuevo != anterior:
                        payload[campo] = nuevo
                if payload:
                    _api_put(f"/api/abm-articulos/complementarios/{int(comp_id)}", _with_abm_lote(payload))
                    guardados += 1
            st.success(f"Complementarios actualizados: {guardados}.")
            st.session_state.pop("abm_complementarios_df", None)
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudieron guardar los cambios: {e}")

    if borrar_complementarios:
        if not comp_ids_seleccionados:
            st.warning("Selecciona al menos un complementario para borrar.")
            return
        try:
            result = _api_delete_json("/api/abm-articulos/complementarios", _with_abm_lote({"ids": comp_ids_seleccionados}))
            st.success(f"Complementarios eliminados: {result.get('deleted', 0)}.")
            st.session_state.pop("abm_complementarios_df", None)
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo borrar: {e}")

    if exportar_complementarios:
        if not comp_ids_seleccionados:
            st.warning("Selecciona al menos un complementario para descargar.")
            return
        try:
            data = _api_post("/api/abm-articulos/complementarios/exportar", _with_abm_lote({"ids": comp_ids_seleccionados}))
            download_res = requests.get(data["download_url"], stream=True, headers=NGROK_HEADERS)
            if download_res.status_code == 200:
                _auto_download(download_res.content, data["filename"], "text/csv")
                st.success(f"Complementarios exportados: {data.get('exported', 0)}. IDs CEGID encontrados correctamente. La descarga se inicio automaticamente.")
                _finalizar_descarga_complementario(comp_ids_seleccionados)
                complementarios_slot.empty()
            else:
                st.error("El complementario se genero, pero no se pudo descargar.")
        except Exception as e:
            st.error(f"No se pudo exportar complementario: {e}")

    cleanup_error = st.session_state.pop("abm_complementario_cleanup_error", None)
    if cleanup_error:
        st.warning(f"El archivo se descargo, pero no se pudo limpiar el listado complementario: {cleanup_error}")

    if False:
        comp_edit_id = st.selectbox(
            "Registro",
            [None] + [row["id"] for row in complementarios],
            format_func=lambda value: "" if value is None else str(value),
            key="abm_comp_edit_id",
        )
        comp_actual = next((row for row in complementarios if row["id"] == comp_edit_id), None)
        if comp_actual:
            e1, e2, e3 = st.columns(3)
            edad_edit = e1.text_input("Edad", value=comp_actual.get("Edad", ""), key="abm_comp_edit_edad")
            material_edit = e2.text_input("Material", value=comp_actual.get("Material", ""), key="abm_comp_edit_material")
            segp_edit = e3.text_input("Segmentacion Proveedor", value=comp_actual.get("Segmentacion Proveedor", ""), key="abm_comp_edit_segp")
            e4, e5, e6 = st.columns(3)
            segm_edit = e4.text_input("Segmentacion Marathon", value=comp_actual.get("Segmentacion Marathon", ""), key="abm_comp_edit_segm")
            vidriera_edit = e5.text_input("Vidriera", value=comp_actual.get("Vidriera", ""), key="abm_comp_edit_vidriera")
            anio_edit = e6.text_input("Año", value=comp_actual.get("Año", ""), key="abm_comp_edit_anio")
            objetivo_edit = st.text_input("Objetivo Gen", value=comp_actual.get("Objetivo Gen", ""), key="abm_comp_edit_obj")
            if st.button("Guardar modificacion", disabled=comp_edit_id is None):
                try:
                    _api_put(
                        f"/api/abm-articulos/complementarios/{comp_edit_id}",
                        {
                            "Edad": edad_edit,
                            "Material": material_edit,
                            "Segmentacion Proveedor": segp_edit,
                            "Segmentacion Marathon": segm_edit,
                            "Vidriera": vidriera_edit,
                            "Año": anio_edit,
                            "Objetivo Gen": objetivo_edit,
                        } | {"lote_uuid": _get_abm_lote_uuid()},
                    )
                    st.success("Complementario actualizado.")
                    st.session_state.pop("abm_complementarios_df", None)
                    _refresh_abm_listados()
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo modificar: {e}")


CONFIG_ABM_MODULOS = {
    "proveedores": {
        "titulo": "Alta de Proveedores",
        "codigo_label": "Cod. Proveedor",
        "descripcion_label": "Razon Social",
    },
    "marcas": {
        "titulo": "Alta de Marcas",
        "codigo_label": "Cod. Marca",
        "descripcion_label": "Desc. Marca",
    },
    "proveedor-marca": {
        "titulo": "Relacion Proveedor-Marca",
        "codigo_label": "Cod. Prov",
        "descripcion_label": "Cod. Marca",
    },
    "objetivos": {
        "titulo": "Alta de Objetivo General",
        "codigo_label": "Cod. Objetivo Grupo",
        "descripcion_label": "Desc. Objetivo Grupo",
    },
    "markups": {
        "titulo": "Alta de Markups",
        "codigo_label": "Cod. Marca",
        "descripcion_label": "Markup",
    },
}


def _render_config_listado(modulo, items):
    meta = CONFIG_ABM_MODULOS[modulo]
    st.markdown("#### Listado")
    if modulo == "proveedores":
        widths = [1.2, 1.1, 2, 1.3, 1, 1.5]
        headers = ["CUIT", "Cod. Proveedor", "Razon Social", "Marca", "Pivot", "Acciones"]
    else:
        widths = [1.2, 2, 1.4]
        headers = [meta["codigo_label"], meta["descripcion_label"], "Acciones"]

    for col, header in zip(st.columns(widths), headers):
        col.markdown(f"**{header}**")

    for item in items:
        cols = st.columns(widths)
        if modulo == "proveedores":
            cols[0].write(item.get("cuit", ""))
            cols[1].write(item.get("codigo", ""))
            cols[2].write(item.get("descripcion", ""))
            cols[3].write(item.get("marca", ""))
            cols[4].write(item.get("pivot", ""))
            acciones_col = cols[5]
        else:
            cols[0].write(item.get("codigo", ""))
            if modulo == "proveedor-marca":
                cols[1].write(item.get("codigoMarca", ""))
            elif modulo == "markups":
                cols[1].write(item.get("markup", ""))
            else:
                cols[1].write(item.get("descripcion", ""))
            acciones_col = cols[2]

        b1, b2 = acciones_col.columns(2)
        if b1.button("Modificar", key=f"abm_config_{modulo}_edit_{item['id']}", type="secondary"):
            _render_config_dialog(modulo, {"accion": "modificar", "item": item})
        if b2.button("Eliminar", key=f"abm_config_{modulo}_delete_{item['id']}", type="primary"):
            _render_config_dialog(modulo, {"accion": "eliminar", "item": item})


def _mensaje_config(modulo, accion):
    nombres = {
        "proveedores": "proveedor",
        "marcas": "marca",
        "proveedor-marca": "relacion proveedor-marca",
        "objetivos": "objetivo general",
        "markups": "markup",
    }
    nombre = nombres.get(modulo, "registro")
    if accion == "crear":
        return f"La {nombre} se creo correctamente." if modulo in {"marcas", "proveedor-marca"} else f"El {nombre} se creo correctamente."
    if accion == "modificar":
        return f"La {nombre} se modifico correctamente." if modulo in {"marcas", "proveedor-marca"} else f"El {nombre} se modifico correctamente."
    return f"La {nombre} se elimino correctamente." if modulo in {"marcas", "proveedor-marca"} else f"El {nombre} se elimino correctamente."


def _set_config_flash(modulo, message):
    st.session_state[f"abm_config_{modulo}_flash"] = message


def _reset_config_create_form(modulo):
    key = f"abm_config_{modulo}_create_version"
    st.session_state[key] = st.session_state.get(key, 0) + 1


def _render_config_flash(modulo):
    message = st.session_state.pop(f"abm_config_{modulo}_flash", None)
    if message:
        if hasattr(st, "toast"):
            st.toast(message)
        else:
            st.success(message)


def _config_dialog_decorator(title):
    dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    if not dialog:
        return None
    return dialog(title)


def _payload_config_proveedor(cuit, cod_prov, razon_social, marca_txt, pivot):
    return {
        "cuit": cuit,
        "cod_prov": cod_prov,
        "razon_social": razon_social,
        "marca": marca_txt,
        "pivot": pivot,
    }


def _payload_config_simple(modulo, codigo, descripcion):
    if modulo == "proveedor-marca":
        return {"cod_prov": codigo, "codigoMarca": descripcion}
    if modulo == "markups":
        return {"codigoMarca": codigo, "markup": descripcion}
    return {"codigo": codigo, "descripcion": descripcion}


def _render_config_delete_body(modulo, item):
    st.warning("Estas seguro que queres eliminar este registro?")
    relaciones = item.get("relaciones") or []
    if relaciones:
        detalle = ", ".join(
            f"{rel.get('cod_prov', '')} - {rel.get('codigoMarca', '')}".strip(" -")
            for rel in relaciones[:8]
        )
        extra = "" if len(relaciones) <= 8 else f" y {len(relaciones) - 8} mas"
        sujeto = "proveedor" if modulo == "proveedores" else "marca"
        st.info(f"Este {sujeto} tiene relaciones cargadas: {detalle}{extra}. Si lo eliminas, tambien se eliminaran esas relaciones.")

    c1, c2 = st.columns(2)
    if c1.button("Si, eliminar", key=f"abm_config_{modulo}_modal_delete_yes", type="primary", width="stretch"):
        try:
            _api_delete(f"/api/abm-articulos/config/{modulo}/{item['id']}")
            _set_config_flash(modulo, _mensaje_config(modulo, "eliminar"))
            _refresh_abm_config(modulo)
            st.session_state.pop(f"abm_config_{modulo}_dialog", None)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo eliminar: {exc}")
    if c2.button("Cancelar", key=f"abm_config_{modulo}_modal_delete_no", type="secondary", width="stretch"):
        st.session_state.pop(f"abm_config_{modulo}_dialog", None)
        st.rerun()


def _render_config_confirm_update_body(modulo, item, payload):
    st.warning("Estas seguro que queres modificar este registro?")
    c1, c2 = st.columns(2)
    if c1.button("Si, guardar", key=f"abm_config_{modulo}_modal_update_yes", type="primary", width="stretch"):
        try:
            _api_put(f"/api/abm-articulos/config/{modulo}/{item['id']}", payload)
            _set_config_flash(modulo, _mensaje_config(modulo, "modificar"))
            _refresh_abm_config(modulo)
            st.session_state.pop(f"abm_config_{modulo}_dialog", None)
            st.session_state.pop(f"abm_config_{modulo}_modal_payload", None)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo modificar: {exc}")
    if c2.button("No, volver", key=f"abm_config_{modulo}_modal_update_no", type="secondary", width="stretch"):
        st.session_state.pop(f"abm_config_{modulo}_modal_payload", None)
        st.rerun()


def _render_config_update_body(modulo, item):
    pending_payload = st.session_state.get(f"abm_config_{modulo}_modal_payload")
    if pending_payload:
        _render_config_confirm_update_body(modulo, item, pending_payload)
        return

    if modulo == "proveedores":
        with st.form(f"abm_config_{modulo}_modal_form_{item['id']}"):
            c1, c2 = st.columns(2)
            cuit = c1.text_input("CUIT", value=item.get("cuit", ""), max_chars=11, key=f"abm_config_{modulo}_modal_cuit_{item['id']}")
            cod_prov = c2.text_input("Cod. Proveedor", value=item.get("codigo", ""), key=f"abm_config_{modulo}_modal_codigo_{item['id']}")
            razon_social = st.text_input("Razon Social", value=item.get("descripcion", ""), key=f"abm_config_{modulo}_modal_razon_{item['id']}")
            c3, c4 = st.columns(2)
            marca_txt = c3.text_input("Marca", value=item.get("marca", ""), key=f"abm_config_{modulo}_modal_marca_{item['id']}")
            pivot = c4.text_input("Pivot", value=item.get("pivot", ""), key=f"abm_config_{modulo}_modal_pivot_{item['id']}")
            guardar = st.form_submit_button("Guardar cambios", type="primary", width="stretch")
        if guardar:
            st.session_state[f"abm_config_{modulo}_dialog"] = {"accion": "modificar", "item": item}
            st.session_state[f"abm_config_{modulo}_modal_payload"] = _payload_config_proveedor(
                cuit,
                cod_prov,
                razon_social,
                marca_txt,
                pivot,
            )
            st.rerun()

    else:
        meta = CONFIG_ABM_MODULOS[modulo]
        if modulo == "proveedor-marca":
            descripcion_default = item.get("codigoMarca", "")
        elif modulo == "markups":
            descripcion_default = float(item.get("markup") or 0)
        else:
            descripcion_default = item.get("descripcion", "")
        with st.form(f"abm_config_{modulo}_modal_form_{item['id']}"):
            codigo = st.text_input(meta["codigo_label"], value=item.get("codigo", ""), key=f"abm_config_{modulo}_modal_codigo_{item['id']}")
            if modulo == "markups":
                descripcion = st.number_input(meta["descripcion_label"], min_value=0.0, value=descripcion_default, step=0.01, format="%.4f", key=f"abm_config_{modulo}_modal_descripcion_{item['id']}")
            else:
                descripcion = st.text_input(meta["descripcion_label"], value=descripcion_default, key=f"abm_config_{modulo}_modal_descripcion_{item['id']}")
            guardar = st.form_submit_button("Guardar cambios", type="primary", width="stretch")
        if guardar:
            st.session_state[f"abm_config_{modulo}_dialog"] = {"accion": "modificar", "item": item}
            st.session_state[f"abm_config_{modulo}_modal_payload"] = _payload_config_simple(modulo, codigo, descripcion)
            st.rerun()


def _render_config_dialog(modulo, dialog_state=None):
    dialog_state = dialog_state or st.session_state.get(f"abm_config_{modulo}_dialog")
    if not dialog_state:
        return

    item = dialog_state.get("item") or {}
    accion = dialog_state.get("accion")
    title = "Modificar registro" if accion == "modificar" else "Eliminar registro"
    dialog = _config_dialog_decorator(title)
    if not dialog:
        if accion == "modificar":
            _render_config_update_body(modulo, item)
        else:
            _render_config_delete_body(modulo, item)
        return

    @dialog
    def _dialog_content():
        if accion == "modificar":
            _render_config_update_body(modulo, item)
        else:
            _render_config_delete_body(modulo, item)

    _dialog_content()


def _render_config_proveedores():
    modulo = "proveedores"
    version = st.session_state.get(f"abm_config_{modulo}_create_version", 0)
    with st.form(f"abm_config_proveedores_form_{version}"):
        c1, c2, c3 = st.columns(3)
        cuit = c1.text_input("CUIT", max_chars=11, key=f"abm_config_prov_cuit_{version}")
        cod_prov = c2.text_input("Cod. Proveedor", key=f"abm_config_prov_codigo_{version}")
        razon_social = c3.text_input("Razon Social", key=f"abm_config_prov_razon_{version}")
        c4, c5 = st.columns(2)
        marca_txt = c4.text_input("Marca", key=f"abm_config_prov_marca_{version}")
        pivot = c5.text_input("Pivot", key=f"abm_config_prov_pivot_{version}")
        guardar = st.form_submit_button("Crear proveedor", type="primary")
    if guardar:
        try:
            payload = _payload_config_proveedor(cuit, cod_prov, razon_social, marca_txt, pivot)
            _api_post(f"/api/abm-articulos/config/{modulo}", payload)
            _set_config_flash(modulo, _mensaje_config(modulo, "crear"))
            _reset_config_create_form(modulo)
            _refresh_abm_config(modulo)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")


def _render_config_simple(modulo):
    meta = CONFIG_ABM_MODULOS[modulo]
    version = st.session_state.get(f"abm_config_{modulo}_create_version", 0)
    with st.form(f"abm_config_{modulo}_form_{version}"):
        c1, c2 = st.columns(2)
        codigo = c1.text_input(meta["codigo_label"], key=f"abm_config_{modulo}_codigo_{version}")
        if modulo == "markups":
            descripcion = c2.number_input(meta["descripcion_label"], min_value=0.0, step=0.01, format="%.4f", key=f"abm_config_{modulo}_descripcion_{version}")
        else:
            descripcion = c2.text_input(meta["descripcion_label"], key=f"abm_config_{modulo}_descripcion_{version}")
        guardar = st.form_submit_button("Crear registro", type="primary")
    if guardar:
        try:
            payload = _payload_config_simple(modulo, codigo, descripcion)
            _api_post(f"/api/abm-articulos/config/{modulo}", payload)
            _set_config_flash(modulo, _mensaje_config(modulo, "crear"))
            _reset_config_create_form(modulo)
            _refresh_abm_config(modulo)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")


def _render_config_abm_articulos():
    st.subheader("ABM Campos de Articulos")
    tabs = st.tabs([meta["titulo"] for meta in CONFIG_ABM_MODULOS.values()])
    for tab, modulo in zip(tabs, CONFIG_ABM_MODULOS):
        with tab:
            _render_config_flash(modulo)
            if modulo == "proveedores":
                _render_config_proveedores()
            else:
                _render_config_simple(modulo)
            _render_config_dialog(modulo)
            if st.button("Listado", key=f"abm_config_{modulo}_listado_btn"):
                st.session_state[f"abm_config_{modulo}_show_list"] = not st.session_state.get(f"abm_config_{modulo}_show_list", False)
            if st.session_state.get(f"abm_config_{modulo}_show_list", False):
                try:
                    _render_config_listado(modulo, _load_abm_config(modulo))
                except Exception as exc:
                    st.error(f"No se pudo cargar el listado: {exc}")


def _render_app() -> None:
    with st.sidebar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(get_img("logo_marathon_M.png"), width=80)
        st.markdown("<h2 style='text-align: center;'>Panel de Control</h2>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio(
            "Secciones",
            ["Pedido Proveedor", "Propuesta de Compra", "Procesos Especiales", "Articulos", "Config. Articulos", "Auditoria Logistica"],
        )

    st.title(f"📂 {menu}")

    if menu == "Auditoria Logistica":
        _render_auditoria_logistica()
    elif menu == "Articulos":
        _render_abm_articulos()
    elif menu == "Config. Articulos":
        _render_config_abm_articulos()
    else:
        if menu == "Procesos Especiales":
            _render_sync_novedades_panel()
            st.divider()

    # ── Grid de proveedores ───────────────────────────────────────────────────────
        items = {k: v for k, v in PROVIDERS.items() if v["cat"] == menu}
        cols = st.columns(3)

        for idx, (id_p, info) in enumerate(items.items()):
            with cols[idx % 3]:
                _render_provider_card(id_p, info)

    st.divider()
    st.caption(f"Creado por Daniela Diaz © {datetime.now().year}")


try:
    _render_app()
except Exception as exc:
    LOGGER.exception("Unhandled Streamlit frontend error")
    _render_error_details(exc)
