import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(get_img("logo_marathon_M.png"), width=80)
    st.markdown("<h2 style='text-align: center;'>Panel de Control</h2>", unsafe_allow_html=True)
    st.divider()
    menu = st.radio("Secciones", ["Pedido Proveedor", "Propuesta de Compra", "Procesos Especiales", "Auditoria Logistica"])

st.title(f"📂 {menu}")


def _api_get(path: str, params=None) -> dict:
    res = requests.get(f"{BACKEND_URL}{path}", params=params, headers=NGROK_HEADERS, timeout=20)
    res.raise_for_status()
    return res.json()


def _api_post(path: str, payload=None) -> dict:
    res = requests.post(f"{BACKEND_URL}{path}", json=payload or {}, headers=NGROK_HEADERS, timeout=300)
    res.raise_for_status()
    return res.json()


def _render_auditoria_logistica() -> None:
    st.subheader("Panel de Control de Auditoria")

    default_hasta = datetime.now().date() + timedelta(days=1)
    default_desde = default_hasta - timedelta(days=7)

    if st.button("Limpiar filtros"):
        st.session_state["aud_empresa"] = ""
        st.session_state["aud_desde"] = default_desde
        st.session_state["aud_hasta"] = default_hasta
        st.session_state["aud_proveedor"] = ""
        st.session_state["aud_marca"] = ""
        st.session_state["aud_estado"] = ""
        st.session_state["aud_mes"] = ""
        st.session_state["aud_documento_id"] = 0
        st.session_state["aud_incluir_def"] = True
        st.session_state["aud_show_results"] = False

    sync_col, empresa_col, desde_col, hasta_col, def_col = st.columns([1, 1, 1, 1, 1])
    empresa = empresa_col.selectbox(
        "Empresa",
        ["", "002", "001"],
        format_func=lambda value: {
            "": "Ambas",
            "002": "Marathon",
            "001": "Blanco",
        }.get(value, value),
        key="aud_empresa",
    )
    desde = desde_col.date_input("Desde", value=default_desde, key="aud_desde")
    hasta = hasta_col.date_input("Hasta", value=default_hasta, key="aud_hasta")
    incluir_def = def_col.checkbox("Incluir DEF", value=True, key="aud_incluir_def")
    with sync_col:
        if st.button("Sincronizar CEGID", type="primary", width="stretch"):
            with st.spinner("Consultando PIECE/LIGNE..."):
                try:
                    result = _api_post(
                        "/api/auditoria/sync/cegid",
                        {
                            "tipos": ["CF", "ALF", "BLF"],
                            "desde": desde.isoformat(),
                            "hasta": hasta.isoformat(),
                            "souche": empresa or None,
                            "incluir_def": incluir_def,
                        },
                    )
                    st.success(f"Sincronizados: {result.get('documentos', 0)} documentos y {result.get('lineas', 0)} lineas.")
                    st.session_state["aud_show_results"] = False
                except Exception as e:
                    st.error(f"No se pudo sincronizar CEGID: {e}")

    st.divider()
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 1])
    proveedor = f1.text_input("Proveedor", placeholder="Ej: ADIDA", key="aud_proveedor").strip() or None
    marca = f2.text_input("Marca", placeholder="Ej: ADIDAS", key="aud_marca").strip() or None
    estado = f3.selectbox(
        "Estado",
        ["", "OK", "PENDIENTE", "PROPUESTA_NO_CARGADA", "PENDIENTE_RECEPCION", "NOTIFICACION_PARCIAL", "SOBRE_ENTREGA"],
        format_func=lambda value: "Todos" if value == "" else value,
        key="aud_estado",
    ) or None
    mes = f4.text_input("Mes entrega", value="", placeholder="YYYY-MM", key="aud_mes").strip() or None
    if f5.button("Aplicar filtros", width="stretch"):
        st.session_state["aud_show_results"] = True

    if not st.session_state.get("aud_show_results", False):
        st.info("Sincroniza CEGID o aplica filtros para ver resultados.")
        return

    try:
        data = _api_get(
            "/api/auditoria/documentos",
            params={
                "proveedor": proveedor,
                "estado": estado,
                "marca": marca,
                "mes": mes,
                "souche": empresa or None,
            },
        )
        items = data.get("items", [])
    except Exception as e:
        st.error(f"No se pudo consultar auditoria: {e}")
        return

    if not items:
        st.warning("Todavia no hay documentos conciliados para mostrar.")
        return

    df = pd.DataFrame(items)
    total_pedido = df.get("cantidad_pedida", pd.Series(dtype=float)).sum()
    total_facturado = df.get("cantidad_facturada", pd.Series(dtype=float)).sum()
    total_notificado = df.get("cantidad_notificada", pd.Series(dtype=float)).sum()
    total_recibido = df.get("cantidad_recibida", pd.Series(dtype=float)).sum()
    circuitos_ok = int((df.get("estado", pd.Series(dtype=str)) == "OK").sum())
    otif = round(circuitos_ok / len(df) * 100, 2) if len(df) else 0
    base_pendiente = total_pedido if total_pedido else total_facturado
    unidades_pendientes = max(base_pendiente - total_recibido, 0)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("OTIF filtrado", f"{otif}%")
    k2.metric("Documentos", len(df))
    k3.metric("Facturado CF", f"{total_facturado:,.0f}")
    k4.metric("Recibido BLF", f"{total_recibido:,.0f}")

    k5, k6, k7, _ = st.columns(4)
    k5.metric("Pedido DEF", f"{total_pedido:,.0f}")
    k6.metric("Notificado ALF", f"{total_notificado:,.0f}")
    k7.metric("Unidades pendientes", f"{unidades_pendientes:,.0f}")

    columnas = [
        "documento_id",
        "codigo_documento",
        "proveedor",
        "cegid_souche",
        "marca",
        "articulos",
        "cantidad_pedida",
        "cantidad_facturada",
        "cantidad_notificada",
        "cantidad_recibida",
        "cumplimiento",
        "estado",
    ]
    columnas = [col for col in columnas if col in df.columns]
    st.dataframe(df[columnas], width="stretch", hide_index=True)

    documento_id = st.number_input("Documento para detalle", min_value=0, step=1, key="aud_documento_id")

    if documento_id:
        try:
            detalle = _api_get(f"/api/auditoria/documentos/{int(documento_id)}")
        except Exception as e:
            st.error(f"No se pudo abrir el detalle: {e}")
            return

        st.subheader(f"Detalle {detalle['documento']['codigo_documento']}")
        detalle_df = pd.DataFrame(detalle.get("lineas", []))
        if detalle_df.empty:
            st.info("El documento no tiene lineas relacionadas.")
        else:
            st.dataframe(detalle_df, width="stretch", hide_index=True)

    st.subheader("Comparativo DEF vs BLF")
    try:
        plan_data = _api_get(
            "/api/auditoria/plan-vs-recepcion",
            params={
                "proveedor": proveedor,
                "marca": marca,
                "mes": mes,
                "souche": empresa or None,
            },
        )
        plan_items = plan_data.get("items", [])
    except Exception as e:
        st.error(f"No se pudo consultar DEF vs BLF: {e}")
        return

    if not plan_items:
        st.info("No hay datos DEF/BLF para comparar con los filtros actuales.")
    else:
        plan_df = pd.DataFrame(plan_items)
        st.dataframe(plan_df, width="stretch", hide_index=True)

# ── Función reutilizable para mostrar resultados de auditoría ─────────────────
def _render_audit_results(data: dict) -> None:
    """Muestra los resultados de auditoría y el botón de descarga."""
    audit = data.get("audit", {})
    has_audit = data.get("has_audit", False)

    st.toast("¡Archivo procesado!", icon="✅")

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
        else:
            st.success("No hay variaciones de precio respecto a CEGID.")

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


def _render_provider_card(id_p: str, info: dict) -> None:
    """Renderiza la tarjeta de un proveedor con uploader y lógica de procesamiento."""
    with st.container(border=True):
        st.image(get_img(info["logo"]), width='stretch')
        st.subheader(info["name"], divider="blue")

        with st.expander(f"Utilizar {info['name']}"):
            st.caption(f"Tipo de archivo: {info['ext']}")
            file = st.file_uploader(
                "Seleccionar archivo",
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
                            st.error(f"Error: {res.text}")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")


if menu == "Auditoria Logistica":
    _render_auditoria_logistica()
else:
    # ── Grid de proveedores ───────────────────────────────────────────────────────
    items = {k: v for k, v in PROVIDERS.items() if v["cat"] == menu}
    cols = st.columns(3)

    for idx, (id_p, info) in enumerate(items.items()):
        with cols[idx % 3]:
            _render_provider_card(id_p, info)

st.divider()
st.caption(f"Creado por Daniela Diaz © {datetime.now().year}")
