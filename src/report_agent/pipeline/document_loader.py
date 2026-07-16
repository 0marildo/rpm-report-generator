"""Document loading and validation."""

import logging
import os
import tempfile

import fitz

logger = logging.getLogger(__name__)


class DocumentLoader:
    def load(self, file_data: bytes, filename: str) -> str:
        if not file_data or len(file_data) < 100:
            raise ValueError(f"File too small or empty: {filename}")

        suffix = os.path.splitext(filename)[1].lower()
        if suffix != ".pdf":
            raise ValueError(f"Unsupported file type: {suffix}")

        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", prefix="doc_"
        )
        tmp.write(file_data)
        tmp.close()

        try:
            doc = fitz.open(tmp.name)
            page_count = doc.page_count
            doc.close()
            if page_count == 0:
                os.unlink(tmp.name)
                raise ValueError(f"PDF has no pages: {filename}")
        except Exception as e:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Cannot open PDF: {filename} ({e})")

        logger.info("Loaded %s (%d pages, %.1f KB)", filename, page_count, len(file_data) / 1024)
        return tmp.name

    def unload(self, pdf_path: str) -> None:
        try:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
        except OSError:
            logger.warning("Failed to remove temp file: %s", pdf_path)
