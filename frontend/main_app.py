import streamlit as st
import requests
import os
import pandas as pd
import logging
import platform
import sys
import traceback
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


@st.cache_data(ttl=900, show_spinner=False)
def _load_abm_catalogos() -> dict:
    return _api_get("/api/abm-articulos/catalogos")


@st.cache_data(ttl=15, show_spinner=False)
def _load_abm_borradores() -> list:
    return _api_get("/api/abm-articulos/borradores").get("items", [])


@st.cache_data(ttl=15, show_spinner=False)
def _load_abm_complementarios() -> list:
    return _api_get("/api/abm-articulos/complementarios").get("items", [])


def _refresh_abm_listados():
    _load_abm_borradores.clear()
    _load_abm_complementarios.clear()


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
                            st.error(f"Error: {res.text}")
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
                            st.error(f"Error: {res.text}")
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
        dry_run = c2.toggle("Dry-run", value=True, help="Simula la corrida sin escribir en Google Sheets.")

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
                    with st.expander("Resumen tecnico", expanded=True):
                        st.text(result.get("summary", ""))
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
    codigo = ((tipo_sel or {}).get("codigo") or "").upper()
    descripcion = ((tipo_sel or {}).get("descripcion") or "").upper()
    return {
        "ACC": "ACC",
        "ACCESORIOS": "ACC",
        "BIC": "BIC",
        "BICICLETAS": "BIC",
        "CAL": "CAL",
        "CALZADO": "CAL",
        "CLU": "CLU",
        "CLUBES": "CLU",
        "IND": "IND",
        "INDUMENTARIA": "IND",
        "MED": "MED",
        "MEDIAS": "MED",
        "VER": "CAL",
        "VERANO": "CAL",
    }.get(codigo) or {
        "ACCESORIOS": "ACC",
        "BICICLETAS": "BIC",
        "CALZADO": "CAL",
        "CLUBES": "CLU",
        "INDUMENTARIA": "IND",
        "MEDIAS": "MED",
        "VERANO": "CAL",
    }.get(descripcion)


def _tipo_texto_talle(tipo_sel):
    codigo = ((tipo_sel or {}).get("codigo") or "").upper()
    descripcion = ((tipo_sel or {}).get("descripcion") or "").upper()
    return {
        "ACC": "ACCESORIOS",
        "BIC": "BICICLETA",
        "CAL": "CALZADO",
        "IND": "INDUMENTARIA",
        "MED": "MEDIAS",
    }.get(codigo) or {
        "ACCESORIOS": "ACCESORIOS",
        "BICICLETAS": "BICICLETA",
        "CALZADO": "CALZADO",
        "INDUMENTARIA": "INDUMENTARIA",
        "MEDIAS": "MEDIAS",
    }.get(descripcion)


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


def _clear_abm_form_state(preserve=None):
    preserve = set(preserve or [])
    prefixes = ("abm_",)
    for key in list(st.session_state.keys()):
        if key.startswith(prefixes) and key not in preserve:
            st.session_state.pop(key, None)


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


def _siluetas_para_tipo(tipo_sel, siluetas):
    tipo = ((tipo_sel or {}).get("codigo") or "").upper()
    if not tipo:
        return []
    prefijos = {
        "ACC": ("ACC",),
        "CAL": ("CAL",),
        "IND": ("IND",),
        "MED": ("MED",),
        "BIC": ("BIC",),
    }.get(tipo, (tipo,))
    filtradas = [s for s in siluetas if (s.get("codigo") or "").upper().startswith(prefijos)]
    return filtradas or siluetas


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


def _descripciones_talle_para_tipo(tipo_sel, talles):
    texto = _tipo_texto_talle(tipo_sel)
    items = talles
    if texto:
        filtrados = [t for t in talles if (t.get("descripcion") or "").upper().startswith(texto)]
        items = filtrados or talles
    return _dedupe_descripciones(items)


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


@st.fragment
def _render_abm_articulos() -> None:
    st.subheader("Alta de Articulos")
    try:
        catalogos = _load_abm_catalogos()
    except Exception as e:
        st.error(f"No se pudieron cargar los catalogos: {e}")
        return

    tipos = catalogos.get("tipos_producto", [])
    marcas = catalogos.get("marcas", [])
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
    c1, c2 = st.columns([1, 2])
    codigo = c1.text_input("Codigo", key="abm_codigo")
    descripcion = c2.text_input("Descripcion", key="abm_descripcion")

    c3, c4, c5 = st.columns(3)
    tipo_sel = c3.selectbox("Desc. Tipo de Producto", [None] + tipos, format_func=_label, key="abm_tipo")
    marca_sel = c4.selectbox("Desc. Marca", [None] + marcas, format_func=_label, key="abm_marca")
    genero_sel = c5.selectbox("Desc. Genero", [None] + catalogos.get("generos", []), format_func=_label, key="abm_genero")

    c6, c7, c8, c8b = st.columns(4)
    edad_sel = c6.selectbox("Desc. Edad", [None] + catalogos.get("edades", []), format_func=_label, key="abm_edad")
    valor_genero_sel = c7.selectbox("VALOR", [None] + valores_genero, format_func=_label, key="abm_valor_genero")
    siluetas_filtradas = _siluetas_para_tipo(tipo_sel, catalogos.get("siluetas", []))
    silueta_sel = c8.selectbox("Desc. Silueta", [None] + siluetas_filtradas, format_func=_label, key="abm_silueta")
    uso_sel = c8b.selectbox("Desc. Uso", [None] + catalogos.get("usos", []), format_func=_label, key="abm_uso")

    capsulas = catalogos.get("capsulas", [])
    temporadas = catalogos.get("temporadas", [])
    materiales = catalogos.get("materiales", [])
    seg_proveedores = catalogos.get("segmentaciones_proveedor", [])
    seg_marathon = catalogos.get("segmentaciones_marathon", [])
    vidrieras = catalogos.get("vidrieras", [])
    objetivos_filtrados = _objetivos_para_tipo(tipo_sel, catalogos.get("objetivos", []))

    c9, c10, c11 = st.columns(3)
    capsula_sel = c9.selectbox("Desc. Capsula", [None] + capsulas, index=_default_index(capsulas, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_capsula")
    division_sel = c10.selectbox("Desc. Division", [None] + catalogos.get("divisiones", []), format_func=_label, key="abm_division")
    temporada_sel = c11.selectbox("Desc. Temporada", [None] + temporadas, index=_default_index(temporadas, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_temporada")

    c12, c13, c14 = st.columns(3)
    material_sel = c12.selectbox("Desc. Material", [None] + materiales, index=_default_index(materiales, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_material")
    seg_prov_sel = c13.selectbox("Desc. Segmentacion Proveedor", [None] + seg_proveedores, index=_default_index(seg_proveedores, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_seg_prov")
    seg_marathon_sel = c14.selectbox("Desc. Segmentacion Marathon", [None] + seg_marathon, index=_default_index(seg_marathon, ["PENDIENTE", "APLICAR"]), format_func=_label, key="abm_seg_marathon")

    c15, c16, c17 = st.columns(3)
    vidriera_sel = c15.selectbox("Desc. Exhibicion", [None] + vidrieras, index=_default_index(vidrieras, ["N/A"]), format_func=_label, key="abm_vidriera")
    anio_sel = c16.selectbox("Desc. Anio", [None] + catalogos.get("anios", []), format_func=_label, key="abm_anio")
    if st.session_state.get("abm_objetivo") not in ([None] + objetivos_filtrados):
        st.session_state.pop("abm_objetivo", None)
    objetivo_sel = c17.selectbox("Desc. Objetivo General", [None] + objetivos_filtrados, format_func=_label, key="abm_objetivo")

    c18, c19, c20 = st.columns(3)
    color_talle = _color_talle_para_tipo((tipo_sel or {}).get("codigo"), colores)
    valores_color = [c for c in colores if not color_talle or c.get("codigo") == color_talle.get("codigo")]
    valor_color_sel = c18.selectbox("Desc. Valor Color", [None] + valores_color, format_func=lambda item: "" if not item else item.get("descripcionValor", ""), key="abm_valor_color")
    proveedor_sel = c19.selectbox("Proveedor Habitual", [None] + catalogos.get("proveedores", []), format_func=_label_codigo, key="abm_proveedor")
    c20.text_input("Desc. Color Talle", value=(color_talle or {}).get("descripcion", ""), disabled=True)

    precio_compra = st.number_input("Precio compra", min_value=0.0, step=0.01, format="%.2f", key="abm_precio_compra")
    markup_valor = _markup_para(marca_sel, tipo_sel, catalogos.get("markups", []))
    precio_sugerido = round(precio_compra * markup_valor, 2) if markup_valor else 0.0
    precio_venta_default = max(precio_sugerido, precio_compra + 0.01) if precio_compra else 0.0
    precio_venta = st.number_input(
        "Precio venta",
        min_value=0.0,
        value=float(precio_venta_default),
        step=0.01,
        format="%.2f",
        key="abm_precio_venta",
    )
    if markup_valor:
        st.caption(f"Markup aplicado: {markup_valor:.4f}. Precio sugerido: {precio_sugerido:.2f}.")
    if precio_compra and precio_venta <= precio_compra:
        st.warning("El precio de venta debe ser mayor al precio de compra.")

    st.markdown("### Talles")
    descripciones_talle = _descripciones_talle_para_tipo(tipo_sel, talles)
    if st.session_state.get("abm_desc_talle") not in ([""] + descripciones_talle):
        st.session_state.pop("abm_desc_talle", None)
    desc_talle_sel = st.selectbox("Desc. Talle", [""] + descripciones_talle, key="abm_desc_talle")
    if st.session_state.get("abm_desc_talle_actual") != desc_talle_sel:
        st.session_state["abm_desc_talle_actual"] = desc_talle_sel
        st.session_state.pop("abm_talles_df", None)
    talles_filtrados = _dedupe_talles([t for t in talles if t.get("descripcion") == desc_talle_sel])

    if desc_talle_sel:
        rows = []
        for talle in talles_filtrados:
            rows.append({
                "id": talle.get("id"),
                "Seleccionar": True,
                "Descripcion": talle.get("descripcion", ""),
                "Talle": talle.get("valorTalle", ""),
                "Equiv": talle.get("descripcionValorTalle") or talle.get("valorTalle", ""),
                "codigoBarra": talle.get("codigoBarra", ""),
            })

        if "abm_talles_df" not in st.session_state:
            st.session_state["abm_talles_df"] = pd.DataFrame(rows)

        codigos_pegados = st.text_area(
            "Pegar codigos de barra para talles seleccionados",
            key="abm_codigos_pegados",
            height=90,
            placeholder="Un codigo por linea. Se aplican solo a los talles seleccionados.",
        )
        tb1, tb2, tb3, tb4 = st.columns([1, 1, 1, 1])
        if tb1.button("Seleccionar / deseleccionar", width="stretch", key="abm_talles_toggle_btn"):
            df_tmp = st.session_state["abm_talles_df"].copy()
            nuevo_valor = not bool(df_tmp["Seleccionar"].all()) if not df_tmp.empty else True
            df_tmp["Seleccionar"] = nuevo_valor
            st.session_state["abm_talles_df"] = df_tmp
            st.rerun()
        if tb2.button("Pegar en seleccionados", disabled=not codigos_pegados.strip(), width="stretch", key="abm_talles_paste_btn"):
            df_tmp = st.session_state["abm_talles_df"].copy()
            mask = df_tmp["Seleccionar"].fillna(False)
            codigos = [line.strip() for line in codigos_pegados.splitlines() if line.strip()]
            indices = df_tmp.index[mask].tolist()
            for idx, codigo_barra in zip(indices, codigos):
                df_tmp.at[idx, "codigoBarra"] = codigo_barra
            st.session_state["abm_talles_df"] = df_tmp
            st.rerun()
        if tb3.button("Generar codigos temporales", disabled=not codigo, width="stretch", key="abm_talles_generate_btn"):
            df_tmp = st.session_state["abm_talles_df"].copy()
            mask = df_tmp["Seleccionar"].fillna(False)
            df_tmp.loc[mask, "codigoBarra"] = df_tmp.loc[mask, "Talle"].apply(lambda talle: f"T{codigo}{talle}")
            st.session_state["abm_talles_df"] = df_tmp
            st.rerun()
        if tb4.button("Limpiar codigos de barras", width="stretch", key="abm_talles_clear_btn"):
            df_tmp = st.session_state["abm_talles_df"].copy()
            mask = df_tmp["Seleccionar"].fillna(False)
            df_tmp.loc[mask, "codigoBarra"] = ""
            st.session_state["abm_talles_df"] = df_tmp
            st.rerun()

        editor_source = st.session_state.get("abm_talles_df", pd.DataFrame(rows))
        with st.form("abm_talles_form"):
            ean_df = st.data_editor(
                editor_source.drop(columns=["id"], errors="ignore"),
                hide_index=True,
                width="stretch",
                disabled=["Descripcion", "Talle", "Equiv"],
                key="abm_talles_editor_widget",
            )
            aplicar_talles = st.form_submit_button("Aplicar cambios de talles", width="stretch")
        if aplicar_talles:
            ean_df.insert(0, "id", editor_source["id"].values)
            st.session_state["abm_talles_df"] = ean_df
            st.rerun()
        else:
            ean_df = st.session_state["abm_talles_df"]
    else:
        ean_df = pd.DataFrame()

    if st.button("Guardar borrador", type="primary", width="stretch", key="abm_guardar_borrador_btn"):
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
                {
                    "base": base,
                    "complementario": complementario,
                    "talles": talles_payload,
                    "precios": {"precioCompra": precio_compra, "precioVenta": precio_venta},
                },
            )
            st.success(f"Borrador guardado: {result.get('created', 0)} fila(s).")
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo guardar el borrador: {e}")

    st.divider()
    st.subheader("Borradores pendientes")
    try:
        borradores = _load_abm_borradores()
    except Exception as e:
        st.error(f"No se pudieron cargar los borradores: {e}")
        borradores = []

    if not borradores:
        st.info("No hay borradores pendientes.")
    else:
        borradores_df = pd.DataFrame(borradores)
        if "abm_borradores_df" not in st.session_state or set(st.session_state["abm_borradores_df"].get("id", [])) != set(borradores_df.get("id", [])):
            borradores_df.insert(0, "Seleccionar", False)
            st.session_state["abm_borradores_df"] = borradores_df

        bb1, bb2, bb3 = st.columns([1, 1, 2])
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
            aplicar_borradores = st.form_submit_button("Aplicar seleccion de borradores", width="stretch")
        borradores_editor.insert(1, "id", st.session_state["abm_borradores_df"]["id"].values)
        if aplicar_borradores:
            st.session_state["abm_borradores_df"] = borradores_editor
            st.rerun()
        ids_seleccionados = borradores_editor.loc[borradores_editor["Seleccionar"].fillna(False), "id"].tolist()

        if bb2.button("Eliminar seleccionados", disabled=not ids_seleccionados, width="stretch", key="abm_borradores_delete_btn"):
            try:
                result = _api_delete_json("/api/abm-articulos/borradores", {"ids": ids_seleccionados})
                st.success(f"Borradores eliminados: {result.get('deleted', 0)}.")
                st.session_state.pop("abm_borradores_df", None)
                _refresh_abm_listados()
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar: {e}")

        if bb3.button("Exportar borradores", type="primary", width="stretch", key="abm_borradores_export_btn"):
            try:
                data = _api_post("/api/abm-articulos/exportar")
                download_res = requests.get(data["download_url"], stream=True, headers=NGROK_HEADERS)
                if download_res.status_code == 200:
                    st.session_state["abm_export_download"] = {
                        "content": download_res.content,
                        "filename": data["filename"],
                        "message": f"Exportados {data.get('exported', 0)} articulo(s).",
                    }
                    _refresh_abm_listados()
                    _clear_abm_form_state(preserve={"abm_export_download", "abm_complementario_download"})
                    st.rerun()
                else:
                    st.error("El ZIP se genero, pero no se pudo descargar.")
            except Exception as e:
                st.error(f"No se pudo exportar: {e}")

    export_download = st.session_state.get("abm_export_download")
    if export_download:
        st.success(export_download["message"])
        st.download_button(
            "Descargar ART/PCO/PVE",
            data=export_download["content"],
            file_name=export_download["filename"],
            mime="application/zip",
            width="stretch",
            key="abm_download_art_zip_btn",
        )

    st.divider()
    st.subheader("Listado complementario")
    try:
        complementarios = _load_abm_complementarios()
    except Exception as e:
        st.error(f"No se pudieron cargar los complementarios: {e}")
        complementarios = []

    if not complementarios:
        st.info("No hay articulos complementarios pendientes de descarga.")
        return

    comp_df = pd.DataFrame(complementarios)
    if "abm_complementarios_df" not in st.session_state or set(st.session_state["abm_complementarios_df"].get("id", [])) != set(comp_df.get("id", [])):
        comp_df.insert(0, "Seleccionar", False)
        st.session_state["abm_complementarios_df"] = comp_df

    cb1, cb2, cb3, cb4, cb5 = st.columns([1, 1, 1, 1, 2])
    if cb1.button("Seleccionar / deseleccionar", width="stretch", key="abm_complementarios_toggle_btn"):
        df_tmp = st.session_state["abm_complementarios_df"].copy()
        nuevo_valor = not bool(df_tmp["Seleccionar"].all()) if not df_tmp.empty else True
        df_tmp["Seleccionar"] = nuevo_valor
        st.session_state["abm_complementarios_df"] = df_tmp
        st.rerun()

    editable_comp_cols = {
        "Seleccionar",
        "ID Articulo",
        "Edad",
        "Material",
        "Segmentacion Proveedor",
        "Segmentacion Marathon",
        "Vidriera",
        "AÃ±o",
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
        aplicar_complementarios = st.form_submit_button("Aplicar cambios complementarios", width="stretch")
    comp_editor.insert(1, "id", st.session_state["abm_complementarios_df"]["id"].values)
    if aplicar_complementarios:
        st.session_state["abm_complementarios_df"] = comp_editor
        st.rerun()
    comp_ids_seleccionados = comp_editor.loc[comp_editor["Seleccionar"].fillna(False), "id"].tolist()

    if cb2.button("Guardar cambios", width="stretch", key="abm_complementarios_save_btn"):
        try:
            originales = pd.DataFrame(complementarios).set_index("id")
            cambios = comp_editor.set_index("id")
            campos_editables = ["ID Articulo", "Edad", "Material", "Segmentacion Proveedor", "Segmentacion Marathon", "Vidriera", "AÃ±o", "Objetivo Gen"]
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
                    _api_put(f"/api/abm-articulos/complementarios/{int(comp_id)}", payload)
                    guardados += 1
            st.success(f"Complementarios actualizados: {guardados}.")
            st.session_state.pop("abm_complementarios_df", None)
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudieron guardar los cambios: {e}")

    if cb3.button("Borrar seleccionados", disabled=not comp_ids_seleccionados, width="stretch", key="abm_complementarios_delete_selected_btn"):
        try:
            result = _api_delete_json("/api/abm-articulos/complementarios", {"ids": comp_ids_seleccionados})
            st.success(f"Complementarios eliminados: {result.get('deleted', 0)}.")
            st.session_state.pop("abm_complementarios_df", None)
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo borrar: {e}")

    if cb4.button("Borrar todo", width="stretch", key="abm_complementarios_delete_all_btn"):
        try:
            result = _api_delete_json("/api/abm-articulos/complementarios", {"all": True})
            st.success(f"Complementarios eliminados: {result.get('deleted', 0)}.")
            st.session_state.pop("abm_complementarios_df", None)
            _refresh_abm_listados()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo borrar todo: {e}")

    if cb5.button("Descargar complementario", type="primary", width="stretch", key="abm_complementarios_export_btn"):
        try:
            data = _api_post("/api/abm-articulos/complementarios/exportar", {"ids": comp_ids_seleccionados})
            download_res = requests.get(data["download_url"], stream=True, headers=NGROK_HEADERS)
            if download_res.status_code == 200:
                st.session_state["abm_complementario_download"] = {
                    "content": download_res.content,
                    "filename": data["filename"],
                    "message": f"Complementarios exportados: {data.get('exported', 0)}. Fallback CEGID: {data.get('fallbacks', 0)}.",
                }
                st.rerun()
            else:
                st.error("El complementario se genero, pero no se pudo descargar.")
        except Exception as e:
            st.error(f"No se pudo exportar complementario: {e}")

    comp_download = st.session_state.get("abm_complementario_download")
    if comp_download:
        st.success(comp_download["message"])
        st.download_button(
            "Descargar archivo complementario",
            data=comp_download["content"],
            file_name=comp_download["filename"],
            mime="text/csv",
            width="stretch",
            on_click=_clear_abm_form_state,
            key="abm_download_complementario_btn",
        )

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
                        },
                    )
                    st.success("Complementario actualizado.")
                    st.session_state.pop("abm_complementarios_df", None)
                    _refresh_abm_listados()
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo modificar: {e}")


def _render_app() -> None:
    with st.sidebar:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(get_img("logo_marathon_M.png"), width=80)
        st.markdown("<h2 style='text-align: center;'>Panel de Control</h2>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio(
            "Secciones",
            ["Pedido Proveedor", "Propuesta de Compra", "Procesos Especiales", "ABM Articulos", "Auditoria Logistica"],
        )

    st.title(f"📂 {menu}")

    if menu == "Auditoria Logistica":
        _render_auditoria_logistica()
    elif menu == "ABM Articulos":
        _render_abm_articulos()
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
