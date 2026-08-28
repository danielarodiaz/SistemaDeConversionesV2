import os
import sys
import zipfile
import csv
import io

# ── Path setup: debe ir PRIMERO para que todos los imports de backend.* funcionen
# tanto al ejecutar como script (py backend/app.py) como al importar como módulo.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, '..')))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from backend.utils.pedido_helpers import (
    auditar_promos_articulos,
    generar_zip_con_variaciones,
    resolver_codigos_articulo_para_auditoria_promos,
)
from backend.database import DB_AUTH_TYPE, DB_HOST, DB_NAME, _HOSTNAME
from backend.services.auditoria_service import AuditoriaService
from backend.scripts.abm_articulos.service import (
    crear_borrador as abm_crear_borrador,
    actualizar_complementario as abm_actualizar_complementario,
    eliminar_borrador as abm_eliminar_borrador,
    eliminar_borradores as abm_eliminar_borradores,
    eliminar_complementarios as abm_eliminar_complementarios,
    exportar_complementarios as abm_exportar_complementarios,
    exportar_borradores as abm_exportar_borradores,
    listar_complementarios as abm_listar_complementarios,
    listar_borradores as abm_listar_borradores,
    obtener_catalogos as abm_obtener_catalogos,
)

# Fuerza UTF-8 en la consola para evitar UnicodeEncodeError con emojis en Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Carga variables de entorno
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── Pedido Proveedor ──────────────────────────────────────────────────────────
from backend.scripts.pedido_proveedor.adida_processor     import process_adidas_pedido_proveedor
from backend.scripts.pedido_proveedor.bestsox_processor   import process_bestsox_pedido_proveedor
from backend.scripts.pedido_proveedor.braku_processor     import process_braku_pedido_proveedor
from backend.scripts.pedido_proveedor.diadora_processor   import process_diadora_pedido_proveedor
from backend.scripts.pedido_proveedor.johnfoos_processor  import process_johnfoos_pedido_proveedor
from backend.scripts.pedido_proveedor.kdy_processor       import process_kdy_pedido_proveedor
from backend.scripts.pedido_proveedor.kosiuko_processor   import process_kosiuko_pedido_proveedor
from backend.scripts.pedido_proveedor.leuru_processor     import process_leuru_pedido_proveedor
from backend.scripts.pedido_proveedor.procer_procesador   import process_procer_pedido_proveedor
from backend.scripts.pedido_proveedor.proyec_processor    import process_proyec_pedido_proveedor
from backend.scripts.pedido_proveedor.puma_processor      import process_puma_pedido_proveedor
from backend.scripts.pedido_proveedor.saucony_processor   import process_saucony_pedido_proveedor
from backend.scripts.pedido_proveedor.topper_processor    import process_topper_pedido_proveedor
# distrinando: comentado por dependencia de data_service (verificar disponibilidad)
# from backend.scripts.pedido_proveedor.distrinando_processor import process_distrinando_pedido_proveedor

# ── Propuesta de Compra ───────────────────────────────────────────────────────
from backend.scripts.propuesta_compra.adida_processor     import process_adidas_propuesta_compra
from backend.scripts.propuesta_compra.nike_processor      import process_nike_propuesta_compra
from backend.scripts.propuesta_compra.puma_processor      import process_puma_propuesta_compra
from backend.scripts.propuesta_compra.topper_processor    import process_topper_propuesta_compra

# ── Procesos Especiales ───────────────────────────────────────────────────────
from backend.scripts.procesos_especiales.arca_processor         import process_arca_procesos_especiales
from backend.scripts.procesos_especiales.mayorista_processor    import process_mayorista_procesos_especiales
# gastos_processor y sevillanitaV2_processor dependen de módulos de datos opcionales (data.gastos_database,
# data.ocr_database). Se importan de forma diferida para que el servidor no falle en startup.
try:
    from backend.scripts.procesos_especiales.gastos_processor import process_gastos_procesos_especiales
    _GASTOS_DISPONIBLE = True
except ModuleNotFoundError:
    _GASTOS_DISPONIBLE = False
    print("⚠️  gastos_processor no disponible: falta el módulo 'data.gastos_database'.")
try:
    from backend.scripts.procesos_especiales.sevillanitaV2_processor import process_sevillanitaV2_procesos_especiales
    _SEVILLANITA_DISPONIBLE = True
except ModuleNotFoundError:
    _SEVILLANITA_DISPONIBLE = False
    print("⚠️  sevillanitaV2_processor no disponible: falta el módulo 'data.ocr_database'.")
try:
    from backend.scripts.procesos_especiales.sync_novedades.main import run_sync as run_sync_novedades
    _SYNC_NOVEDADES_DISPONIBLE = True
except ModuleNotFoundError as e:
    _SYNC_NOVEDADES_DISPONIBLE = False
    print(f"Sync NOVEDADES no disponible: {e}")

# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
auditoria_service = AuditoriaService()

@app.route('/api/status', methods=['GET'])
def status():
    """Endpoint de diagnóstico: muestra cómo está configurada la conexión a la DB."""
    return jsonify({
        "status": "online",
        "hostname": _HOSTNAME,
        "db_auth_type": DB_AUTH_TYPE,
        "db_host": DB_HOST,
        "db_name": DB_NAME,
    }), 200


@app.route('/api/auditoria/resumen', methods=['GET'])
def auditoria_resumen():
    try:
        return jsonify(auditoria_service.resumen()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/auditoria/documentos', methods=['GET','POST'])
def auditoria_documentos():
    if request.method == 'POST':
        try:
            payload = request.get_json(force=True)
            result = auditoria_service.registrar_documento(
                proveedor_data=payload.get("proveedor", {}),
                documento_data=payload.get("documento", {}),
                lineas=payload.get("lineas", []),
            )
            return jsonify({"status": "success", **result}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            proveedor = request.args.get('proveedor') or None
            estado = request.args.get('estado') or None
            marca = request.args.get('marca') or None
            mes = request.args.get('mes') or None
            souche = request.args.get('souche') or None
            limit = int(request.args.get('limit', 200))
            data = auditoria_service.explorador(
                proveedor=proveedor,
                estado=estado,
                marca=marca,
                mes=mes,
                souche=souche,
                limit=limit,
            )
            return jsonify({"items": data}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route('/api/auditoria/documentos/<int:documento_id>', methods=['GET'])
def auditoria_detalle_documento(documento_id):
    try:
        data = auditoria_service.detalle_documento(documento_id)
        if data is None:
            return jsonify({"error": "Documento no encontrado"}), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/auditoria/plan-vs-recepcion', methods=['GET'])
def auditoria_plan_vs_recepcion():
    try:
        proveedor = request.args.get('proveedor') or None
        marca = request.args.get('marca') or None
        mes = request.args.get('mes') or None
        souche = request.args.get('souche') or None
        limit = int(request.args.get('limit', 500))
        data = auditoria_service.plan_vs_recepcion(
            proveedor=proveedor,
            marca=marca,
            mes=mes,
            souche=souche,
            limit=limit,
        )
        return jsonify({"items": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/auditoria/def/recepciones-posteriores', methods=['GET'])
def auditoria_recepciones_posteriores():
    try:
        # 1. Extraemos las variables que viajan desde el frontend de Streamlit
        mes_target = request.args.get("mes")  # Viene en formato '2026-03'
        souche = request.args.get("souche") or None
        proveedor = request.args.get("proveedor") or None
        marca = request.args.get("marca") or None

        if not mes_target:
            return jsonify({"error": "Falta el parámetro requerido 'mes' (YYYY-MM)"}), 400

        # 2. CORRECCIÓN: Llamamos al nombre de función REAL que tenés en tu auditoria_service.py
        data = auditoria_service.recepciones_posteriores_def(
            proveedor=proveedor,
            marca=marca,
            mes=mes_target,
            souche=souche
        )
        
        return jsonify({"status": "success", "items": data}), 200
    except Exception as e:
        print(f"❌ ERROR EN ENDPOINT REZAGOS (Pestaña 3): {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auditoria/sync/cegid', methods=['POST'])
def auditoria_sync_cegid():
    try:
        payload = request.get_json(silent=True) or {}
        mes_target = payload.get("mes_target")
        souche = payload.get("souche") or None
        
        if not mes_target:
            return jsonify({"error": "Falta el parámetro requerido 'mes_target' (YYYY-MM)"}), 400

        # Llamamos al nuevo servicio automatizado que calcula las ventanas de forma interna
        result = auditoria_service.sincronizar_circuito_cegid(
            mes_target=mes_target,
            souche=souche
        )
        return jsonify({"status": "success", **result}), 200
    except Exception as e:
        # Esto te va a mostrar en la consola de Docker el error exacto si vuelve a fallar
        print(f"❌ ERROR CRÍTICO EN SYNC: {str(e)}") 
        return jsonify({"error": str(e)}), 500


@app.route('/api/procesos-especiales/sync-novedades', methods=['POST'])
def procesos_especiales_sync_novedades():
    if not _SYNC_NOVEDADES_DISPONIBLE:
        return jsonify({"error": "Sync NOVEDADES no disponible en este entorno"}), 503
    try:
        uploaded_file = request.files.get("file")
        if uploaded_file:
            _, uploaded_ext = os.path.splitext(uploaded_file.filename)
            if uploaded_ext.lower() not in {".xlsx", ".xls"}:
                return jsonify({"error": "El tipo de archivo no es el esperado. Por favor, subí un archivo Excel."}), 400
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = secure_filename(f"SYNC_NOVEDADES_{ts}_{uploaded_file.filename}")
            excel_path = os.path.join(UPLOAD_FOLDER, filename)
            uploaded_file.save(excel_path)
            dry_run = str(request.form.get("dry_run", "true")).lower() in {"1", "true", "yes", "si"}
            send_email = str(request.form.get("send_email", "false")).lower() in {"1", "true", "yes", "si"}
        else:
            payload = request.get_json(silent=True) or {}
            excel_path = payload.get("excel_path") or None
            dry_run = bool(payload.get("dry_run", True))
            send_email = bool(payload.get("send_email", False))

        result = run_sync_novedades(
            dry_run=dry_run,
            excel_path=excel_path,
            send_email=send_email,
        )
        return jsonify({"status": "success", **result}), 200
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/abm-articulos/catalogos', methods=['GET'])
def abm_articulos_catalogos():
    try:
        return jsonify(abm_obtener_catalogos()), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/borradores', methods=['GET'])
def abm_articulos_borradores():
    try:
        return jsonify({"items": abm_listar_borradores()}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/borradores', methods=['POST'])
def abm_articulos_crear_borrador():
    try:
        payload = request.get_json(force=True) or {}
        result = abm_crear_borrador(payload)
        return jsonify({"status": "success", **result}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/borradores/<int:borrador_id>', methods=['DELETE'])
def abm_articulos_eliminar_borrador(borrador_id):
    try:
        deleted = abm_eliminar_borrador(borrador_id)
        if not deleted:
            return jsonify({"error": "Borrador no encontrado"}), 404
        return jsonify({"status": "success"}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/borradores', methods=['DELETE'])
def abm_articulos_eliminar_borradores():
    try:
        payload = request.get_json(silent=True) or {}
        deleted = abm_eliminar_borradores(payload.get("ids", []))
        return jsonify({"status": "success", "deleted": deleted}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/exportar', methods=['POST'])
def abm_articulos_exportar():
    try:
        payload = request.get_json(silent=True) or {}
        result = abm_exportar_borradores(payload.get("ids", []))
        backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
        return jsonify({
            "status": "success",
            **result,
            "download_url": f"{backend_url}/api/download/{result['filename']}",
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/complementarios', methods=['GET'])
def abm_articulos_complementarios():
    try:
        return jsonify({"items": abm_listar_complementarios()}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/complementarios/<int:comp_id>', methods=['PUT'])
def abm_articulos_actualizar_complementario(comp_id):
    try:
        payload = request.get_json(force=True) or {}
        item = abm_actualizar_complementario(comp_id, payload)
        if item is None:
            return jsonify({"error": "Complementario no encontrado"}), 404
        return jsonify({"status": "success", "item": item}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/complementarios', methods=['DELETE'])
def abm_articulos_eliminar_complementarios():
    try:
        payload = request.get_json(silent=True) or {}
        deleted = abm_eliminar_complementarios(
            comp_ids=payload.get("ids", []),
            borrar_todo=bool(payload.get("all", False)),
        )
        return jsonify({"status": "success", "deleted": deleted}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/abm-articulos/complementarios/exportar', methods=['POST'])
def abm_articulos_exportar_complementarios():
    try:
        payload = request.get_json(silent=True) or {}
        result = abm_exportar_complementarios(payload.get("ids", []))
        backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
        return jsonify({
            "status": "success",
            **result,
            "download_url": f"{backend_url}/api/download/{result['filename']}",
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Mapa de procesadores ──────────────────────────────────────────────────────
# Cada entrada: {"func": <función>, "ext": <extensión de salida>}
# Agregar un nuevo procesador = agregar una sola línea aquí.
PROCESSOR_MAP = {
    # Pedido Proveedor
    "adidas":           {"func": process_adidas_pedido_proveedor,   "ext": ".csv"},
    "bestsox":          {"func": process_bestsox_pedido_proveedor,  "ext": ".csv"},
    "braku":            {"func": process_braku_pedido_proveedor,    "ext": ".csv"},
    "diadora":          {"func": process_diadora_pedido_proveedor,  "ext": ".csv"},
    # "distrinando":    {"func": process_distrinando_pedido_proveedor, "ext": ".csv"},
    "johnfoos":         {"func": process_johnfoos_pedido_proveedor, "ext": ".csv"},
    "kdy":              {"func": process_kdy_pedido_proveedor,      "ext": ".csv"},
    "kosiuko":          {"func": process_kosiuko_pedido_proveedor,  "ext": ".csv"},
    "leuru":            {"func": process_leuru_pedido_proveedor,    "ext": ".csv"},
    "procer":           {"func": process_procer_pedido_proveedor,    "ext": ".csv"},
    "proyec":           {"func": process_proyec_pedido_proveedor,     "ext": ".csv"},
    "puma":             {"func": process_puma_pedido_proveedor,     "ext": ".csv"},
    "saucony":          {"func": process_saucony_pedido_proveedor,  "ext": ".csv"},
    "topper":           {"func": process_topper_pedido_proveedor,   "ext": ".csv"},
    # Propuesta de Compra
    "adidas_propuesta": {"func": process_adidas_propuesta_compra,  "ext": ".csv"},
    "nike":             {"func": process_nike_propuesta_compra,     "ext": ".csv"},
    "puma_propuesta":   {"func": process_puma_propuesta_compra,    "ext": ".csv"},
    "topper_propuesta": {"func": process_topper_propuesta_compra,  "ext": ".zip"},
    # Procesos Especiales
    "arca":             {"func": process_arca_procesos_especiales,      "ext": ".xlsx"},
    "mayorista":        {"func": process_mayorista_procesos_especiales, "ext": ".xlsx"},
    **( {"gastos":      {"func": process_gastos_procesos_especiales,    "ext": ".zip"}} if _GASTOS_DISPONIBLE else {} ),
    **( {"sevillanita": {"func": process_sevillanitaV2_procesos_especiales, "ext": ".zip"}} if _SEVILLANITA_DISPONIBLE else {} ),
}

# Extensión de ENTRADA esperada por cada procesador
EXPECTED_INPUT_EXT = {
    "adidas":           ".xlsx",
    "bestsox":          ".xlsx",
    "braku":            ".xlsx",
    "diadora":          ".xlsx",
    "distrinando":      ".xlsx",
    "johnfoos":         ".xlsx",
    "kdy":              ".xlsx",
    "kosiuko":          ".txt",
    "leuru":            ".txt",
    "procer":           ".xlsx",
    "proyec":           ".xlsx",
    "puma":             ".csv",
    "saucony":          ".xlsx",
    "topper":           ".txt",
    "adidas_propuesta": ".xlsx",
    "nike":             ".xlsx",
    "puma_propuesta":   ".xlsx",
    "topper_propuesta": ".xlsx",
    "arca":             ".xlsx",
    "gastos":           ".xlsx",
    "mayorista":        ".xlsx",
    "sevillanita":      ".xlsx",
}

AUDITORIA_PROMOS_PROVIDER_KEYS = {
    "adidas",
    "bestsox",
    "braku",
    "diadora",
    "johnfoos",
    "kdy",
    "kosiuko",
    "leuru",
    "procer",
    "proyec",
    "puma",
    "saucony",
    "topper",
    "adidas_propuesta",
    "nike",
    "puma_propuesta",
    "topper_propuesta",
}


def _origen_auditoria_promos(provider_key: str) -> str:
    return "PROPUESTA_COMPRA" if provider_key.endswith("_propuesta") or provider_key == "nike" else "PEDIDO_PROVEEDOR"


def _leer_codigos_barras_de_salida(path: str) -> list:
    if not path or not os.path.exists(path):
        return []

    codigos = []

    def cargar_filas(file_obj):
        reader = csv.DictReader(file_obj, delimiter="|")
        for row in reader:
            codigo = (row.get("CODIGO BARRAS") or row.get("Codigo Barras") or "").strip()
            if codigo:
                codigos.append(codigo)

    try:
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    with zf.open(name) as raw:
                        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                        cargar_filas(text)
        else:
            with open(path, newline="", encoding="utf-8-sig") as file_obj:
                cargar_filas(file_obj)
    except Exception as e:
        print(f"Error leyendo codigos de barras para auditoria de promos: {e}")

    return list(dict.fromkeys(codigos))


@app.route('/api/process/<provider_id>', methods=['POST'])
def process_file(provider_id):
    provider_key = provider_id.lower()
    config = PROCESSOR_MAP.get(provider_key)
    if not config:
        return jsonify({"error": "Procesador no encontrado"}), 404

    files = request.files.getlist('files') if provider_key == "sevillanita" else []
    file = request.files.get('file')
    if provider_key == "sevillanita":
        if len(files) != 2:
            return jsonify({"error": "Sevillanita requiere dos archivos .xlsx"}), 400
    elif not file:
        return jsonify({"error": "No se recibió archivo"}), 400

    # Validación de tipo de archivo de entrada
    expected_ext = EXPECTED_INPUT_EXT.get(provider_key)
    if expected_ext:
        files_to_validate = files if provider_key == "sevillanita" else [file]
        for uploaded_file in files_to_validate:
            _, uploaded_ext = os.path.splitext(uploaded_file.filename)
            if uploaded_ext.lower() != expected_ext.lower():
                return jsonify({
                    "error": f"El tipo de archivo no es el esperado. Por favor, procesá un archivo {expected_ext.upper()}"
                }), 400

    input_path = None
    input_paths = []
    if provider_key == "sevillanita":
        for uploaded_file in files:
            filename = secure_filename(uploaded_file.filename)
            saved_path = os.path.join(UPLOAD_FOLDER, filename)
            uploaded_file.save(saved_path)
            input_paths.append(saved_path)
    else:
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

    processor_func = config["func"]
    base_ext = config["ext"]
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{provider_id.upper()}_{ts}{base_ext}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        processor_input = input_paths if provider_key == "sevillanita" else input_path
        result = processor_func(processor_input, output_path)
        result_output_path = output_path

        if isinstance(result, str):
            result_output_path = result
            output_filename = os.path.basename(result)
            result = {"output_path": result}
        elif isinstance(result, dict) and result.get("output_path"):
            result_output_path = result["output_path"]

        # Detectar si el resultado contiene datos de auditoría
        audit_report = {
            "faltantes": [],
            "cambios_precio": [],
            "actualizar_ean": [],
            "alertas_promos": [],
            "articulos_promos_chequeados": [],
            "conflictos_suc": [],
            "ean_vacios": [],
            "campos_requeridos_vacios": [],
            "codigos_barras_no_encontrados": [],
            "codigos_barras_completados": [],
            "alertas_sucursales": [],
            "avisos_sucursales": [],
            "avisos_generales": [],
            "sevillanita": {},
        }
        has_audit = False
        message = None
        archivos_extra = []

        ya_audito_promos = isinstance(result, dict) and "alertas_promos" in result
        if provider_key in AUDITORIA_PROMOS_PROVIDER_KEYS and not ya_audito_promos:
            codigos_barras_promos = _leer_codigos_barras_de_salida(result_output_path)
            codigos_promos_chequeados = resolver_codigos_articulo_para_auditoria_promos(
                codigos_barras=codigos_barras_promos,
            )
            alertas_promos = auditar_promos_articulos(
                codigos_articulo=codigos_promos_chequeados,
                proveedor=provider_id.upper(),
                origen=_origen_auditoria_promos(provider_key),
            )
            if not isinstance(result, dict):
                result = {}
            result["articulos_promos_chequeados"] = [
                {"Articulo": codigo}
                for codigo in codigos_promos_chequeados
            ]
            if alertas_promos:
                result["alertas_promos"] = alertas_promos
            elif codigos_promos_chequeados:
                result.setdefault("alertas_promos", [])
                result.setdefault("avisos_generales", []).append(
                    "Todos los articulos chequeados tienen promo N/A."
                )

        if isinstance(result, dict):
            message = result.get('mensaje')
            archivos_extra = result.get('archivos_extra') or []
            if result.get("output_path"):
                output_filename = os.path.basename(result["output_path"])
            tiene_alertas = (
                result.get('faltantes')
                or result.get('cambios_precio')
                or result.get('actualizar_ean')
                or result.get('alertas_promos')
                or result.get('articulos_promos_chequeados')
                or result.get('conflictos_suc')
                or result.get('ean_vacios')
                or result.get('campos_requeridos_vacios')
                or result.get('codigos_barras_no_encontrados')
                or result.get('codigos_barras_completados')
                or result.get('alertas_sucursales')
                or result.get('avisos_sucursales')
                or result.get('avisos_generales')
                or result.get('mensaje')
                or result.get('sevillanita')
            )
            if tiene_alertas:
                audit_report = result
                has_audit = True

        # ── Empacar en ZIP si hay variaciones de precio ───────────────────────
        # Se genera siempre que haya cambios_precio, independientemente del procesador.
        cambios = audit_report.get('cambios_precio', [])
        if cambios and os.path.exists(output_path):
            proveedor_slug = provider_id.upper()
            zip_path = generar_zip_con_variaciones(
                csv_importacion_path=output_path,
                cambios_precio=cambios,
                proveedor=proveedor_slug,
                output_folder=OUTPUT_FOLDER,
                ts=ts,
            )
            if archivos_extra:
                with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
                    for extra_path in archivos_extra:
                        if os.path.exists(extra_path):
                            zf.write(extra_path, os.path.basename(extra_path))
                            os.remove(extra_path)
            output_filename = os.path.basename(zip_path)
        elif archivos_extra and os.path.exists(output_path):
            proveedor_slug = provider_id.upper()
            base = f"{proveedor_slug}_{ts}"
            import_filename = f"{base}_IMPORTACION.csv"
            import_path = os.path.join(OUTPUT_FOLDER, import_filename)
            os.rename(output_path, import_path)

            zip_filename = f"{base}.zip"
            zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(import_path, import_filename)
                for extra_path in archivos_extra:
                    if os.path.exists(extra_path):
                        zf.write(extra_path, os.path.basename(extra_path))

            for cleanup_path in [import_path, *archivos_extra]:
                if os.path.exists(cleanup_path):
                    os.remove(cleanup_path)

            output_filename = zip_filename

        backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
        return jsonify({
            "status": "success",
            "filename": output_filename,
            "download_url": f"{backend_url}/api/download/{output_filename}",
            "audit": audit_report,
            "has_audit": has_audit,
            "message": message,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return jsonify({"error": "Archivo no encontrado"}), 404
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    # host='0.0.0.0' permite conexiones externas al servidor
    app.run(host='0.0.0.0', port=5000)
