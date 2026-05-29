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
                
                st.dataframe(
                    df_historial,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "talle": st.column_config.TextColumn("Talle"),
                        "comprobante": st.column_config.TextColumn("Remito (BLF)"),
                        "fecha_ingreso": st.column_config.TextColumn("Fecha Entrada"),
                        "cantidad_ingresada": st.column_config.NumberColumn("Cantidad Recibida", format="%d u."),
                        "dias_desvio": st.column_config.NumberColumn("Desfase (Meses)"),
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
