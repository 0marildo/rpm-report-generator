"""Cursor-based deterministic report layout.

The template supplies section anchors, never image bounding boxes.  Content is
measured first, then paginated, then rendered from the resulting plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

import pymupdf

from .image_layout_engine import GridLayout, ImageLayoutEngine
from .page_renderer import PageRenderer
from .table_renderer import TableRenderer
from .template_parser import ImagePlaceholderDef, TemplateDef, parse_template
from .text_renderer import TextRenderer

logger = logging.getLogger(__name__)

PAGE_W = 595.0
PAGE_H = 842.0
MARGIN_L = 35.0
MARGIN_R = 35.0
MARGIN_T = 55.0
MARGIN_B = 55.0
SECTION_GAP = 8.0
CONTINUATION_TEMPLATE_PAGE = 10
CONTINUATION_CURSOR_Y = MARGIN_T + 26.0


@dataclass(frozen=True)
class SectionAnchor:
    category: str
    page: int
    cursor_y: float
    flow_bottom: float | None


class SectionAnalyzer:
    """Converts template placeholders into flow anchors and safe page bounds."""

    def __init__(self, template: TemplateDef):
        self.template = template

    def anchors(self) -> list[SectionAnchor]:
        raw: list[ImagePlaceholderDef] = [
            placeholder
            for placeholders in self.tpl.image_placeholders.values()
            for placeholder in placeholders
        ]
        # Multiple template markers for one category still represent one section.
        first_by_category: dict[str, ImagePlaceholderDef] = {}
        for placeholder in sorted(raw, key=lambda p: (p.page, p.insert_rect[1])):
            first_by_category.setdefault(placeholder.category, placeholder)
        ordered = sorted(first_by_category.values(), key=lambda p: (p.page, p.insert_rect[1]))
        result: list[SectionAnchor] = []
        for index, placeholder in enumerate(ordered):
            next_anchor_y = None
            if index + 1 < len(ordered) and ordered[index + 1].page == placeholder.page:
                next_anchor_y = ordered[index + 1].insert_rect[1] - SECTION_GAP
            # ``area_bottom`` is calculated by the parser from the next text
            # block on the page. It is a collision boundary, not an image
            # placeholder size: the grid solver still receives the entire
            # remaining flow region and paginates rather than shrinking.
            flow_bottom = placeholder.area_bottom
            if next_anchor_y is not None:
                flow_bottom = min(flow_bottom, next_anchor_y)
            # Only the insertion text baseline is used.  area_* dimensions are
            # intentionally ignored by the flow engine.
            result.append(SectionAnchor(placeholder.category, placeholder.page, placeholder.insert_rect[1], flow_bottom))
        return result


class LayoutEngine:
    """Coordinates template cleaning, flow layout, pagination and rendering."""

    def __init__(self, template_path: str):
        self.template_path = template_path
        self.image_layout_engine = ImageLayoutEngine()
        self.text_renderer = TextRenderer()
        self.table_renderer = TableRenderer()
        self.page_renderer = PageRenderer()
        self.tpl = parse_template(template_path)

    def layout_document(self, doc: pymupdf.Document, fields: dict[str, str], image_sections: dict[str, list[dict]]) -> None:
        self._fill_form_fields(doc, fields)
        self._clear_placeholders(doc)
        self._layout_photos(doc, image_sections)

    def _fill_form_fields(self, doc: pymupdf.Document, fields: dict[str, str]) -> None:
        aliases = {"company_name": "proprietario", "client_name": "proprietario", "address": "endereco", "classification": "classificacao", "floors": "num_pavimentos", "building_area": "area_total", "process_number": "processo", "report_number": "laudo_exigencias"}
        resolved = {key: str(value).strip() for key, value in fields.items() if value is not None and str(value).strip()}
        for source, target in aliases.items():
            if source in resolved:
                if target == "proprietario":
                    names = [resolved[key] for key in ("client_name", "company_name") if key in resolved]
                    resolved[target] = " / ".join(names)
                else:
                    resolved[target] = resolved[source]
        for name, value in resolved.items():
            field = self.tpl.text_fields.get(name)
            if field and field.page < doc.page_count:
                self.table_renderer.fill_table_cells(doc[field.page], {name: value}, self.tpl.text_fields)

    def _clear_placeholders(self, doc: pymupdf.Document) -> None:
        for placeholders in self.tpl.image_placeholders.values():
            for placeholder in placeholders:
                if placeholder.page >= doc.page_count:
                    continue
                page = doc[placeholder.page]
                # The v2 template has no embedded sample images.  Clear the
                # instruction itself, leaving all other template text and
                # artwork intact. Placeholder dimensions are never passed to
                # the layout solver.
                page.draw_rect(pymupdf.Rect(placeholder.insert_rect), color=(1, 1, 1), fill=(1, 1, 1), width=0)

    def _layout_photos(self, doc: pymupdf.Document, image_sections: dict[str, list[dict]]) -> None:
        anchors = SectionAnalyzer(self.tpl).anchors()
        known = {anchor.category for anchor in anchors}
        # Unknown sections remain deterministic and are appended after known ones.
        anchors.extend(SectionAnchor(category, doc.page_count, MARGIN_T, None) for category in sorted(set(image_sections) - known))
        figure = 1
        inserted = 0
        printable_bottom = PAGE_H - MARGIN_B
        for anchor in anchors:
            remaining = list(image_sections.get(anchor.category, []))
            if not remaining:
                continue
            page_index = anchor.page + inserted
            ph = None
            if page_index < doc.page_count:
                ph_list = self.tpl.image_placeholders.get(anchor.category, [])
                ph = next((p for p in ph_list if p.page == anchor.page), None)
            
            # Use exact insert_rect coordinates from JSON when available,
            # but only for a single image.  For multiple images, fall back to
            # flow layout so they can paginate instead of overlapping.
            if ph is not None and ph.insert_rect is not None and len(remaining) == 1:
                rect = pymupdf.Rect(*ph.insert_rect)
                page = doc[page_index]
                img_data = remaining[0].get("data") or remaining[0].get("path")
                if isinstance(img_data, bytes):
                    page.insert_image(rect, stream=img_data, keep_proportion=True)
                else:
                    page.insert_image(rect, filename=img_data, keep_proportion=True)
                page.draw_rect(rect, color=(0.65, 0.65, 0.65), width=0.5)
                caption = f"Figura {figure} – {self._get_category_title(anchor.category)}."
                caption_width = pymupdf.get_text_length(caption, fontname="helv", fontsize=8)
                caption_y = rect.y1 + 2
                if caption_y < PAGE_H - MARGIN_B - 14:
                    page.insert_text(pymupdf.Point(rect.x0 + (rect.x1 - rect.x0) / 2 - caption_width / 2, caption_y), caption, fontname="helv", fontsize=8, color=(0.15, 0.15, 0.15))
                figure += 1
                continue
            
            # Fallback to flow layout for sections without exact coordinates
            if page_index >= doc.page_count:
                page_index = self._new_continuation_page(doc, doc.page_count, anchor.category)
                inserted += 1
                cursor_y = CONTINUATION_CURSOR_Y
                page_limit = printable_bottom
                flow_x = MARGIN_L
                flow_width = PAGE_W - MARGIN_L - MARGIN_R
                continuation = True
            else:
                cursor_y = max(MARGIN_T, anchor.cursor_y)
                page_limit = min(printable_bottom, anchor.flow_bottom or printable_bottom)
                flow_x = MARGIN_L
                flow_width = PAGE_W - MARGIN_L - MARGIN_R
                continuation = False

            while remaining:
                layout = self.image_layout_engine.solve(
                    remaining,
                    x=flow_x,
                    y=cursor_y,
                    width=flow_width,
                    height=page_limit - cursor_y,
                    require_full_width=not continuation,
                )
                if layout.page_break_recommendation:
                    insertion = page_index + 1
                    page_index = self._new_continuation_page(doc, insertion, anchor.category)
                    inserted += 1
                    cursor_y = CONTINUATION_CURSOR_Y
                    page_limit = printable_bottom
                    flow_x = MARGIN_L
                    flow_width = PAGE_W - MARGIN_L - MARGIN_R
                    continuation = True
                    continue
                self._render_grid(doc[page_index], layout, figure, anchor.category)
                figure += len(layout.placed)
                remaining = layout.remaining
                cursor_y += layout.required_height + SECTION_GAP
                if remaining:
                    page_index = self._new_continuation_page(doc, page_index + 1, anchor.category)
                    inserted += 1
                    cursor_y = CONTINUATION_CURSOR_Y
                    page_limit = printable_bottom
                    flow_x = MARGIN_L
                    flow_width = PAGE_W - MARGIN_L - MARGIN_R
                    continuation = True

    def _new_continuation_page(self, doc: pymupdf.Document, position: int, category: str) -> int:
        source = min(CONTINUATION_TEMPLATE_PAGE, doc.page_count - 1)
        self.page_renderer.duplicate_template_page(doc, source, position)
        page = doc[position]
        # A copied template page may contain its own body text (for example a
        # conclusions page).  Continuations reserve a clean flow canvas while
        # retaining the template's header and footer artwork.
        page.draw_rect(
            pymupdf.Rect(MARGIN_L, MARGIN_T, PAGE_W - MARGIN_R, PAGE_H - MARGIN_B),
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
        )
        title = f"{self._get_category_title(category).upper()} (CONT.)"
        self.text_renderer.render_title(page, title, MARGIN_L, MARGIN_T)
        return position

    def _render_grid(self, page: pymupdf.Page, layout: GridLayout, figure: int, category: str) -> None:
        for offset, placement in enumerate(layout.placed):
            rect = pymupdf.Rect(*placement.rect_coords)
            if isinstance(placement.data, str):
                page.insert_image(rect, filename=placement.data, keep_proportion=True)
            else:
                page.insert_image(rect, stream=placement.data, keep_proportion=True)
            page.draw_rect(rect, color=(0.65, 0.65, 0.65), width=0.5)
            caption = f"Figura {figure + offset} – {self._get_category_title(category)}."
            caption_width = pymupdf.get_text_length(caption, fontname="helv", fontsize=8)
            page.insert_text(pymupdf.Point(placement.caption_point_coords[0] - caption_width / 2, placement.caption_point_coords[1]), caption, fontname="helv", fontsize=8, color=(0.15, 0.15, 0.15))

    @staticmethod
    def _get_category_title(category: str) -> str:
        titles = {"le_print": "Laudo de Exigências", "extintor": "Extintor de incêndio", "hidrante_recalque": "Hidrante de recalque", "hidrante_urbano": "Hidrante urbano", "hidrante_caixa": "Caixa de mangueira", "cmi_exterior": "Casa de máquinas – vista externa", "cmi_interior": "Casa de máquinas – interior", "bomba_placa": "Placa de identificação da bomba", "curva_bomba": "Curva de desempenho da bomba", "alarme": "Alarme de incêndio", "sprinkler": "Sprinkler", "sinalizacao": "Sinalização de segurança", "iluminacao_emergencia": "Iluminação de emergência", "saida_emergencia": "Saída de emergência", "risco_especifico": "Risco específico", "fachada": "Fachada da edificação", "visao_geral": "Visão geral", "fotos_gerais": "Fotos gerais de inspeção"}
        return titles.get(category, category.replace("_", " ").title())
