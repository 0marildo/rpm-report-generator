"""Report preview rendering using PyMuPDF.

This module renders generated report PDFs to PNG preview images so the user
can approve or reject the report before downloading the final file.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import fitz

from .template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

PREVIEW_DIR = Path(tempfile.gettempdir()) / "report-agent" / "previews"
PREVIEW_DPI = 150


class PreviewRenderer:
    def __init__(self, template_name: str | None = None):
        self.template_renderer = TemplateRenderer(template_name)

    def render_preview_pages(
        self,
        fields: dict[str, str],
        image_sections: dict[str, list[dict]],
        max_pages: int | None = None,
    ) -> list[str]:
        """Render preview pages as PNG files and return their paths."""
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = self.template_renderer.render_preview(fields, image_sections)
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        if max_pages:
            page_count = min(page_count, max_pages)
        preview_paths = []
        for i in range(page_count):
            page = doc[i]
            pix = page.get_pixmap(dpi=PREVIEW_DPI)
            out_path = str(PREVIEW_DIR / f"preview_{i}.png")
            pix.save(out_path)
            preview_paths.append(out_path)
        doc.close()
        return preview_paths

    def get_final_report_path(
        self,
        fields: dict[str, str],
        image_sections: dict[str, list[dict]],
    ) -> str:
        preview_path = self.template_renderer.render_preview(fields, image_sections)
        out_path = os.path.join(tempfile.gettempdir(), "report-agent", "technical_report.pdf")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if preview_path != out_path:
            os.replace(preview_path, out_path)
        return out_path


__all__ = ["PreviewRenderer", "PREVIEW_DIR", "PREVIEW_DPI"]
