from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carga variables de entorno
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Configuración de Paths para evitar ModuleNotFoundError
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, '..')))

# Importaciones de Procesadores
from backend.scripts.procesos_especiales.arca_processor import process_arca_procesos_especiales
from backend.scripts.pedido_proveedor.topper_processor import process_topper_pedido_proveedor
from backend.scripts.pedido_proveedor.puma_processor import process_puma_pedido_proveedor
from backend.scripts.pedido_proveedor.adida_processor import process_adidas_pedido_proveedor
from backend.scripts.pedido_proveedor.kdy_processor import process_kdy_pedido_proveedor
from backend.scripts.pedido_proveedor.bestsox_processor import process_bestsox_pedido_proveedor
from backend.scripts.pedido_proveedor.johnfoos_processor import process_johnfoos_pedido_proveedor
from backend.scripts.pedido_proveedor.diadora_processor import process_diadora_pedido_proveedor
from backend.scripts.pedido_proveedor.leuru_processor import process_leuru_pedido_proveedor
from backend.utils.control_precios_processor import controlar_precios_y_empacar

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

PROCESSOR_MAP = {
    "adidas": process_adidas_pedido_proveedor,
    "bestsox": process_bestsox_pedido_proveedor,
    # "braku": process_braku_pedido_proveedor,
    # "diadora": process_diadora_pedido_proveedor,
    "diadora": process_diadora_pedido_proveedor,
    # "distrinando": process_distrinando_pedido_proveedor,
    # "gruppo7": process_gruppo7_pedido_proveedor,
    "johnfoos": process_johnfoos_pedido_proveedor,
    "kdy": process_kdy_pedido_proveedor,
    # "kosiuko": process_kosiuko_pedido_proveedor,
    "leuru": process_leuru_pedido_proveedor,
    "puma": process_puma_pedido_proveedor,
    # "saucony": process_saucony_pedido_proveedor,
    "topper": process_topper_pedido_proveedor,
    # "adidas_propuesta": process_adidas_propuesta_proveedor,
    # "nike_propuesta": process_nike_propuesta_proveedor,
    # "puma_propuesta": process_puma_propuesta_proveedor,
    # "topper_propuesta": process_topper_propuesta_proveedor,
    "arca": {"func": process_arca_procesos_especiales, "ext": ".xlsx"},
    # "mayorista": {"func": process_mayorista_procesos_especiales, "ext": ".xlsx"},
    # "gastos": process_gastos_procesos_especiales,
    # "sevillanitaV2": process_sevillanitaV2_procesos_especiales,
}

# Extensión de ENTRADA esperada por cada procesador
EXPECTED_INPUT_EXT = {
    "adidas":   ".xlsx",
    "bestsox":  ".xlsx",
    "diadora":  ".xlsx",
    "johnfoos": ".xlsx",
    "kdy":     ".xlsx",
    "leuru":   ".txt",
    "puma":    ".csv",
    "topper":  ".txt",
    "nike":    ".xlsx",
    "arca":    ".xlsx",
    "gastos":  ".xlsx",
}

@app.route('/api/process/<provider_id>', methods=['POST'])
def process_file(provider_id):
    config = PROCESSOR_MAP.get(provider_id.lower())
    if not config:
        return jsonify({"error": "Procesador no encontrado"}), 404

    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No se recibió archivo"}), 400

    # --- VALIDACIÓN DE TIPO DE ARCHIVO ---
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

    # Determinación de función y extensión
    if isinstance(config, dict):
        processor_func = config["func"]
        extension = config["ext"]
    else:
        processor_func = config
        extension = ".csv"

    output_filename = f"{provider_id.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
            # 4. Ejecutar el proceso
            result = processor_func(input_path, output_path)
            
            # --- LÓGICA DE DETECCIÓN DE AUDITORÍA ---
            # Si el resultado es un diccionario con datos, es una auditoría. 
            # Si está vacío o es un return de 'procesos especiales', has_audit será False.
            if isinstance(result, dict) and (result.get('faltantes') or result.get('cambios_precio') or result.get('actualizar_ean') or result.get('conflictos_suc')):
                audit_report = result
                has_audit = True
            else:
                audit_report = {"faltantes": [], "cambios_precio": [], "actualizar_ean": [], "conflictos_suc": []}
                # Si el resultado es un dict, preservar conflictos_suc aunque no haya otras alertas
                if isinstance(result, dict) and result.get('conflictos_suc'):
                    audit_report['conflictos_suc'] = result['conflictos_suc']
                has_audit = False
            
            # 5. Lógica del ZIP (Solo si hay cambios de precio reales)
            if has_audit and audit_report.get("cambios_precio"):
                print("📦 Generando ZIP de precios...")
                ts_zip = datetime.now().strftime("%Y%m%d_%H%M%S")
                res_zip = controlar_precios_y_empacar(
                    output_path=output_path, 
                    now_str=ts_zip,
                    output_folder=OUTPUT_FOLDER,
                    tipo="pedido"
                )
                if res_zip and res_zip[0] == "zip":
                    output_filename = res_zip[1]

            return jsonify({
                "status": "success",
                "filename": output_filename,
                "download_url": f"{os.getenv('BACKEND_URL', 'http://localhost:5000')}/api/download/{output_filename}",
                "audit": audit_report,
                "has_audit": has_audit  # <-- Informamos al Front si debe mostrar alertas
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
    app.run(port=5000, debug=True)