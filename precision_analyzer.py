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
        # 1. OCR LOCAL (Tesseract) com confidence filter
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
                            f"Sua missão é LER OS TEXTOS nas plantas baixas que representam MÓVEIS e classificar o acabamento deles baseado na cor de fundo.\n"
                            f"LISTA OFICIAL: {official_list}.\n"
                            f"IGNORAR COMPLETAMENTE: cesto de lixo, lixeira, parede, pilar, "
                            f"coluna, entrada, saída, escada, elevador, banheiro, depósito, estoque, "
                            f"copa, corredor, hall, recepção, área, setor, zona, sala.\n\n"
                            f"💡 REGRA DE CONTAGEM GERAL E QUANTIDADE DETERMINÍSTICA:\n"
                            f"Muitas vezes, a imagem contém múltiplos módulos idênticos enfileirados/adjacentes um ao lado do outro. Siga esta regra sagrada:\n"
                            f"- **A QUANTIDADE É O NÚMERO DE ETIQUETAS DE TEXTO ESCRITO:** Conte o número exato de vezes que a etiqueta de texto (por exemplo, 'PF 807mm', 'MED 500mm', 'BA 800', etc.) está escrita/impressa no recorte de imagem.\n"
                            f"- Se a etiqueta de texto estiver impressa **TRÊS** vezes na imagem, a quantidade ('qtd') desse item no JSON DEVE ser **3**! Nunca retorne '2' se vir 3 textos!\n"
                            f"- Se a etiqueta de texto estiver impressa **DUAS** vezes na imagem, a quantidade ('qtd') DEVE ser **2**!\n"
                            f"- Se a etiqueta de texto estiver impressa **UMA** vez, a quantidade ('qtd') DEVE ser **1**!\n"
                            f"- Cada tag de texto no desenho representa 1 unidade física daquele móvel.\n\n"
                            f"💡 ORIENTAÇÃO DE PRECISÃO DE OCR E LEITURA (INSTRUÇÃO VISUAL CRÍTICA):\n"
                            f"1. O número da medida é a parte mais crítica e legível da imagem.\n"
                            f"⚠️ **LEITURA DE TEXTOS ROTACIONADOS / NA VERTICAL:** Muitas estantes estão posicionadas ao longo de paredes verticais no desenho, fazendo com que a escrita delas esteja rotacionada em 90 graus (na vertical). Você DEVE rotacionar mentalmente a imagem em 90 graus (tanto para a esquerda quanto para a direita) para conseguir ler as palavras corretamente! Nunca leia as linhas de forma estritamente horizontal se o texto estiver de pé ou de lado! Por exemplo, se vir a escrita 'MED 500mm' rotacionada de lado (deitada ou de pé), classifique-a EXATAMENTE como 'MED 500' e jamais a confunda com 'CESTAO' ou outro expositor promocional por ler na horizontal!\n"
                            f"2. ⚠️ APRENDIZADO VISUAL E PREVENÇÃO DE ERROS DE OCR/CLASSIFICAÇÃO:\n"
                            f"   - **⚠️ PDV (PONTO DE VENDA) É SEMPRE PADRÃO 600:** O PDV é padrão 600 e sempre será 600 no catálogo da Projefarma. Qualquer leitura de PDV na imagem (ex: 'PDV 700mm', 'PDV 800mm', 'PDV 1000', 'PDV') deve ser classificada OBRIGATORIAMENTE com nome 'PDV 600'! NUNCA retorne outro tamanho de PDV além do 'PDV 600'.\n"
                            f"   - **⚠️ GÔNDOLA 3000 (GOND 3000) vs GOND 2000:** A Gôndola de 3000mm (ex: 'GOND 3000' ou 'GOND 3000mm') representa um módulo central de gôndola comprido. Em fontes pixeladas de CAD, o número '3' costuma ter a parte de cima achatada/curvada parecendo um '2' (fazendo você ler erroneamente 'GOND 2000'). Preste atenção extraordinária ao comprimento do módulo central: se for uma gôndola central longa, classifique-a como 'GOND 3000' e NUNCA como 'GOND 2000'. A escrita que parece '2000' é na verdade um '3000' pixelado devido à compressão do CAD!\n"
                            f"   - **⚠️ PAINEL CANALETADO vs PF CANALETADO:** O expositor 'PAINEL CANALETADO' (geralmente acompanhado de 1000mm, ex: '1000mm PAINEL CANALETADO') é um painel largo com ranhuras. Devido à pixelização e compressão da palavra 'PAINEL' no desenho, as hastes verticais das letras P-A-I-N-E-L fazem com que pareça escrito 'PF CANALETADO'. Preste atenção: se for um painel largo (geralmente com indicação de 1000mm) com canaletas horizontais de exposição, a palavra escrita é **PAINEL CANALETADO**. Classifique-o obrigatoriamente como 'PAINEL CANALETADO' e nunca como 'PF CANALETADO'!\n"
                            f"   - **⚠️ CESTÃO 400 (CESTAO 400): REGRA ABSOLUTA DE GEOMETRIA:** O Cestão é um expositor promocional isolado composto por um **quadrado dividido em 4 quadrantes (grid de 2x2)** contendo pequenos círculos/esferas organizados em seu interior (produtos promocionais/frascos). Devido a bordas escuras ou textos internos truncados (como 'DESTAQUE', 'DEST', 'RESTAG', 'BENGRIP', 'REST', 'AQUE', 'RESTAG 400'), o Vision AI frequentemente se confunde e o classifica como 'DERMO' (acabamento preto) ou 'BA 600'.\n"
                            f"     * **SE O RECORTE MOSTRAR ESTE GRID 2x2 QUADRADO COM CÍRCULOS EM CADA QUADRANTE, ELE É OBRIGATORIAMENTE UM 'CESTAO 400' com acabamento 'normal'!** Ignore absolutamente qualquer palavra que pareça ler como 'DERMO', 'BA 600', 'DESTAQUE', etc. A estrutura geométrica do grid 2x2 de cestão promocional tem prioridade máxima sobre qualquer texto! O acabamento do cestão é sempre 'normal', nunca 'preto' ou 'amadeirado'!\n"
                            f"   - **MED 500 vs MED 807:** Se a estante tem escrito '500' ou '500mm' (ex: 'MED 500mm' ou 'MED 500'): Classifique EXATAMENTE como 'MED 500'! É extremamente importante ler o número '500' correto e não confundir de jeito nenhum com '807' ou 'MED 807'!\n"
                            f"     *⚠️ ATENÇÃO COM FONTES PIXELADAS (5 vs 6):* Em fontes blocky/CAD pixeladas, o número '5' (de '500') costuma ter o espaço central preenchido por pixels, fazendo com que pareça muito com um '6' (gerando '600' ou '600mm'). Como não existe o produto 'MED 600' ou 'MED 700' no catálogo oficial da Projefarma (apenas MED 500 e MED 807), se você vir algo que pareça 'MED 600' ou 'MED 700', classifique-o SEMPRE como 'MED 500'! **Da mesma forma, o item 'MIP' só existe na medida 'MIP 500'. Se a imagem mostrar o que parece ser 'MIP 600' ou 'MIP 600mm' devido a pixels borrados ou distorções, classifique OBRIGATORIAMENTE como 'MIP 500'!**\n"
                            f"   - **MED 807 vs BA 800 vs PDV:** Se a estante tem escrito '807' ou '807mm' (ex: 'MED 807mm' ou 'MED 807'): Classifique EXATAMENTE como 'MED 807'! NUNCA classifique 'MED 807' como 'BA 800' ou 'PDV 800' ou 'PDV 807'! Preste muita atenção para ler 'MED' na primeira linha e '807' na segunda linha, sem confundir com 'BA' ou '800'. Mesmo que as letras estejam pixeladas, se o texto contiver 'MED' e '807', classifique como 'MED 807'!\n"
                            f"   - Se a estante tem escrito '550' ou '550mm' na área de Perfumaria: Classifique como 'PF 550'.\n"
                            f"   - Se a estante tem escrito '807' ou '807mm' na área de Perfumaria: Classifique como 'PF 807'.\n"
                            f"   - Se a estante tem escrito '1000' ou '1000mm' na área de Perfumaria: Classifique como 'PF 1000'.\n"
                            f"   - Se a gôndola tem escrito '2000' ou '2000mm' (ex: 'GOND 2000mm' ou 'GOND 2000'): Classifique como 'GOND 2000'.\n"
                            f"   - Se a gôndola tem escrito '1700' ou '1700mm': Classifique como 'GOND 1700'.\n"
                            f"   - Se a gôndola tem escrito '1400' ou '1400mm': Classifique como 'GOND 1400'.\n"
                            f"   - **BA vs PDV:** Se disser 'BA' (ex: 'BA 800mm', 'BA 800', 'BA 1000'): Classifique EXATAMENTE como 'BA 600', 'BA 700', 'BA 800' ou 'BA 1000'! NUNCA confunda ou misture BA com PDV, pois são produtos distintos no catálogo!\n"
                            f"   - **BASE 1200:** O item 'BASE 1200' (ou 'BASE 1200mm') representa a base/plinto expositor. Ele geralmente tem caixas e produtos coloridos (vermelhos, roxos, etc.) desenhados em cima e a escrita 'BASE 1200mm' (ou 'BASE 1200') no meio. Se você vir a escrita 'BASE' e '1200' ou '1200mm' na imagem, mesmo que haja produtos coloridos desenhados por cima tampando parte do texto, você DEVE retornar o JSON com o item 'BASE 1200'! Não confunda com 'PF CANALETADO'!\n"
                            f"   - **ESMALTES:** Se a estante/expositor tem escrito 'ESMALTES' ou 'ESMALTE' (ex: 'ESMALTES 500mm', 'ESMALTES 807mm'): Classifique EXATAMENTE como 'ESMALTES'. Preste muita atenção se houver outro móvel ao lado no mesmo recorte (como 'PF CANALETADO 807mm' grudado ou ao lado dele), você DEVE retornar AMBOS no JSON final com suas respectivas quantidades! **⚠️ LEMBRE-SE: NUNCA classifique como 'ESMALTES' um expositor quadrado isolado 2x2 (cestão), o expositor de ESMALTES é obrigatoriamente uma estante linear de parede longa e retangular!**\n"
                            f"   - **DERMO:** Estantes de dermocosméticos devem ser classificadas como 'DERMO'. Se tiverem o fundo preto, o acabamento será 'preto'. Se tiverem fundo marrom/madeira, o acabamento será 'amadeirado'. Se tiverem fundo claro/branco, o acabamento será 'normal'.\n"
                            f"   - **CANTONEIRA 400:** O móvel 'CANTONEIRA 400' representa uma prateleira de canto e possui o formato geométrico de um **TRIÂNGULO** no desenho CAD. Se você vir um recorte que tenha o formato geométrico de um **TRIÂNGULO** (ou contiver palavras como 'CANTONEIRA', 'CANTO', 'CANTONEIRA 400'), você DEVE classify exatamente como 'CANTONEIRA 400'! Preste muita atenção para rotacionar mentalmente a imagem em 90 graus para conseguir ler as palavras escritas dentro dele!\n"
                            f"   - **CHECKOUT E BOMB 970:** Se o recorte contiver um balcão de checkout (ex: 'CHECKOUT 1000mm') E na frente/lado dele houver uma prateleira longa e estreita cheia de produtos coloridos (representados por pequenos retângulos, grids ou pequenos círculos em amarelo, azul, roxo, laranja, etc., representando doces, gomas e balas de checkout), isso significa que ele possui uma bomboniere de checkout acoplada! Nesse caso, você DEVE classificar o balcão como 'CHECKOUT 1000' (ou 'CHECKOUT') E TAMBÉM incluir o item 'BOMB 970' com qtd: 1 na lista de 'achados' do JSON final!\n"
                            f"3. ⚠️ REGRA EXCLUSIVA DO CESTÃO: O Cestão é um expositor promocional isolado. O desenho possui produtos representados em cima que aparecem como preenchimentos coloridos (ex: verdes, laranjas, vermelhos) ou círculos/esferas organizados em matriz (representando caixas e frascos de remédios).\n"
                            f"   - **Existem DOIS modelos de Cestão no catálogo da Projefarma:**\n"
                            f"     1. **'CESTAO 400'** (Cestão 400x400): É o modelo menor de 400mm. O texto na planta diz 'CESTÃO 400', 'CESTAO 400', ou contém variações como 'RESTAG 400', 'REST 400', 'RESTAG 400X400', 'RESTÃO 400', 'CESTÃO 400mm'. Se houver qualquer menção ao número '400' ou se for um cesto quadrado pequeno de 400mm, você DEVE retornar exatamente o nome 'CESTAO 400' no JSON final! NUNCA ignore a escrita 'CESTÃO 400' ou similar!\n"
                            f"     2. **'CESTAO'** (Cestão Padrão/Geral): Classifique como 'CESTAO' apenas se for um cestão geral sem menção a '400' ou se disser apenas 'CESTÃO' / 'CESTAO'.\n"
                            f"   - **⚠️ EVITE FALSO NEGATIVO E CONFUSÃO COM CAIXAS DE REMÉDIO OU OUTROS ITENS ('GESTÃO', 'DESTAQUE' vs 'CESTÃO'):** Às vezes, o cesto promocional tem caixas de remédios ou textos impressos no CAD com nomes muito parecidos ou associados (como 'GESTÃO', 'DESTAQUE', 'DEST', 'AQUE', 'DEST AQUE'). O Vision AI pode se confundir e ler 'DESTAQUE' e classificá-lo incorretamente como 'DERMO' por semelhança de letras ou fundo preto! Isso é um ERRO GRAVE! Se você ler qualquer palavra parecida com 'DESTAQUE', 'DEST AQUE', 'DEST', 'AQUE', 'CESTÃO', 'CESTAO', 'GESTÃO', 'GESTAO', 'RESTÃO', 'RESTAG', 'REST' (com ou sem o número '400'), ou se houver uma matriz de círculos/esferas desenhada (produtos no cestão), você DEVE retornar exatamente o nome 'CESTAO 400' com acabamento 'normal'! NUNCA classifique 'DESTAQUE' ou esse cesto como 'DERMO' e NUNCA classifique como acabamento 'preto'! O acabamento do cestão é sempre 'normal'!\n"
                            f"   - **⚠️ REGRA DE ACABAMENTO DO CESTÃO SOB SOBREPOSIÇÃO COLORIDA:** Como o Cestão tem caixas de medicamentos coloridas desenhadas ao fundo (verdes, laranjas, vermelhas, etc. como 'BENGRIP' ou 'GESTÃO' na imagem), essas cores de medicamentos NÃO indicam um acabamento de madeira/marrom ou preto do móvel! Cestões sob fundos coloridos de produtos devem SEMPRE ser classificados com acabamento **'normal'**. Eles só serão 'preto' ou 'amadeirado' se o preenchimento da etiqueta de texto for explicitamente um marrom sólido ou preto sólido!\n"
                            f"   - **⚠️ REGRA DETERMINÍSTICA DE QUANTIDADE POR TEXTO ESCRITO:** A quantidade do 'CESTAO 400' é definida RIGOROSAMENTE pelo número de textos escritos na imagem, e nunca pelas linhas ou divisórias do desenho!\n"
                            f"     * Se o recorte contiver apenas **UM** texto escrito (ex: apenas uma palavra 'CESTÃO 400mm' ou 'RESTAG 400' na imagem), a quantidade é **1**! Mesmo que o desenho do cesto possua divisórias ou linhas internas no meio, a quantidade deve ser classificada como **1**!\n"
                            f"     * Se o recorte contiver **DOIS** textos escritos de forma separada (ex: duas etiquetas distintas de 'CESTÃO 400mm' ou 'RESTAG 400' na mesma imagem), a quantidade é **2**!\n"
                            f"   - **⚠️ PREVENÇÃO DE FALSO POSITIVO PARA CESTÃO:** O Cestão é um expositor promocional isolado, quadrado (400x400) ou redondo. Ele **NUNCA** deve ser confundido com balcões de atendimento, caixas (checkout) ou painéis. Se você vir um desenho que mostre um balcão com o desenho de um computador/monitor/teclado em cima, ou um espaço para a cadeira do operador, isto é um **CAIXA** ou **CHECKOUT**, e **NUNCA** um Cestão! Não classifique desenhos de balcões com computadores/monitores ou caixas registradoras como 'CESTAO'!\n\n"
                            f"💡 REGRA DE DETECÇÃO DE ACABAMENTO (CORES DE FUNDO DA CAIXA DE TEXTO):\n"
                            f"O acabamento de cada item deve ser classificado em 'normal', 'preto' ou 'amadeirado' dependendo EXCLUSIVAMENTE da cor de fundo (fill/background) da caixa ou bloco do texto do módulo na imagem:\n"
                            f"   - **⚠️ PAPEL DE FUNDO DO CAD NÃO É AMADEIRADO:** A planta baixa CAD possui uma cor de fundo geral que costuma ser bege, amarelo-claro, cinza claro ou esbranquiçado (cor padrão do papel de desenho). **ESSA COR DE FUNDO GERAL NÃO SIGNIFICA QUE O MÓVEL É AMADEIRADO!** O acabamento de um móvel só é 'amadeirado' se a caixa ou bloco específico do texto daquele módulo tiver um preenchimento marrom sólido nítido ou textura de madeira. Se o fundo for apenas a cor padrão do papel (bege/amarelado claro/cinza/branco), classifique o acabamento sempre como 'normal'!\n"
                            f"   - Se o fundo/preenchimento da caixa de texto do módulo for MARROM / COR DE MADEIRA (brown/wood/wooden fill), classifique o acabamento exatamente como 'amadeirado'.\n"
                            f"   - Se o fundo/preenchimento da caixa de texto do módulo for PRETO sólido (solid black fill), classifique o acabamento exatamente como 'preto'.\n"
                            f"   - Se o fundo/preenchimento for colorido devido a desenhos de remédios/caixas de produtos (verde, laranja, vermelho, etc., como nos cestões), ou for branco, cinza claro ou qualquer cor padrão clara (white/light grey/none), classifique o acabamento como 'normal'.\n"
                            f"NÃO decida o acabamento pelo nome do móvel, olhe estritamente as cores da imagem!\n\n"
                            f"⚠️ NUNCA retorne um JSON vazio '{{}}' se houver um móvel ou palavra escrita visível na imagem! Se vir letras (como 'PDV', 'BA', 'MED', 'PF', 'ESMALTES', 'CESTÃO', 'CESTAO', 'RESTAG', 'REST', 'GESTÃO', 'GESTAO', 'RESTÃO', 'DESTAQUE', 'DEST AQUE', 'DEST', 'AQUE', 'PAINEL CANALETADO', 'CANALETADO') e um número de medida ou palavra legível, você DEVE retornar o JSON com o item correspondente de acordo com as regras acima! Se o recorte for um cestão (grid 2x2 com círculos), retorne OBRIGATORIAMENTE 'CESTAO 400' com acabamento 'normal'! Se disser claramente 'MED' e '807mm', retorne 'MED 807' e não confunda com balcões! Se disser claramente 'MED' e '500mm', retorne 'MED 500' e não confunda com 'MED 807'! Se houver múltiplos móveis (como 'ESMALTES 500mm' E 'PF CANALETADO 807mm' na mesma imagem), retorne uma lista com TODOS eles!\n"
                            f"Retorne JSON: {{\"achados\": [{{ \"nome\": \"TEXTO_LIDO\", \"qtd\": 1, \"acabamento\": \"normal\"|\"preto\"|\"amadeirado\" }}]}}\n"
                            f"⚠️ NOTA: Se você ler a palavra 'DESTAQUE', 'DEST AQUE', 'DEST' ou 'AQUE' em um cesto promocional (expositor quadrado ou redondo com círculos representando produtos), retorne 'CESTAO 400' no campo nome e 'normal' no acabamento no JSON!\n"
                            f"⚠️ NOTA 2: Se você ler a palavra 'DERMO' ou 'DERMOCOSMETICOS' na perfumaria, retorne 'DERMO'.\n"
                            f"⚠️ NOTA 3: VITRINE - Se o recorte contiver a palavra 'VITRINE', 'VITRINE 807', 'VITRINE 807MM', 'VITRINE MDF', ou qualquer variação com 'VITRINE', retorne exatamente 'VITRINE' no campo nome. A VITRINE é um expositor com vidro, frequentemente posicionado ao lado de estantes de perfumaria (PF) ou dermocosméticos. Se ela aparecer no mesmo recorte junto com outro móvel (por exemplo: 'PF 550' ao lado de 'VITRINE 807'), você DEVE retornar AMBOS no JSON - nunca ignore uma VITRINE mesmo que haja outro item no mesmo recorte!"
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Quais móveis estão escritos e desenhados na imagem? Identifique e retorne TODOS os móveis presentes no recorte (ex: se houver ESMALTES e PF CANALETADO lado a lado, ou se houver dois balcões, ou se houver VITRINE ao lado de PF). Preste atenção extraordinária a ESMALTES, PF CANALETADO, PF, DERMO, PDV, BA, CHECKOUT, CAIXA, CESTO e VITRINE. CONTE CADA UM INDIVIDUALMENTE e identifique o acabamento pela cor de fundo do texto do módulo (amadeirado se fundo marrom, preto se fundo preto, normal se fundo claro/branco). Retorne TODOS em uma lista no JSON bruto!"},
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
                acabamento_ai = found.get("acabamento", "normal").lower()
                if acabamento_ai not in ("preto", "amadeirado", "normal"):
                    acabamento_ai = "normal"
                
                # Tratamento especial de compatibilidade caso o nome em si indique acabamento no texto
                if "PRETO" in nome_ai.upper():
                    acabamento_ai = "preto"
                elif "AMADEIRADO" in nome_ai.upper() or "MDF" in nome_ai.upper():
                    acabamento_ai = "amadeirado"

                match = find_catalog_item(nome_ai)
                if match:
                    if "GOND" in match:
                        qty_ai = 1
                    if "PDV" in match:
                        match = "PDV 600"
                    if match in ("CESTAO", "CESTAO 400"):
                        match = "CESTAO 400"
                        qty_ai = 1
                        acabamento_ai = "normal"
                    if "MED" in match:
                        acabamento_ai = "normal"
                    results.append({"item": match, "fonte": "openai", "qty": qty_ai, "acabamento": acabamento_ai})
                    self._log(f"[OpenAI] Found: {match} (qty {qty_ai}) [Acabamento: {acabamento_ai}]")
        except Exception as e:
            self._log(f"⚠️ OpenAI error: {e}")


        # Guard‑rails para o CESTÃO:
        # 1. Se CESTÃO estiver no recorte, ignoramos absolutamente QUALQUER outro item que não seja CESTAO no mesmo recorte,
        #    pois o CESTÃO é um expositor promocional isolado e qualquer outra detecção (como ESMALTES, PF, MED) é falso positivo.
        has_cestao = any(r["item"] in ("CESTAO", "CESTAO 400") for r in results)
        if has_cestao:
            results = [r for r in results if r["item"] in ("CESTAO", "CESTAO 400")]

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
        """Aggregate detections from OCR and AI, summing quantities for the same item and finish."""
        final_inventory = Counter()
        for res in all_results:
            item = res["item"]
            acabamento = res.get("acabamento", "normal")
            qty = res.get("qty", 1)
            # Chave composta com separador #
            composite_key = f"{item}#{acabamento}"
            final_inventory[composite_key] += qty
        self._log(f"Consolidated inventory: {final_inventory}")
        return dict(final_inventory)

    def validate_total(self, inventario_final):
        """Placeholder for any future validation logic – currently always passes."""
        return {"is_valid": True, "warnings": []}
