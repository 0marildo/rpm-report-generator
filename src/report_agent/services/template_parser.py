import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz

TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
# The production template contains section instructions only; it no longer
# embeds sample photographs that have to be removed during report generation.
DEFAULT_TEMPLATE = "template novo v2.pdf"

PAGE_W = 595
PAGE_H = 842
MARGIN_X = 35
MARGIN_RIGHT = 40
CONTENT_W = PAGE_W - MARGIN_X - MARGIN_RIGHT


@dataclass
class TextFieldDef:
    page: int
    label: str
    label_rect: tuple[float, float, float, float]
    value_x: float
    value_top: float
    value_bottom: float
    max_width: float = 350
    font_size: int = 10


@dataclass
class ImagePlaceholderDef:
    page: int
    category: str
    insert_text: str
    insert_rect: tuple[float, float, float, float]
    area_top: float
    area_bottom: float
    area_x0: float
    area_x1: float


@dataclass
class TemplateDef:
    text_fields: dict[str, TextFieldDef] = field(default_factory=dict)
    image_placeholders: dict[str, list[ImagePlaceholderDef]] = field(default_factory=dict)
    page_count: int = 0


# Keyword → category mapping for INSERIR placeholders (longer matches first)
_PLACEHOLDER_RULES_RAW = [
    ("PRINT DO LE", "le_print"),
    ("CMI DO LADO DE FORA MOSTRANDO PCF, SINALIZAÇÃO E PROTEÇÃO POR EXTINTORES", "cmi_exterior"),
    ("INTERIOR DA CMI MOSTRANDO O CONJUNTO DE BOMBAS, QUADRO ELÉTRICO E MANÔMETRO", "cmi_interior"),
    ("PLACAS DE IDENTIFICAÇÃO DAS BOMBAS", "bomba_placa"),
    ("ETIQUETA DE IDENTIFICAÇÃO DA BOMBA", "bomba_placa"),
    ("CURVA DE DESEMPENHO DA BOMBA", "curva_bomba"),
    ("HIDRANTE DE RECALQUE ABERTO E FECHADO E FOTO DISTANTE", "hidrante_recalque"),
    ("HIDRANTE DE RECALQUE", "hidrante_recalque"),
    ("HIDRANTE E IMAGEM DO GOOGLE", "hidrante_urbano"),
    ("EXTINTORES", "extintor"),
    ("ALARMES", "alarme"),
    ("SPRINKLER", "sprinkler"),
    ("SINALIZAÇÕES", "sinalizacao"),
    ("ILUMINAÇÕES", "iluminacao_emergencia"),
    ("SAÍDAS DE EMERGÊNCIA", "saida_emergencia"),
    ("GERADOR, EXAUSTÃO, GÁS, SPDA", "risco_especifico"),
    ("PRESSURIZAÇÃO DE ESCADAS", "risco_especifico"),
    ("FACHADA", "fachada"),
    ("FOTOS OS DISPOSITIVOS DE MODO GERAL", "visao_geral"),
    ("FOTOS DO LOCAL", "visao_geral"),
    ("VISÃO GERAL", "fachada"),
]
# Sort by keyword length descending so most specific match first
PLACEHOLDER_RULES = sorted(_PLACEHOLDER_RULES_RAW, key=lambda x: -len(x[0]))

TEXT_FIELD_KEYS = [
    ("proprietario", "Proprietário", 11),
    ("cnpj", "CNPJ", 10),
    ("endereco", "Endereço", 10),
    ("classificacao", "Classificação", 10),
    ("num_pavimentos", "Número de Pavimentos", 10),
    ("area_total", "Área Total Construída", 10),
    ("processo", "Processo", 10),
    ("laudo_exigencias", "Laudo de exigências", 10),
    ("fabricante", "nome do fabricante", 9),
    ("serie", "número de série", 9),
    ("modelo", "modelo da bomba", 9),
    ("vazao_nominal", "vazão nominal", 9),
    ("pressao_nominal", "pressão nominal", 9),
    ("rpm", "rotações por minuto de regime", 8),
    ("diametro_rotor", "diâmetro do rotor", 9),
    ("potencia_cv", "potência, em CV", 9),
]


def _parse_text_fields(page_num: int, blocks: list) -> dict[str, TextFieldDef]:
    fields = {}
    for b in blocks:
        if b['type'] != 0:
            continue
        text = ''
        for ln in b.get('lines', []):
            for s in ln.get('spans', []):
                text += s['text']
        text = text.strip()
        if ':' not in text:
            continue
        bx0, by0, bx1, by1 = b['bbox']

        for key, key_label, font_size in TEXT_FIELD_KEYS:
            if key_label.lower() in text.lower().split(':')[0]:
                colon_idx = text.find(':')
                after_colon = text[colon_idx + 1:].strip()
                if after_colon:
                    val_width = fitz.get_text_length(after_colon, fontname="helv", fontsize=font_size)
                    max_width = max(250, val_width + 20)
                else:
                    max_width = 300
                fields[key] = TextFieldDef(
                    page=page_num,
                    label=text.split(':')[0].strip(),
                    label_rect=(bx0, by0, bx1, by1),
                    value_x=bx1 + 4,
                    value_top=by0,
                    value_bottom=by1,
                    max_width=min(max_width, PAGE_W - bx1 - MARGIN_RIGHT),
                    font_size=font_size,
                )
                break
    return fields


def _parse_image_placeholders(page_num: int, blocks: list) -> dict[str, list[ImagePlaceholderDef]]:
    """Find INSERIR/COLOCAR lines and compute image placement areas."""
    from collections import defaultdict
    placeholders: dict[str, list[ImagePlaceholderDef]] = defaultdict(list)

    for i, b in enumerate(blocks):
        if b['type'] != 0:
            continue
        text = ''
        for ln in b.get('lines', []):
            for s in ln.get('spans', []):
                text += s['text']
        text = text.strip()
        upper = text.upper()
        is_insert = 'INSERIR' in upper or 'COLOCAR' in upper
        if not is_insert:
            continue

        bx0, by0, bx1, by1 = b['bbox']

        # Determine category: check each rule in order
        best_cat = None
        for keyword, cat in PLACEHOLDER_RULES:
            if keyword in upper:
                best_cat = cat
                break
        if best_cat is None:
            continue

        # Compute placement area
        area_top = by1 + 5
        area_x0 = MARGIN_X
        area_x1 = PAGE_W - MARGIN_RIGHT

        # Find next text block below on SAME page
        area_bottom = PAGE_H - 60
        for j in range(i + 1, len(blocks)):
            nb = blocks[j]
            if nb['type'] != 0:
                continue
            nb_text = ''
            for ln in nb.get('lines', []):
                for s in ln.get('spans', []):
                    nb_text += s['text']
            nb_text = nb_text.strip()
            nby0 = nb['bbox'][1]
            # skip INSERIR lines that start before the current one ends
            if ('INSERIR' in nb_text.upper() or 'COLOCAR' in nb_text.upper()):
                if nby0 > area_top - 10:
                    # Use this INSERIR line's top as the bottom boundary (next section)
                    area_bottom = nby0 - 8
                break
            if nby0 > area_top + 5:
                area_bottom = nby0 - 8
                break

        # Ensure minimum height for image area
        min_h = 130
        if area_bottom - area_top < min_h:
            area_bottom = area_top + min_h
        if area_bottom > PAGE_H - 45:
            area_bottom = PAGE_H - 45

        placeholders[best_cat].append(ImagePlaceholderDef(
            page=page_num,
            category=best_cat,
            insert_text=text,
            insert_rect=(bx0, by0, bx1, by1),
            area_top=area_top,
            area_bottom=area_bottom,
            area_x0=area_x0,
            area_x1=area_x1,
        ))

    return dict(placeholders)


def parse_template(template_path: str | None = None) -> TemplateDef:
    if template_path is None:
        template_path = str(TEMPLATES_DIR / DEFAULT_TEMPLATE)
    doc = fitz.open(template_path)
    tpl = TemplateDef(page_count=doc.page_count)

    for pg in range(doc.page_count):
        page = doc[pg]
        blocks = page.get_text('dict')['blocks']

        tpl.text_fields.update(_parse_text_fields(pg, blocks))
        tpl.image_placeholders.update(_parse_image_placeholders(pg, blocks))

    doc.close()
    return tpl


def dump_template(tpl: TemplateDef) -> None:
    print(f"Template: {tpl.page_count} pages, "
          f"{len(tpl.text_fields)} text fields, {len(tpl.image_placeholders)} image placeholders")
    print("\nText fields:")
    for name, f in sorted(tpl.text_fields.items(), key=lambda x: (x[1].page, x[1].value_top)):
        print(f"  {name:20s} pg={f.page + 1} x={f.value_x:.0f} y={f.value_top:.0f}-{f.value_bottom:.0f} [{f.label}]")


if __name__ == "__main__":
    tpl = parse_template()
    dump_template(tpl)
