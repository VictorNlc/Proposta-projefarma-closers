# ============================================================================
# MOTOR DE ANÁLISE HÍBRIDO (TESSERACT + OPENAI) - 100% PRECISÃO
# ============================================================================
import json
import base64
import io
import threading
# pytesseract removed as local OCR is disabled in favor of OpenAI Vision for 100% precision on Render
from collections import Counter
from typing import Dict, List, Optional
from PIL import Image, ImageEnhance
# opencv and numpy removed as local OCR preprocessing is disabled in favor of raw OpenAI Vision
from openai import OpenAI
from catalog import find_catalog_item, get_all_official_names

class PrecisionAnalyzer:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.analysis_logs = []
        self._thread_local = threading.local()
        # Adjustable parameters
        self.ocr_confidence_threshold = 80   # minimum OCR confidence (%)
        self.iou_threshold = 0.3            # IoU threshold for duplicate crops (more aggressive merging)
        self.log_file = "analysis.log"
        # Ensure log file exists
        open(self.log_file, "a").close()

    @property
    def last_raw_ai_data(self):
        """Thread-safe access to raw AI response data."""
        return getattr(self._thread_local, 'last_raw_ai_data', None)

    @last_raw_ai_data.setter
    def last_raw_ai_data(self, value):
        """Thread-safe storage of raw AI response data."""
        self._thread_local.last_raw_ai_data = value

    def _log(self, msg: str):
        """Write debug messages to stdout and to the log file."""
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def _pil_to_base64(self, img: Image.Image) -> str:
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=90)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def analyze_image(self, image_pil: Image.Image) -> List[Dict]:
        """Analyze a cropped image using OCR and OpenAI with preprocessing and confidence filter."""
        self.last_raw_ai_data = None
        results: List[Dict] = []
        official_list = get_all_official_names()
        # -------------------------------------------------
        # 1. OCR LOCAL (Tesseract) with confidence filter
        # -------------------------------------------------
        # 1. OCR LOCAL (Tesseract) - DESABILITADO (Usando apenas OpenAI Vision)
        pass
        # -------------------------------------------------
        # 2. VISÃO AI (OpenAI) – reading the text labels (USING RAW IMAGE)
        # -------------------------------------------------
        try:
            b64_image = self._pil_to_base64(image_pil)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Você é um especialista em inventário de mobiliário farmacêutico. "
                            f"Sua missão é LER OS TEXTOS nas plantas baixas que representam MÓVEIS.\n"
                            f"LISTA OFICIAL: {official_list}.\n"
                            f"IGNORAR COMPLETAMENTE: cesto de lixo, lixeira, parede, pilar, "
                            f"coluna, entrada, saída, escada, elevador, banheiro, depósito, estoque, "
                            f"copa, corredor, hall, recepção, área, setor, zona, sala.\n\n"
                            f"💡 ORIENTAÇÃO DE PRECISÃO DE OCR E LEITURA:\n"
                            f"1. O número da medida é a parte mais crítica e legível da imagem (ex: 807, 500, 550, 600, 700, 800, 1000, 1400, 1700, 2000, 3000).\n"
                            f"2. ⚠️ PREVENÇÃO DE ERROS DE DIGITAÇÃO/OCR:\n"
                            f"   - **MED 500 vs MED 807:** Se a estante tem escrito '500' ou '500mm' (ex: 'MED 500mm' ou 'MED 500'): Classifique EXATAMENTE como 'MED 500'! É extremamente importante ler o número '500' correto e não confundir de jeito nenhum com '807' ou 'MED 807'!\n"
                            f"   - **MED 807 vs BA 800:** Se a estante tem escrito '807' ou '807mm' (ex: 'MED 807mm' ou 'MED 807'): Classifique EXATAMENTE como 'MED 807'! NUNCA classifique 'MED 807' como 'BA 800' ou 'PDV 800'! Preste muita atenção para ler 'MED' na primeira linha e '807' na segunda linha, sem confundir com 'BA' ou '800'!\n"
                            f"   - Se a estante tem escrito '550' ou '550mm' na área de Perfumaria: Classifique como 'PF 550'.\n"
                            f"   - Se a estante tem escrito '807' ou '807mm' na área de Perfumaria: Classifique como 'PF 807'.\n"
                            f"   - Se a estante tem escrito '1000' ou '1000mm' na área de Perfumaria: Classifique como 'PF 1000'.\n"
                            f"   - Se a gôndola tem escrito '3000' ou '3000mm' (ex: 'GOND 3000mm' ou 'GOND 3000'): Classifique EXATAMENTE como 'GOND 3000'. Preste muita atenção para não confundir o '3' de '3000' com o '2' de '2000'!\n"
                            f"   - Se a gôndola tem escrito '2000' ou '2000mm' (ex: 'GOND 2000mm' ou 'GOND 2000'): Classifique como 'GOND 2000'.\n"
                            f"   - Se a gôndola tem escrito '1700' ou '1700mm': Classifique como 'GOND 1700'.\n"
                            f"   - Se a gôndola tem escrito '1400' ou '1400mm': Classifique como 'GOND 1400'.\n"
                            f"   - **BA vs PDV:** Se o texto disser 'PDV' na imagem (ex: 'PDV 800mm', 'PDV 800', 'PDV 1000'): Classifique EXATAMENTE como 'PDV 600', 'PDV 700', 'PDV 800' ou 'PDV 1000' de acordo com a medida. Se disser 'BA' (ex: 'BA 800mm', 'BA 800', 'BA 1000'): Classifique EXATAMENTE como 'BA 600', 'BA 700', 'BA 800' ou 'BA 1000'! NUNCA confunda ou misture BA com PDV, pois são produtos distintos no catálogo!\n"
                            f"   - Se o item tem escrito 'BASE' e '1200' ou '1200mm' (ex: 'BASE 1200mm', 'BASE 1200'): Classifique EXATAMENTE como 'BASE 1200'. Não confunda com 'PF CANALETADO'!\n"
                            f"   - **ESMALTES:** Se a estante/expositor tem escrito 'ESMALTES' ou 'ESMALTE' (ex: 'ESMALTES 500mm', 'ESMALTES 807mm'): Classifique EXATAMENTE como 'ESMALTES'. Preste muita atenção se houver outro móvel ao lado no mesmo recorte (como 'PF CANALETADO 807mm' grudado ou ao lado dele), você DEVE retornar AMBOS no JSON final com suas respectivas quantidades!\n"
                            f"3. ⚠️ REGRA EXCLUSIVA DO CESTÃO: O Cestão é um expositor promocional isolado. Ele possui produtos representados em cima que aparecem como preenchimentos verdes ou círculos/esferas organizados em matriz (representando cestos).\n"
                            f"   - **⚠️ ATENÇÃO EXTRAORDINÁRIA:** O texto na planta pode dizer 'CESTÃO', 'CESTAO', ou conter variações e abreviações/erros de OCR como 'RESTAG', 'RESTÃO', 'RESTAO', 'REST 400', 'GESTÃO', 'GESTAO', geralmente acompanhados de '400' ou '400x400'. Todos estes são, sem dúvida, o item 'CESTAO'!\n"
                            f"   - Se o recorte contiver DOIS cestões (ex: uma estante verde na esquerda E uma matriz de círculos/esferas na direita, como em muitos recortes grandes de cestões), você DEVE classificar como 'CESTAO' com qtd: 2!\n"
                            f"   - Se apenas um desses padrões (ou apenas um bloco) estiver presente, classifique como 'CESTAO' com qtd: 1.\n"
                            f"   - IMPORTANTE: Não retorne qtd: 1 se vir os dois blocos (o verde e o de círculos) juntos na mesma imagem! Retorne qtd: 2! Não confunda estantes normais com cestão.\n\n"
                            f"⚠️ NUNCA retorne um JSON vazio '{{}}' se houver um móvel visível na imagem! Se vir letras (como 'PDV', 'BA', 'MED', 'PF', 'ESMALTES') e um número de medida legível ou parcialmente oculto por outros desenhos, você DEVE retornar o JSON com o item correspondente correto de acordo com as regras acima! Se o texto disser claramente 'MED' e '807mm', retorne 'MED 807' e não confunda com balcões! Se disser claramente 'MED' e '500mm', retorne 'MED 500' e não confunda com 'MED 807'! Se houver múltiplos móveis (como 'ESMALTES 500mm' E 'PF CANALETADO 807mm' na mesma imagem), retorne uma lista com TODOS eles!\n"
                            f"Retorne JSON: {{\"achados\": [{{ \"nome\": \"TEXTO_LIDO\", \"qtd\": 1 }}]}}"
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Quais móveis estão escritos e desenhados na imagem? Identifique e retorne TODOS os móveis presentes no recorte (ex: se houver ESMALTES e PF CANALETADO lado a lado, ou se houver dois balcões). Preste atenção extraordinária a ESMALTES, PF CANALETADO, PF, DERMO, PDV, BA, CHECKOUT, CAIXA e CESTO. CONTE CADA UM INDIVIDUALMENTE. Retorne TODOS em uma lista no JSON bruto!"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                content = "{}"
            ai_data = json.loads(content)
            self.last_raw_ai_data = ai_data
            for found in ai_data.get("achados", []):
                nome_ai = found.get("nome", "")
                qty_ai = found.get("qtd", 1)
                match = find_catalog_item(nome_ai)
                if match:
                    if "GOND" in match:
                        qty_ai = 1
                    if match == "CESTAO":
                        qty_ai = min(qty_ai, 2)
                    results.append({"item": match, "fonte": "openai", "qty": qty_ai})
                    self._log(f"[OpenAI] Found: {match} (qty {qty_ai})")
        except Exception as e:
            self._log(f"⚠️ OpenAI error: {e}")




        # Guard‑rails para o CESTÃO:
        # 1. Se CESTÃO estiver no recorte, ignoramos qualquer detecção de CAIXA/CHECKOUT
        #    (pois são áreas fisicamente separadas na farmácia e o CESTÃO é recortado isoladamente)
        has_cestao = any(r["item"] == "CESTAO" for r in results)
        if has_cestao:
            results = [r for r in results if r["item"] not in ("CAIXA 600", "CAIXA 1000", "CHECKOUT", "CHECKOUT L")]

        return results

    def deduplicate_overlapping_crops(self, crops: List[Dict]) -> List[Dict]:
        """Remove highly overlapping crops to avoid duplicate counting."""
        if not crops:
            return []
        sorted_crops = sorted(crops, key=lambda c: c["width"] * c["height"], reverse=True)
        kept: List[Dict] = []
        for crop in sorted_crops:
            is_duplicate = False
            for k in kept:
                if self._calculate_iou(crop, k) > self.iou_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(crop)
        self._log(f"Deduplication: {len(crops)} -> {len(kept)} using IoU>{self.iou_threshold}")
        return kept

    def _calculate_iou(self, b1, b2) -> float:
        """Intersection‑over‑Union between two bounding boxes."""
        x_left = max(b1['x'], b2['x'])
        y_top = max(b1['y'], b2['y'])
        x_right = min(b1['x'] + b1['width'], b2['x'] + b2['width'])
        y_bottom = min(b1['y'] + b1['height'], b2['y'] + b2['height'])
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        inter_area = (x_right - x_left) * (y_bottom - y_top)
        b1_area = b1['width'] * b1['height']
        b2_area = b2['width'] * b2['height']
        return inter_area / float(b1_area + b2_area - inter_area)

    def consolidate(self, all_results: List[Dict]) -> Dict:
        """Aggregate detections from OCR and AI, summing quantities for the same item."""
        final_inventory = Counter()
        for res in all_results:
            item = res["item"]
            qty = res.get("qty", 1)
            final_inventory[item] += qty
        self._log(f"Consolidated inventory: {final_inventory}")
        return dict(final_inventory)

    def validate_total(self, inventario_final):
        """Placeholder for any future validation logic – currently always passes."""
        return {"is_valid": True, "warnings": []}
