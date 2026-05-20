import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime
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
    menu = st.radio("Secciones", ["Pedido Proveedor", "Propuesta de Compra", "Procesos Especiales"])

st.title(f"📂 {menu}")

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


# ── Grid de proveedores ───────────────────────────────────────────────────────
items = {k: v for k, v in PROVIDERS.items() if v["cat"] == menu}
cols = st.columns(3)

for idx, (id_p, info) in enumerate(items.items()):
    with cols[idx % 3]:
        _render_provider_card(id_p, info)

st.divider()
st.caption(f"Creado por Daniela Diaz © {datetime.now().year}")