import os
import sys

# ── Path setup: debe ir PRIMERO para que todos los imports de backend.* funcionen
# tanto al ejecutar como script (py backend/app.py) como al importar como módulo.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, '..')))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from backend.utils.pedido_helpers import generar_zip_con_variaciones
from backend.database import DB_AUTH_TYPE, DB_HOST, DB_NAME, _HOSTNAME

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

# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

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
    "procer":           {"func": process_procer_pedido_proveedor,   "ext": ".csv"},
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


@app.route('/api/process/<provider_id>', methods=['POST'])
def process_file(provider_id):
    config = PROCESSOR_MAP.get(provider_id.lower())
    if not config:
        return jsonify({"error": "Procesador no encontrado"}), 404

    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No se recibió archivo"}), 400

    # Validación de tipo de archivo de entrada
    expected_ext = EXPECTED_INPUT_EXT.get(provider_id.lower())
    if expected_ext:
        _, uploaded_ext = os.path.splitext(file.filename)
        if uploaded_ext.lower() != expected_ext.lower():
            return jsonify({
                "error": f"El tipo de archivo no es el esperado. Por favor, procesá un archivo {expected_ext.upper()}"
            }), 400

    filename = secure_filename(file.filename)
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(input_path)

    processor_func = config["func"]
    base_ext = config["ext"]
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{provider_id.upper()}_{ts}{base_ext}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        result = processor_func(input_path, output_path)

        # Detectar si el resultado contiene datos de auditoría
        audit_report = {"faltantes": [], "cambios_precio": [], "actualizar_ean": [], "conflictos_suc": []}
        has_audit = False

        if isinstance(result, dict):
            tiene_alertas = (
                result.get('faltantes')
                or result.get('cambios_precio')
                or result.get('actualizar_ean')
                or result.get('conflictos_suc')
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
            output_filename = os.path.basename(zip_path)

        backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
        return jsonify({
            "status": "success",
            "filename": output_filename,
            "download_url": f"{backend_url}/api/download/{output_filename}",
            "audit": audit_report,
            "has_audit": has_audit,
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