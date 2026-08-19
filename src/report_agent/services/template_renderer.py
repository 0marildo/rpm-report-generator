"""Template-aware PDF renderer with explicit image injection and post-render preview."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import fitz

from .template_parser import (
    TEMPLATES_DIR,
    DEFAULT_TEMPLATE,
    TemplateDef,
    parse_template,
    PAGE_W,
    PAGE_H,
)
from ..layout import ImageSlot, compute_image_layout_constraints, ImageLayoutError

logger = logging.getLogger(__name__)

TEXT_DARK = (0.15, 0.15, 0.15)
BACKGROUND_KEEP_MIN_SIZE = 580.0


class TemplateRenderer:
    def __init__(self, template_path: str | None = None):
        self.template_path = template_path or str(TEMPLATES_DIR / DEFAULT_TEMPLATE)
        self.tpl: TemplateDef = parse_template(self.template_path)

    def render(
        self,
        output_path: str,
        fields: dict[str, str],
        image_sections: dict[str, list[dict]],
    ) -> str:
        doc = fitz.open(self.template_path)
        self._clear_template_placeholders(doc)
        self._fill_text_fields(doc, fields)
        self._place_images(doc, image_sections)
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        logger.info("Report saved to %s", output_path)
        return output_path

    def render_preview(
        self,
        fields: dict[str, str],
        image_sections: dict[str, list[dict]],
        preview_page: int = 0,
    ) -> str:
        preview_path = os.path.join(tempfile.gettempdir(), "report-agent", "preview.pdf")
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        out = self.render(preview_path, fields, image_sections)
        return out

    def _clear_template_placeholders(self, doc: fitz.Document) -> None:
        # Preserve background images separately so we can re-lock them.
        background_images: dict[int, list[dict]] = {}
        for cat, ph_list in self.tpl.image_placeholders.items():
            for ph in ph_list:
                if ph.page >= doc.page_count:
                    continue
                page = doc[ph.page]
                page.draw_rect(fitz.Rect(ph.insert_rect), color=(1, 1, 1), fill=(1, 1, 1), width=0)
                page.draw_rect(
                    fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom),
                    color=(1, 1, 1),
                    fill=(1, 1, 1),
                    width=0,
                )

        for pg_idx in range(doc.page_count):
            page = doc[pg_idx]
            bg_candidates = []
            for info in page.get_image_info():
                bbox = info.get("bbox")
                if not bbox:
                    continue
                x0, y0, x1, y1 = bbox
                w = x1 - x0
                h = y1 - y0
                if w > BACKGROUND_KEEP_MIN_SIZE and h > BACKGROUND_KEEP_MIN_SIZE:
                    xref = None
                    image_data = None
                    for img in page.get_images():
                        for img_info in page.get_image_info():
                            info_bbox = img_info.get("bbox")
                            if not info_bbox:
                                continue
                            if (
                                abs(info_bbox[0] - x0) < 1e-3
                                and abs(info_bbox[1] - y0) < 1e-3
                                and abs(info_bbox[2] - x1) < 1e-3
                                and abs(info_bbox[3] - y1) < 1e-3
                            ):
                                xref = img[0]
                                break
                        if xref is not None:
                            break
                    if xref is not None:
                        try:
                            image_data = page.extract_image(xref)
                        except Exception:
                            image_data = None
                    bg_candidates.append(
                        {
                            "bbox": fitz.Rect(x0, y0, x1, y1),
                            "xref": xref,
                            "image_data": image_data.get("image") if isinstance(image_data, dict) else None,
                        }
                    )
            if bg_candidates:
                background_images[pg_idx] = bg_candidates

        self._background_images = background_images

    def _apply_locked_backgrounds(self, doc: fitz.Document) -> None:
        """Re-insert template backgrounds as locked images."""
        for pg_idx, images in getattr(self, "_background_images", {}).items():
            if pg_idx >= doc.page_count:
                continue
            page = doc[pg_idx]
            for bg in images:
                try:
                    xref = page.add_redact_annot(bg["bbox"])
                    page.apply_redactions()
                    continue
                except Exception:
                    pass
                try:
                    page.draw_rect(bg["bbox"], color=(1, 1, 1), fill=(1, 1, 1), width=0)
                except Exception:
                    pass

    def _fill_text_fields(self, doc: fitz.Document, fields: dict[str, str]) -> None:
        resolved_fields = {}
        alias_map = {
            "company_name": "proprietario",
            "client_name": "proprietario",
            "cnpj": "cnpj",
            "address": "endereco",
            "classification": "classificacao",
            "floors": "num_pavimentos",
            "building_area": "area_total",
            "process_number": "processo",
            "report_number": "laudo_exigencias",
        }
        for k, v in fields.items():
            if v is not None and str(v).strip() != "":
                resolved_fields[k] = str(v).strip()
        for alias_k, template_k in alias_map.items():
            if alias_k in fields and fields[alias_k] is not None and str(fields[alias_k]).strip() != "":
                if template_k == "proprietario":
                    c_name = str(fields.get("company_name") or "").strip()
                    cl_name = str(fields.get("client_name") or "").strip()
                    if cl_name and c_name:
                        resolved_fields[template_k] = f"{cl_name} / {c_name}"
                    else:
                        resolved_fields[template_k] = cl_name or c_name
                else:
                    resolved_fields[template_k] = str(fields[alias_k]).strip()

        for field_name, value in resolved_fields.items():
            if not value or str(value).strip() == "":
                continue
            fd = self.tpl.text_fields.get(field_name)
            if fd is None or fd.page >= doc.page_count:
                continue
            page = doc[fd.page]
            full_text = str(value).strip()
            font_size = fd.font_size
            text_w = fitz.get_text_length(full_text, fontname="helv", fontsize=font_size)
            if text_w > fd.max_width:
                font_size = max(5, int(font_size * (fd.max_width / text_w)))
            center_y = (fd.value_top + fd.value_bottom) / 2
            page.insert_text(
                fitz.Point(fd.value_x, center_y),
                full_text,
                fontname="helv",
                fontsize=font_size,
                color=TEXT_DARK,
            )

    def _place_images(self, doc: fitz.Document, image_sections: dict[str, list[dict]]) -> None:
        placed_all: list[tuple[int, fitz.Rect, bytes, str]] = []

        POINTS_PER_PIXEL = 72.0 / 96.0
        AREA_WIDTH_PX = 794.0
        AREA_HEIGHT_PX = 1123.0
        MARGIN_PX = (50.0, 50.0, 50.0, 50.0)
        GAP_PX = 20.0
        MIN_IMAGE_WIDTH_PX = 200.0
        MIN_IMAGE_HEIGHT_PX = 160.0

        for cat, ph_list in self.tpl.image_placeholders.items():
            images = image_sections.get(cat, [])
            if not images:
                continue
            ph = next((p for p in ph_list if p.area_bottom - p.area_top >= 80), None)
            if ph is None and ph_list:
                ph = ph_list[0]
            if ph is None:
                continue
            area = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
            try:
                cols, rows, cell_size_px = compute_image_layout_constraints(
                    AREA_WIDTH_PX,
                    AREA_HEIGHT_PX,
                    min(len(images), 9),
                    margin_px=MARGIN_PX,
                    gap_px=GAP_PX,
                    min_image_width_px=MIN_IMAGE_WIDTH_PX,
                    min_image_height_px=MIN_IMAGE_HEIGHT_PX,
                )
            except ImageLayoutError as exc:
                logger.error("Falha ao calcular posicionamento de imagens: %s", exc)
                raise

            cell_size = cell_size_px * POINTS_PER_PIXEL
            min_gap_pt = GAP_PX * POINTS_PER_PIXEL
            total_w = cols * cell_size + (cols - 1) * min_gap_pt
            total_h = rows * cell_size + (rows - 1) * min_gap_pt
            offset_x = area.x0 + (area.width - total_w) / 2
            offset_y = area.y0 + (area.height - total_h) / 2

            for idx, image in enumerate(images[: cols * rows]):
                data = image.get("data") or image.get("path")
                if isinstance(data, str) and os.path.exists(data):
                    data = Path(data).read_bytes()
                if not data:
                    continue
                col = idx % cols
                row = idx // cols
                x = offset_x + col * (cell_size + min_gap_pt)
                y = offset_y + row * (cell_size + min_gap_pt)
                placed_all.append(
                    (
                        ph.page,
                        fitz.Rect(x, y, x + cell_size, y + cell_size),
                        data,
                        image.get("filename") or "image.jpg",
                    )
                )

        for cat, images in image_sections.items():
            if cat in self.tpl.image_placeholders:
                continue
            if not images:
                continue
            ph_list = self.tpl.image_placeholders.get(cat, [])
            ph = next((p for p in ph_list), None)
            page_index = ph.page if ph else 0
            if ph:
                area = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
            else:
                area = fitz.Rect(35, 55, 560, 787)

            try:
                cols, rows, cell_size_px = compute_image_layout_constraints(
                    AREA_WIDTH_PX,
                    AREA_HEIGHT_PX,
                    min(len(images), 9),
                    margin_px=MARGIN_PX,
                    gap_px=GAP_PX,
                    min_image_width_px=MIN_IMAGE_WIDTH_PX,
                    min_image_height_px=MIN_IMAGE_HEIGHT_PX,
                )
            except ImageLayoutError as exc:
                logger.error("Falha ao calcular posicionamento de imagens: %s", exc)
                raise

            cell_size = cell_size_px * POINTS_PER_PIXEL
            min_gap_pt = GAP_PX * POINTS_PER_PIXEL
            total_w = cols * cell_size + (cols - 1) * min_gap_pt
            total_h = rows * cell_size + (rows - 1) * min_gap_pt
            offset_x = area.x0 + (area.width - total_w) / 2
            offset_y = area.y0 + (area.height - total_h) / 2

            for idx, image in enumerate(images[: cols * rows]):
                data = image.get("data") or image.get("path")
                if isinstance(data, str) and os.path.exists(data):
                    data = Path(data).read_bytes()
                if not data:
                    continue
                col = idx % cols
                row = idx // cols
                x = offset_x + col * (cell_size + min_gap_pt)
                y = offset_y + row * (cell_size + min_gap_pt)
                placed_all.append(
                    (
                        page_index,
                        fitz.Rect(x, y, x + cell_size, y + cell_size),
                        data,
                        image.get("filename") or "image.jpg",
                    )
                )

        for page_index, rect, data, filename in placed_all:
            if page_index >= doc.page_count:
                continue
            page = doc[page_index]
            try:
                xref = page.insert_image(rect, stream=data, keep_proportion=True)
                self._lock_image_xref(page, xref, rect)
            except Exception:
                page.insert_image(rect, filename="", stream=data, keep_proportion=True)
            page.draw_rect(rect, color=(0.65, 0.65, 0.65), width=0.5)

    @staticmethod
    def _lock_image_xref(page: fitz.Page, xref: int, rect: fitz.Rect) -> None:
        """Place an invisible locked annotation on top of the inserted image."""
        try:
            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=None, fill=None)
            annot.set_opacity(0)
            annot.set_flags(128 | 512)
            annot.update()
        except Exception as exc:
            logger.warning("Could not lock inserted image xref=%s: %s", xref, exc)
