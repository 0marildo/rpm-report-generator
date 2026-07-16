"""Document classification: scanned vs digital PDFs."""

import logging
import fitz

logger = logging.getLogger(__name__)

SCANNED_TEXT_THRESHOLD = 50
SCANNED_CHAR_THRESHOLD = 100


class DocumentClassifier:
    def classify(self, pdf_path: str) -> dict:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count

        total_text = ""
        pages_with_text = 0
        pages_with_images = 0

        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text().strip()
            total_text += text
            if len(text) > 20:
                pages_with_text += 1
            if len(page.get_images(full=True)) > 0:
                pages_with_images += 1

        doc.close()

        text_length = len(total_text)
        has_meaningful_text = (
            text_length > SCANNED_TEXT_THRESHOLD
            and pages_with_text >= max(1, page_count // 3)
        )

        is_scanned = not has_meaningful_text and pages_with_images > 0

        result = {
            "page_count": page_count,
            "total_text_length": text_length,
            "pages_with_text": pages_with_text,
            "pages_with_images": pages_with_images,
            "is_scanned": is_scanned,
            "has_meaningful_text": has_meaningful_text,
            "classification": "scanned" if is_scanned else "digital",
        }

        logger.info(
            "Classified %s: %s (text=%d chars, img_pages=%d/%d)",
            pdf_path, result["classification"],
            text_length, pages_with_images, page_count,
        )
        return result

    def classify_batch(self, pdf_paths: list[str]) -> list[dict]:
        return [self.classify(p) for p in pdf_paths]
