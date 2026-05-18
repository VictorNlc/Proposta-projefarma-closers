# ============================================================================
# APLICAÇÃO FLASK - INTERFACE WEB COM 100% DE PRECISÃO
# ============================================================================

import os
import json
import base64
import io
import time
from flask import Flask, request, jsonify, render_template, send_file
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
from PIL import Image
from precision_analyzer import PrecisionAnalyzer
from catalog import find_catalog_item
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app) # Habilita CORS para todas as origens, permitindo requisições do Lovable
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DEBUG_FOLDER'] = 'debug'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DEBUG_FOLDER'], exist_ok=True)

# Inicializa analisador de forma preguiçosa (lazy) no endpoint para não quebrar o boot do Render
analyzer = None

# ============================================================================
# ROTAS
# ============================================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/renderizar-pdf", methods=["POST"])
def renderizar_pdf():
    """Renderiza página do PDF em baixa resolução para o canvas."""
    pdf_file = request.files.get("pdf")
    pagina = int(request.form.get("pagina", 1))
    
    if not pdf_file:
        return jsonify({"erro": "Nenhum PDF enviado"}), 400
    
    try:
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if pagina < 1 or pagina > len(doc):
            return jsonify({"erro": f"Página {pagina} inválida"}), 400
        
        page = doc[pagina - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Converte para base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return jsonify({
            "imagem": b64,
            "largura": pix.width,
            "altura": pix.height,
            "paginas": len(doc)
        })
    
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/analisar", methods=["POST"])
def analisar():
    """Analisa recortes com 100% de precisão."""
    global analyzer
    if not analyzer:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"erro": "A chave OPENAI_API_KEY não está configurada no servidor. Por favor, adicione-a nas variáveis de ambiente do Render."}), 500
        analyzer = PrecisionAnalyzer(api_key)
    pdf_file = request.files.get("pdf")
    pagina = int(request.form.get("pagina", 1))
    recortes_json = request.form.get("recortes", "[]")
    cliente = request.form.get("cliente", "Proposta")
    rotacionar = request.form.get("rotacionar", "false") == "true"
    
    if not pdf_file:
        return jsonify({"erro": "Nenhum PDF enviado"}), 400
    
    try:
        recortes = json.loads(recortes_json)
        
        # Deduplica recortes sobrepostos
        # Não deduplicar recortes sobrepostos – queremos contar todas as ocorrências lidas pela IA
        recortes_deduplic = recortes
        
        pdf_bytes = pdf_file.read()
        ZOOM_IA = 8.0
        scale_x = scale_y = 2.0
        
        # Acumula inventário consolidado (deduplicado) e total bruto (inclui todas as ocorrências)
        inventario_consolidado = {}
        raw_total = 0
        logs = []
        
        for i, recorte in enumerate(recortes_deduplic):
            try:
                # Extrai recorte do PDF
                doc_local = fitz.open(stream=pdf_bytes, filetype="pdf")
                page_local = doc_local[pagina - 1]
                
                x1, y1, w, h = recorte["x"], recorte["y"], recorte["width"], recorte["height"]
                x1_pdf, y1_pdf = x1 / scale_x, y1 / scale_y
                x2_pdf, y2_pdf = (x1 + w) / scale_x, (y1 + h) / scale_y
                
                rect = fitz.Rect(x1_pdf, y1_pdf, x2_pdf, y2_pdf)
                
                # Dynamic crop zoom: Ensure the cropped image has at least 600px in its largest dimension
                # Cap the zoom factor between 8.0 and 30.0 to make tiny texts perfectly crisp without memory issues.
                max_dim = max(rect.width, rect.height)
                zoom_factor = max(8.0, min(30.0, 600.0 / max_dim)) if max_dim > 0 else 8.0
                
                pix = page_local.get_pixmap(matrix=fitz.Matrix(zoom_factor, zoom_factor), clip=rect)
                crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                rotation_angle = recorte.get("rotacao", 0)
                if rotation_angle == 0 and rotacionar:
                    rotation_angle = 180
                
                if rotation_angle == 90:
                    crop_img = crop_img.rotate(270, expand=True)
                elif rotation_angle == 180:
                    crop_img = crop_img.rotate(180)
                elif rotation_angle == 270:
                    crop_img = crop_img.rotate(90, expand=True)
                
                # Salva para debug
                debug_path = os.path.join(app.config['DEBUG_FOLDER'], f"crop_{i}_{int(time.time()*1000)}.png")
                crop_img.save(debug_path)
                
                # Analisa com sistema Híbrido (OCR Local + OpenAI Vision)
                resultados_recorte = analyzer.analyze_image(crop_img)
                
                # Regra especial para PF 807 baseada na altura (tamanho Y do recorte)
                # Se a altura for maior ou igual a 51 (ex: entre 55 e 57), vira "PF 807 COM FUNDO".
                # Se for menor que 51 (ex: ~45), continua "PF 807" normal.
                h_recorte = recorte.get("height", 0)
                for r in resultados_recorte:
                    if r["item"] == "PF 807":
                        if h_recorte >= 51:
                            r["item"] = "PF 807 COM FUNDO"
                            analyzer._log(f"[Altura Recorte] PF 807 convertido para PF 807 COM FUNDO (altura: {h_recorte})")
                        else:
                            analyzer._log(f"[Altura Recorte] PF 807 mantido como PF 807 normal (altura: {h_recorte})")
                
                # Consolida o que foi achado neste recorte específico
                inventario_recorte = analyzer.consolidate(resultados_recorte)
                
                # Atualiza inventário consolidado (deduplicado entre recortes)
                for nome, qty in inventario_recorte.items():
                    inventario_consolidado[nome] = inventario_consolidado.get(nome, 0) + qty
                
                # Soma quantidade bruta (conta todas as ocorrências antes de deduplicar entre recortes)
                raw_total += sum(inventario_recorte.values())
                
                logs.append({
                    "recorte": i + 1,
                    "status": "OK",
                    "itens_encontrados": [
                        {"nome": r["item"], "qty": r.get("qty", 1), "fonte": r.get("fonte", "?")}
                        for r in resultados_recorte
                    ],
                    "raw_ai_data": getattr(analyzer, 'last_raw_ai_data', None),
                    "debug_image": f"/api/debug-image/{os.path.basename(debug_path)}",
                    "consolidado": {k: v for k, v in inventario_recorte.items()},
                    "total": sum(inventario_recorte.values())
                })
                
                doc_local.close()
            
            except Exception as e:
                logs.append({
                    "recorte": i + 1,
                    "status": "ERRO",
                    "erro": str(e)
                })
        
        # Formata resposta
        inventario_final = [
            {"nome": nome, "quantidade": qty}
            for nome, qty in sorted(inventario_consolidado.items())
        ]
        
        # Usa o total deduplicado (soma das quantidades no inventário consolidado)
        total = sum(item["quantidade"] for item in inventario_final)
        
        # Valida
        validacao = analyzer.validate_total(inventario_final)
        
        return jsonify({
            "inventario": inventario_final,
            "total": total,
            "num_tipos": len(inventario_final),
            "logs": logs,
            "validacao": validacao,
            "cliente": cliente
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

@app.route('/api/debug-image/<filename>')
def serve_debug_image(filename):
    """Serve as imagens de recorte salvas na pasta debug para auditoria."""
    return send_file(os.path.join(app.config['DEBUG_FOLDER'], secure_filename(filename)))

@app.route("/api/exportar-excel", methods=["POST"])
def exportar_excel():
    """Exporta inventário para Excel."""
    data = request.get_json()
    inventario = data.get("inventario", [])
    cliente = data.get("cliente", "Proposta")
    
    # Cria workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventário"
    
    # Estilos
    header_fill = PatternFill(start_color="1a1f3a", end_color="1a1f3a", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    header_align = Alignment(horizontal="center", vertical="center")
    
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 15
    ws.row_dimensions[1].height = 30
    
    # Cabeçalho
    ws["A1"] = "PRODUTO"
    ws["B1"] = "QUANTIDADE"
    for cell in [ws["A1"], ws["B1"]]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
    
    # Dados
    alt_fill = PatternFill(start_color="f0f4ff", end_color="f0f4ff", fill_type="solid")
    for i, item in enumerate(inventario, start=2):
        ws[f"A{i}"] = item["nome"]
        ws[f"B{i}"] = item["quantidade"]
        ws[f"B{i}"].alignment = Alignment(horizontal="center")
        if i % 2 == 0:
            ws[f"A{i}"].fill = alt_fill
            ws[f"B{i}"].fill = alt_fill
    
    # Total
    total_row = len(inventario) + 3
    ws[f"A{total_row}"] = "TOTAL"
    ws[f"B{total_row}"] = sum(item["quantidade"] for item in inventario)
    for cell in [ws[f"A{total_row}"], ws[f"B{total_row}"]]:
        cell.font = Font(bold=True, size=12)
        cell.fill = PatternFill(start_color="00d4ff", end_color="00d4ff", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Salva
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    
    filename = f"inventario_{cliente.replace(' ', '_')}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/api/exportar-json", methods=["POST"])
def exportar_json():
    """Exporta inventário para JSON."""
    data = request.get_json()
    inventario = data.get("inventario", [])
    cliente = data.get("cliente", "Proposta")
    
    output = {
        "cliente": cliente,
        "data": time.strftime("%Y-%m-%d %H:%M:%S"),
        "inventario": inventario,
        "total": sum(item["quantidade"] for item in inventario),
        "num_tipos": len(inventario)
    }
    
    buf = io.BytesIO()
    buf.write(json.dumps(output, indent=2, ensure_ascii=False).encode('utf-8'))
    buf.seek(0)
    
    filename = f"inventario_{cliente.replace(' ', '_')}.json"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/json"
    )

@app.route("/health", methods=["GET"])
def health():
    """Verificação de saúde."""
    return jsonify({"status": "ok", "version": "1.0.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
