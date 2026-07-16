"""Extraction orchestrator: routes documents through the pipeline."""

import logging
from typing import Optional

from .document_loader import DocumentLoader
from .document_classifier import DocumentClassifier
from .text_extractor import TextExtractor
from .vision_extractor import VisionExtractor
from .schema_validator import SchemaValidator
from .multi_pass_extractor import MultiPassExtractor

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 3
MIN_FIELDS_FOR_CONFIDENCE = 3


class ExtractionOrchestrator:
    def __init__(self, gemini=None):
        self.loader = DocumentLoader()
        self.classifier = DocumentClassifier()
        self.text_extractor = TextExtractor()
        self.vision_extractor = VisionExtractor(gemini=gemini)
        self.multi_pass = MultiPassExtractor(gemini=gemini)
        self.validator = SchemaValidator()

    def extract_document(
        self,
        file_data: bytes,
        filename: str,
    ) -> dict:
        pdf_path = None
        try:
            pdf_path = self.loader.load(file_data, filename)

            # Classify document (checks if scanned vs digital)
            classification = self.classifier.classify(pdf_path)

            # Try text extraction first
            text_result = self.text_extractor.extract(pdf_path)
            extracted_text = text_result.get("text", "")
            text_length = len(extracted_text.strip())

            # Decide mode: if scanned or minimal text, force visual multimodal parsing
            is_scanned = classification["is_scanned"] or text_length < 100

            logger.info(
                "Running Multi-pass Extraction for %s (scanned=%s, text_length=%d)",
                filename, is_scanned, text_length
            )

            # Run 4-pass extraction using Gemini
            raw_fields = self.multi_pass.extract(
                pdf_path,
                raw_text=None if is_scanned else extracted_text
            )

            # Validate and normalize keys/values
            validated = self.validator.validate(raw_fields)
            normalized = self.validator.normalize_fields(validated["fields"])

            confidence = self._check_confidence(normalized, text_length)

            return {
                "success": True,
                "fields": normalized,
                "extraction_method": "multi_pass_vision" if is_scanned else "multi_pass_text",
                "confidence": confidence,
                "classification": classification,
                "source_document": filename,
                "conflicts": [],
            }

        except Exception as e:
            logger.error("Extraction pipeline failed for %s: %s", filename, e, exc_info=True)
            return {
                "success": False,
                "fields": {},
                "extraction_method": "failed",
                "error": str(e),
                "source_document": filename,
            }
        finally:
            if pdf_path:
                self.loader.unload(pdf_path)

    def _check_confidence(self, fields: dict, text_length: int) -> dict:
        non_empty = sum(1 for v in fields.values() if v and str(v).strip())
        key_fields = [
            "proprietario", "client_name", "cnpj", "endereco", "address",
            "classificacao", "classification", "processo", "process_number",
        ]
        key_found = sum(1 for k in key_fields if k in fields and fields[k])

        if non_empty >= 8 and key_found >= 3:
            level = "high"
        elif non_empty >= MIN_FIELDS_FOR_CONFIDENCE and key_found >= 1:
            level = "medium"
        elif non_empty >= 1:
            level = "low"
        else:
            level = "none"

        return {
            "level": level,
            "field_count": non_empty,
            "key_field_count": key_found,
            "text_length": text_length,
            "score": min(100, non_empty * 10 + key_found * 15),
        }

    def _merge_fields(self, primary: dict, secondary: dict) -> dict:
        merged = dict(secondary)
        for key, value in primary.items():
            if value and str(value).strip():
                merged[key] = value
        return merged
