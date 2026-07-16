"""Report generation orchestrator.

Connects template layout engine with low-level PDF renderer.
"""

import logging
import os
import tempfile

from .template_parser import TEMPLATES_DIR, DEFAULT_TEMPLATE
from .layout_engine import LayoutEngine
from .pdf_renderer import PDFRenderer

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, template_name: str = DEFAULT_TEMPLATE):
        self.template_path = str(TEMPLATES_DIR / template_name)
        self.layout_engine = LayoutEngine(self.template_path)
        self.pdf_renderer = PDFRenderer()

    def generate(
        self,
        output_path: str,
        fields: dict[str, str],
        image_sections: dict[str, list[tuple[str, bytes]]],
    ) -> dict:
        os.makedirs(os.path.dirname(output_path) or "/tmp/report-agent", exist_ok=True)

        # Standardize images list input format for the LayoutEngine
        renderer_input: dict[str, list[dict]] = {}
        total_images = 0
        for section, images in image_sections.items():
            renderer_input[section] = [
                {"data": img_bytes, "filename": fname}
                for fname, img_bytes in images
            ]
            total_images += len(images)

        logger.info(
            "Generating deterministic report: %d fields, %d images in %d sections",
            len(fields), total_images, len(renderer_input),
        )

        # Open the PDF template base
        doc = self.pdf_renderer.open_document(self.template_path)

        # Run layout engine sequential placement
        self.layout_engine.layout_document(doc, fields, renderer_input)

        # Compile and compress final output
        result_path = self.pdf_renderer.save_document(doc, output_path)
        
        num_pages = doc.page_count
        doc.close()

        return {
            "output_path": result_path,
            "num_pages": num_pages,
            "num_images": total_images,
            "fields_filled": len(fields),
        }
