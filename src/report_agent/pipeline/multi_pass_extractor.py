"""Template-driven Page-chunked Extractor using Gemini."""

import json
import logging
import os
import re
from typing import Optional

import fitz
from PIL import Image
import io

logger = logging.getLogger(__name__)

PAGE_IMAGE_DPI = int(os.getenv("PAGE_IMAGE_DPI", "200"))
CHUNK_PAGES = int(os.getenv("CHUNK_PAGES", "4"))
MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1024"))

SCHEMA_FIELDS = {
    "company_name": "Razão social da empresa responsável pela edificação.",
    "client_name": "Nome do proprietário ou responsável técnico do imóvel.",
    "cnpj": "CNPJ da empresa ou CPF do proprietário.",
    "address": "Endereço completo da edificação (logradouro, número, bairro, cidade, UF).",
    "process_number": "Número do processo no CBMERJ (ex: E-27/...).",
    "report_number": "Número do Laudo de Exigências (ex: LE-XXXXX/XX).",
    "classification": "Classificação da edificação (ex: A-1, F-3, E-1).",
    "building_area": "Área total construída em m².",
    "floors": "Número de pavimentos da edificação.",
    "engineer": "Nome do engenheiro que assina o laudo.",
    "crea": "Número de registro no CREA do engenheiro.",
    "approved_systems": "Sistemas de segurança contra incêndio e pânico aprovados.",
    "specific_risks": "Riscos específicos listados no laudo (ex: gerador, gás canalizado, subestação elétrica).",
    "observations": "Observações gerais do laudo.",
    "fabricante": "Fabricante da bomba de incêndio principal/jockey.",
    "serie": "Número de série da bomba de incêndio.",
    "modelo": "Modelo da bomba de incêndio.",
    "vazao_nominal": "Vazão nominal da bomba (ex: m³/h, L/min, gpm).",
    "pressao_nominal": "Pressão nominal da bomba (ex: mca, bar, psi).",
    "rpm": "RPM de regime da bomba.",
    "diametro_rotor": "Diâmetro do rotor da bomba (ex: mm ou polegadas).",
    "potencia_cv": "Potência do motor da bomba em CV ou HP.",
}


def _downscale_image(data: bytes, mime_type: str = "image/png") -> bytes:
    try:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        fmt_map = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
        if width <= MAX_IMAGE_SIDE and height <= MAX_IMAGE_SIDE:
            return data
        ratio = min(MAX_IMAGE_SIDE / width, MAX_IMAGE_SIDE / height)
        new_size = (int(width * ratio), int(height * ratio))
        resized = image.resize(new_size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        resized.save(out, format=fmt_map.get(mime_type.lower().split(";")[0], "PNG"))
        return out.getvalue()
    except Exception:
        return data


def _pdf_page_chunks(
    pdf_path: str,
    *,
    dpi: int = PAGE_IMAGE_DPI,
    chunk_pages: int = CHUNK_PAGES,
):
    doc = fitz.open(pdf_path)
    total = len(doc)
    for start in range(0, total, chunk_pages):
        end = min(start + chunk_pages, total)
        chunks = []
        for page_index in range(start, end):
            page = doc[page_index]
            pix = page.get_pixmap(dpi=dpi)
            data = _downscale_image(pix.tobytes("png"), "image/png")
            chunks.append((page_index + 1, data, "image/png"))
        yield start + 1, end, chunks
    doc.close()


class MultiPassExtractor:
    def __init__(self, gemini=None):
        self.gemini = gemini

    def _get_gemini(self):
        if self.gemini is None:
            from ..core.gemini_client import GeminiClient
            self.gemini = GeminiClient()
        return self.gemini

    def extract(self, pdf_path: str, raw_text: Optional[str] = None) -> dict[str, str]:
        gemini = self._get_gemini()
        logger.info("Iniciando extração chunked por páginas de %s", pdf_path)

        fields: dict[str, str] = {}

        for page_start, page_end, pages in _pdf_page_chunks(pdf_path):
            logger.info("Processando páginas %d-%d", page_start, page_end)

            schema_desc = json.dumps(
                {k: v for k, v in SCHEMA_FIELDS.items()}, indent=2, ensure_ascii=False
            )
            prompt = (
                f"Você receberá imagens de {page_start} a {page_end} páginas do documento.\n"
                f"Extraia os seguintes campos e retorne SOMENTE JSON válido.\n"
                f"Campos:\n{schema_desc}\n"
                f"Regras:\n"
                f"- Use string vazia se não encontrado.\n"
                f"- Não invente dados.\n"
                f"- Não retorne texto fora do JSON.\n"
            )

            content = [{"type": "text", "text": prompt}]
            for page_num, image_data, mime_type in pages:
                b64 = __import__("base64").b64encode(image_data).decode("utf-8")
                content.append({"type": "text", "text": f"[Pagina {page_num}]"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    }
                )

            messages = [
                {
                    "role": "user",
                    "content": content,
                }
            ]

            try:
                response = gemini.llm.invoke(messages)
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning("Falha no chunk %d-%d: %s", page_start, page_end, exc)
                continue

            parsed = self._parse_json(raw)
            for key in SCHEMA_FIELDS:
                val = parsed.get(key, "")
                if val is None:
                    val = ""
                val = str(val).strip()
                if val and key not in fields:
                    fields[key] = val
                    logger.info("Chunk %d-%d extraiu: %s = %s", page_start, page_end, key, val)

        fields["_report_hash"] = self._make_hash(pdf_path, fields)
        return fields

    @staticmethod
    def _make_hash(pdf_path: str, fields: dict[str, str]) -> str:
        import hashlib
        with open(pdf_path, "rb") as f:
            base = f.read()
        data = base + json.dumps(fields, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]

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
        logger.warning("Falha ao parsear JSON do Gemini: %.200s", text)
        return {}
