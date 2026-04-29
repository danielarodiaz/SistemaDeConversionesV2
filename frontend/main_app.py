import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Carga variables de entorno desde .env si existe
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Sistema Conversor V2", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "static", "img")
local_css(os.path.join(BASE_DIR, "static", "css", "custom_style.css"))

def get_img(name):
    return os.path.join(IMG_DIR, name)

PROVIDERS = {
    "adidas": {"name": "Adidas", "logo": "logo_adida.png", "cat": "Pedido Proveedor", "ext": ".xlsx"},
    "bestsox": {"name": "Best Sox", "logo": "logo_bestsox.png", "cat": "Pedido Proveedor", "ext": ".xlsx"},
    "diadora": {"name": "Diadora", "logo": "logo_G7.png", "cat": "Pedido Proveedor", "ext": ".xlsx"},
    "johnfoos": {"name": "John Foos", "logo": "logo_johnfoos.png", "cat": "Pedido Proveedor", "ext": ".xlsx"},
    "kdy": {"name": "Kdy", "logo": "logo_kdy.png", "cat": "Pedido Proveedor", "ext": ".xlsx"},
    "leuru": {"name": "Leuru", "logo": "logo_leuru.png", "cat": "Pedido Proveedor", "ext": ".txt"},
    "puma": {"name": "Puma", "logo": "logo_puma.png", "cat": "Pedido Proveedor", "ext": ".csv"},
    "topper": {"name": "Topper", "logo": "logo_topper.png", "cat": "Pedido Proveedor", "ext": ".txt"},
    "nike": {"name": "Nike", "logo": "logo_nike.png", "cat": "Propuesta de Compra", "ext": ".xlsx"},
    "arca": {"name": "ARCA", "logo": "logo_arca.png", "cat": "Procesos Especiales", "ext": ".xlsx"},
    "gastos": {"name": "Gastos", "logo": "logo_gastos.png", "cat": "Procesos Especiales", "ext": ".xlsx"},
}

with st.sidebar:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(get_img("logo_marathon_M.png"), width=80)
    
    st.markdown("<h2 style='text-align: center;'>Panel de Control</h2>", unsafe_allow_html=True)
    st.divider()
    menu = st.radio("Secciones", ["Pedido Proveedor", "Propuesta de Compra", "Procesos Especiales"])

st.title(f"📂 {menu}")

items = {k: v for k, v in PROVIDERS.items() if v["cat"] == menu}
cols = st.columns(3)

for idx, (id_p, info) in enumerate(items.items()):
    with cols[idx % 3]:
        with st.container(border=True): 
            st.image(get_img(info["logo"]), width='stretch')
            st.subheader(info["name"], divider="blue")
            
            with st.expander(f"Utilizar {info['name']}"):
                st.caption(f"Tipo de archivo: {info['ext']}")
                file = st.file_uploader("Seleccionar archivo", key=id_p, label_visibility="collapsed")
            
            if file:
                if st.button(f"Procesar {info['name']}", key=f"btn_{id_p}", type="primary", width="stretch"):
                    with st.spinner("⏳ Trabajando..."):
                        files = {"file": (file.name, file.getvalue())}
                        try:
                            res = requests.post(f"{BACKEND_URL}/api/process/{id_p}", files=files)
                             # Dentro del bloque donde haces el request.post al backend:
                            if res.status_code == 200:
                                data = res.json()
                                audit = data.get("audit", {})
                                has_audit = data.get("has_audit", False)

                                st.toast("¡Archivo procesado!", icon="✅")

                                # SOLO MOSTRAR SI EL PROCESO ES AUDITABLE (Adidas, Puma, Topper)
                                if has_audit:
                                    # --- SECCIÓN FALTANTES ---
                                    if audit.get('faltantes'):
                                        df_faltantes = pd.DataFrame(audit['faltantes'])
                                        modelos_unicos = df_faltantes['Material'].nunique()
                                        st.error(f"🚨 Debes crear {modelos_unicos} Modelo(s) nuevo(s) en CEGID")
                                        with st.expander("Ver detalle de talles a crear", expanded=True):
                                            st.dataframe(df_faltantes.sort_values(by=["Material", "Size"]), width="stretch")

                                    # --- SECCIÓN ACTUALIZAR EAN ---
                                    if audit.get("actualizar_ean"):
                                        modelos_ean = pd.DataFrame(audit["actualizar_ean"])['articulo'].nunique()
                                        st.info(f"⚠️ Hay {modelos_ean} Modelo(s) con EANs nuevos.")
                                        with st.expander("Ver talles a vincular"):
                                            st.dataframe(pd.DataFrame(audit["actualizar_ean"]), width="stretch")

                                    # --- SECCIÓN PRECIOS ---
                                    if audit.get('cambios_precio'):
                                        st.warning(f"📊 Se detectaron {len(audit['cambios_precio'])} variaciones de precio.")
                                        with st.expander("🔍 Revisar Resumen de Precios por Modelo"):
                                            df_precios = pd.DataFrame(audit['cambios_precio'])
                                            df_display = df_precios.copy()
                                            df_display['precio_cegid'] = df_display['precio_cegid'].map("${:,.2f}".format)
                                            df_display['precio_prov'] = df_display['precio_prov'].map("${:,.2f}".format)
                                            df_display['variacion_porcentaje'] = df_display['variacion_porcentaje'].map("{:.2f}%".format)
                                            st.dataframe(df_display, width="stretch")
                                    else:
                                        # Este mensaje solo sale en Pedidos si todo está OK
                                        st.success("No hay variaciones de precio respecto a CEGID.")

                                # --- SECCIÓN CONFLICTOS DE SUC (para KDY) ---
                                if audit.get('conflictos_suc'):
                                    df_conflictos = pd.DataFrame(audit['conflictos_suc'])
                                    remitos_afectados = df_conflictos['Remito'].nunique() if 'Remito' in df_conflictos.columns else '?'
                                    st.error(f"🚨 ¡ATENCIÓN! {remitos_afectados} remito(s) tienen líneas con distinto valor de **Suc**. Revisá el detalle antes de importar.")
                                    with st.expander("🔍 Ver líneas con Suc inconsistente", expanded=True):
                                        if 'Remito' in df_conflictos.columns:
                                            df_conflictos = df_conflictos.sort_values(by='Remito')
                                        st.dataframe(df_conflictos, width="stretch")
                                
                                # --- SECCIÓN DESCARGA (Común a todos) ---
                                download_res = requests.get(data["download_url"], stream=True)
                                if download_res.status_code == 200:
                                    st.download_button(
                                        label="⬇️ Descargar Archivo",
                                        data=download_res.content,
                                        file_name=data["filename"],
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if data["filename"].endswith(".xlsx") else "text/csv",
                                        width="stretch"
                                    )
                            else:
                                st.error(f"Error: {res.text}")
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

st.divider()
st.caption(f"Creado por Daniela Diaz © {datetime.now().year}")