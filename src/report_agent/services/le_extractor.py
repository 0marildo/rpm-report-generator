"""LE (Laudo de Exigências) extraction using Gemini Vision."""

import json
import logging
import re

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Você é um especialista em segurança contra incêndio e pânico do CBMERJ.
Extraia dados estruturados do documento fornecido (Laudo de Exigências ou documento oficial).

Retorne APENAS um JSON válido com os campos abaixo. Use null para campos não encontrados.

Campos a extrair:
- proprietario: Razão social ou nome do proprietário da edificação
- cnpj: CNPJ no formato XX.XXX.XXX/XXXX-XX (ou CPF)
- endereco: Endereço completo (logradouro, número, bairro, cidade, UF)
- classificacao: Classificação da edificação conforme COSCIP (ex: "E-1 - ESCOLAR EM GERAL"). Incluir complemento e finalidade quando disponíveis.
- num_pavimentos: Número de pavimentos (apenas dígitos)
- area_total: Área total construída em m² (ex: "12963,20 m²")
- processo: Número do processo (ex: E27/27266/11220/2026)
- laudo_exigencias: Número do LE (ex: LE-04698/26)
- fabricante: Nome do fabricante das bombas (se disponível)
- serie: Número de série das bombas (se disponível)
- modelo: Modelo das bombas (se disponível)
- vazao_nominal: Vazão nominal das bombas (se disponível)
- pressao_nominal: Pressão nominal das bombas (se disponível)
- rpm: Rotações por minuto das bombas (se disponível)
- diametro_rotor: Diâmetro do rotor (se disponível)
- potencia_cv: Potência em CV (se disponível)

Retorne APENAS o JSON, sem texto adicional."""


def _get_gemini_client():
    from ..core.gemini_client import GeminiClient
    return GeminiClient()


class LEExtractor:
    def __init__(self, gemini=None):
        self.gemini = gemini

    def extract(self, pdf_path: str) -> dict[str, str]:
        logger.info("Extracting LE data from %s", pdf_path)
        if self.gemini is None:
            self.gemini = _get_gemini_client()
        try:
            raw = self.gemini.generate_with_pdf(
                prompt=EXTRACTION_PROMPT,
                pdf_path=pdf_path,
                system_instruction="Analista preciso de documentos. Extraia campos visualmente. Retorne APENAS JSON válido.",
            )
            fields = self._parse_json(raw)
            cleaned = {k: str(v).strip() for k, v in fields.items()
                       if v is not None and str(v).strip() and str(v).strip() not in ("", "null", "None")}
            logger.info("Extracted %d fields from %s", len(cleaned), pdf_path)
            return cleaned
        except Exception as e:
            logger.error("LE extraction failed: %s", e)
            return {}

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
        logger.warning("Failed to parse Gemini response as JSON: %.200s", text)
        return {}
