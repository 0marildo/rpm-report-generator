"""Template-aware PDF renderer.

Fills text fields and places images into the new_template.pdf using
dynamically discovered field positions and image placeholder zones.
"""

import logging
from collections import defaultdict
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
from .image_layout_engine import (
    ImageLayoutEngine,
    draw_images_on_page,
    create_image_page,
    SECTION_TITLE_SIZE,
    SECTION_TITLE_GAP,
    MARGIN_L,
    MARGIN_T,
    MARGIN_R,
    MARGIN_B,
)

logger = logging.getLogger(__name__)

TEXT_DARK = (0.15, 0.15, 0.15)

SECTION_LABELS = {
    "le_print": "LAUDO DE EXIGÊNCIAS",
    "extintor": "EXTINTORES",
    "hidrante_recalque": "HIDRANTE DE RECALQUE",
    "hidrante_urbano": "HIDRANTE URBANO",
    "hidrante_caixa": "CAIXAS DE MANGUEIRA",
    "cmi": "CASA DE MÁQUINAS DE INCÊNDIO",
    "cmi_exterior": "CASA DE MÁQUINAS DE INCÊNDIO",
    "cmi_interior": "CASA DE MÁQUINAS DE INCÊNDIO",
    "bomba_placa": "BOMBAS DE INCÊNDIO",
    "curva_bomba": "CURVA DA BOMBA",
    "alarme": "ALARME DE INCÊNDIO",
    "sprinkler": "SPRINKLERS",
    "sinalizacao": "SINALIZAÇÃO DE SEGURANÇA",
    "iluminacao_emergencia": "ILUMINAÇÃO DE EMERGÊNCIA",
    "saida_emergencia": "SAÍDAS DE EMERGÊNCIA",
    "risco_especifico": "RISCOS ESPECÍFICOS",
    "fachada": "FACHADA",
    "visao_geral": "VISÃO GERAL",
    "fotos_gerais": "FOTOS DE INSPEÇÃO",
}


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

        # First, cover all template placeholders (example photos and text instructions)
        self._clear_template_placeholders(doc)

        self._fill_text_fields(doc, fields)
        self._place_images(doc, image_sections)

        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        logger.info("Report saved to %s", output_path)
        return output_path

    def _clear_template_placeholders(self, doc: fitz.Document) -> None:
        # 1. Cover all parsed image placeholders' areas and text blocks in the template
        for cat, ph_list in self.tpl.image_placeholders.items():
            for ph in ph_list:
                if ph.page < doc.page_count:
                    page = doc[ph.page]
                    # Cover insert instruction text
                    ir = fitz.Rect(ph.insert_rect)
                    page.draw_rect(ir, color=(1, 1, 1), fill=(1, 1, 1), width=0)
                    
                    # Cover the entire placeholder slot area
                    sr = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
                    page.draw_rect(sr, color=(1, 1, 1), fill=(1, 1, 1), width=0)

        # 2. Cover any remaining embedded placeholder images (anything other than background xref=9 on target pages)
        target_pages = [2, 3, 4, 6, 8, 9] # pages 3, 4, 5, 7, 9, 10
        for pg_idx in target_pages:
            if pg_idx >= doc.page_count:
                continue
            page = doc[pg_idx]
            image_info = page.get_image_info()
            for info in image_info:
                bbox = info.get('bbox')
                if bbox:
                    x0, y0, x1, y1 = bbox
                    w = x1 - x0
                    h = y1 - y0
                    # Keep full-page background artwork and cover sample images
                    if not (w > 580 and h > 800):
                        rect = fitz.Rect(x0, y0, x1, y1)
                        rect.x0 -= 2
                        rect.y0 -= 2
                        rect.x1 += 2
                        rect.y1 += 2
                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), width=0)

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
        engine = ImageLayoutEngine()
        overflow_pages: dict[int, list[tuple[str, list]]] = {}
        idx_counter = 1

        for cat, ph_list in self.tpl.image_placeholders.items():
            images = image_sections.get(cat, [])
            if not images:
                continue

            slot_rect = None
            slot_page = 0
            for ph in ph_list:
                h = ph.area_bottom - ph.area_top
                if h >= 80:
                    slot_rect = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
                    slot_page = ph.page
                    break
            if slot_rect is None and ph_list:
                ph = ph_list[0]
                slot_rect = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
                slot_page = ph.page

            title_h = SECTION_TITLE_SIZE + SECTION_TITLE_GAP
            result = engine.layout_section(
                images, cat, slot_rect, start_index=idx_counter,
                overflow_title_height=title_h,
            )
            idx_counter += len(result["placed"]) + sum(len(p) for p in result["new_pages"])

            if result["placed"] and slot_rect:
                draw_images_on_page(doc[slot_page], result["placed"])

            if result["new_pages"]:
                target_page = slot_rect and slot_page or 0
                overflow_pages.setdefault(target_page, []).append(
                    (cat, result["new_pages"])
                )

        for cat, images in image_sections.items():
            if cat in self.tpl.image_placeholders:
                continue
            if not images:
                continue
            ph_list = self.tpl.image_placeholders.get(cat, [])
            slot_rect = None
            slot_page = 0
            if ph_list:
                ph = ph_list[0]
                slot_rect = fitz.Rect(ph.area_x0, ph.area_top, ph.area_x1, ph.area_bottom)
                slot_page = ph.page

            result = engine.layout_section(
                images, cat, slot_rect, start_index=idx_counter,
                overflow_title_height=SECTION_TITLE_SIZE + SECTION_TITLE_GAP,
            )
            idx_counter += len(result["placed"]) + sum(len(p) for p in result["new_pages"])

            if result["placed"] and slot_rect:
                draw_images_on_page(doc[slot_page], result["placed"])
            if result["new_pages"]:
                overflow_pages.setdefault(slot_page or 0, []).append(
                    (cat, result["new_pages"])
                )

        overflow_flat: list[tuple[int, str, list]] = []
        for tpl_pg in sorted(overflow_pages.keys()):
            for cat, page_groups in overflow_pages[tpl_pg]:
                for pg in page_groups:
                    overflow_flat.append((tpl_pg, cat, pg))

        offset = 0
        for tpl_pg, cat, placed_group in overflow_flat:
            section_title = SECTION_LABELS.get(cat, cat.upper())
            create_image_page(
                doc, placed_group,
                section_title=section_title,
                page_w=PAGE_W, page_h=PAGE_H,
                margins=(MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B),
                position=tpl_pg + 1 + offset,
            )
            offset += 1
