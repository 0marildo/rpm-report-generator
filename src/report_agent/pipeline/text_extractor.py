"""Local text extraction using PyMuPDF and pdfplumber."""

import logging

import fitz

logger = logging.getLogger(__name__)


class TextExtractor:
    def extract(self, pdf_path: str) -> dict:
        try:
            return self._extract_with_pymupdf(pdf_path)
        except Exception as e:
            logger.error("Text extraction failed: %s", e)
            return {}

    def _extract_with_pymupdf(self, pdf_path: str) -> dict:
        doc = fitz.open(pdf_path)
        all_text = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                all_text.append(text.strip())

        doc.close()

        combined = "\n".join(all_text)

        fields = self._parse_fields(combined)

        result = {
            "raw_text": combined[:5000],
            "fields": fields,
            "text_length": len(combined),
        }

        logger.info(
            "Extracted %d chars, %d fields from %s",
            len(combined), len(fields), pdf_path,
        )
        return result

    def _parse_fields(self, text: str) -> dict[str, str]:
        fields = {}
        lines = text.split("\n")

        field_patterns = [
            ("proprietario", ["proprietário", "proprietario", "razão social", "razao social"]),
            ("cnpj", ["cnpj", "cpf"]),
            ("endereco", ["endereço", "endereco"]),
            ("classificacao", ["classificação", "classificacao"]),
            ("num_pavimentos", ["número de pavimentos", "num pavimentos", "pavimentos"]),
            ("area_total", ["área total", "area total"]),
            ("processo", ["processo"]),
            ("laudo_exigencias", ["laudo de exigências", "laudo de exigencias", "nº do le"]),
            ("fabricante", ["fabricante", "nome do fabricante"]),
            ("serie", ["série", "serie", "número de série"]),
            ("modelo", ["modelo"]),
            ("vazao_nominal", ["vazão nominal", "vazao nominal"]),
            ("pressao_nominal", ["pressão nominal", "pressao nominal"]),
            ("rpm", ["rotações por minuto", "rpm"]),
            ("diametro_rotor", ["diâmetro do rotor", "diametro do rotor"]),
            ("potencia_cv", ["potência", "potencia", "cv"]),
        ]

        for field_name, keywords in field_patterns:
            for line in lines:
                line_lower = line.lower().strip()
                for keyword in keywords:
                    if keyword in line_lower:
                        value = line.split(":", 1)[-1].strip() if ":" in line else ""
                        if not value:
                            parts = line_lower.split(keyword)
                            if len(parts) > 1:
                                value = parts[1].strip(" :")
                        if value and len(value) > 1:
                            fields[field_name] = value
                            break
                if field_name in fields:
                    break

        return fields
