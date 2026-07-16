"""Vision-based extraction using Gemini for scanned documents."""

import json
import logging
import re

logger = logging.getLogger(__name__)

VISION_PROMPT = """Você é um especialista em segurança contra incêndio e pânico do CBMERJ.
Extraia dados estruturados do documento fornecido (Laudo de Exigências ou documento oficial).

Retorne APENAS um JSON válido com os campos abaixo. Use null para campos não encontrados.

Campos a extrair:
- company_name: Razão social da empresa responsável
- client_name: Nome do proprietário ou responsável pela edificação
- cnpj: CNPJ no formato XX.XXX.XXX/XXXX-XX (ou CPF)
- address: Endereço completo (logradouro, número, bairro, cidade, UF)
- process_number: Número do processo (ex: E27/27266/11220/2026)
- report_number: Número do laudo/relatório (ex: LE-04698/26)
- classification: Classificação da edificação conforme COSCIP
- building_area: Área total construída em m²
- floors: Número de pavimentos
- engineer: Nome do engenheiro responsável
- crea: CREA do engenheiro
- approved_systems: Sistemas aprovados (extintores, sprinklers, alarmes, etc.)
- specific_risks: Riscos específicos identificados
- observations: Observações gerais
- proprietario: Razão social ou nome do proprietário
- num_pavimentos: Número de pavimentos
- area_total: Área total construída em m²
- processo: Número do processo
- laudo_exigencias: Número do LE
- fabricante: Nome do fabricante das bombas
- serie: Número de série das bombas
- modelo: Modelo das bombas
- vazao_nominal: Vazão nominal das bombas
- pressao_nominal: Pressão nominal das bombas
- rpm: Rotações por minuto das bombas
- diametro_rotor: Diâmetro do rotor
- potencia_cv: Potência em CV

Retorne APENAS o JSON, sem texto adicional."""


class VisionExtractor:
    def __init__(self, gemini=None):
        self.gemini = gemini

    def _get_gemini(self):
        if self.gemini is None:
            from ..core.gemini_client import GeminiClient
            self.gemini = GeminiClient()
        return self.gemini

    def extract(self, pdf_path: str) -> dict:
        logger.info("Vision extraction from %s", pdf_path)
        gemini = self._get_gemini()

        raw = gemini.generate_with_pdf(
            prompt=VISION_PROMPT,
            pdf_path=pdf_path,
            system_instruction="Analista preciso de documentos. Extraia campos visualmente. Retorne APENAS JSON válido.",
        )

        fields = self._parse_json(raw)

        cleaned = {
            k: str(v).strip()
            for k, v in fields.items()
            if v is not None and str(v).strip() and str(v).strip() not in ("", "null", "None")
        }

        logger.info("Vision extracted %d fields from %s", len(cleaned), pdf_path)
        return cleaned

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
        logger.warning("Failed to parse vision response as JSON: %.200s", text)
        return {}
