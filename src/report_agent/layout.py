from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ImageSlot:
    x: float
    y: float
    width: float
    height: float


class ImageLayoutError(Exception):
    """Raised when requested images cannot be placed under the given constraints."""


# PDF annotation flag values per PDF 32000-1:2008 Table 186.
# PyMuPDF <1.29.0 does not expose these constants, so they are repeated here.
_PDF_ANNOT_FLAG_LOCKED = 1 << 9  # bit 9
_PDF_ANNOT_FLAG_NO_VIEW = 1 << 5  # bit 5


def compute_image_layout_constraints(
    area_width_px: float,
    area_height_px: float,
    image_count: int,
    *,
    margin_px: tuple[float, float, float, float] = (50.0, 50.0, 50.0, 50.0),
    gap_px: float = 20.0,
    min_image_width_px: float = 200.0,
    min_image_height_px: float = 160.0,
) -> tuple[int, int, float]:
    """Return (cols, rows, cell_size_px) for the requested image count.
    cell_size_px is the square side in pixels at 96 DPI.
    Raises ImageLayoutError if placement is impossible.
    """
    if image_count <= 0:
        raise ImageLayoutError("Nenhuma imagem para posicionar.")
    if image_count > 9:
        raise ImageLayoutError("Limite máximo de 9 imagens por seção.")
    if gap_px < 0:
        raise ImageLayoutError("O espaçamento entre imagens não pode ser negativo.")
    if min_image_width_px <= 0 or min_image_height_px <= 0:
        raise ImageLayoutError("Dimensões mínimas de imagem devem ser positivas.")

    content_w = area_width_px - margin_px[1] - margin_px[3]
    content_h = area_height_px - margin_px[0] - margin_px[2]
    if content_w <= 0 or content_h <= 0:
        raise ImageLayoutError(
            "A área disponível para imagens é menor que as margens informadas. "
            "Será necessário edição manual do PDF."
        )

    for cols in range(1, 4):
        rows = max(1, (image_count + cols - 1) // cols)
        cell_w = (content_w - (cols - 1) * gap_px) / cols
        cell_h = (content_h - (rows - 1) * gap_px) / rows
        cell_size = min(cell_w, cell_h)
        if cell_size < min_image_width_px or cell_size < min_image_height_px:
            continue
        return cols, rows, cell_size

    raise ImageLayoutError(
        "Não foi possível posicionar as imagens com as restrições fornecidas. "
        "Será necessário edição manual do PDF."
    )


def layout_images(
    area_x: float,
    area_y: float,
    area_width: float,
    area_height: float,
    image_count: int,
    min_gap: float,
    min_height: float,
    max_height: float,
    *,
    margin_px: tuple[float, float, float, float] = (50.0, 50.0, 50.0, 50.0),
    gap_px: float = 20.0,
    min_image_width_px: float = 200.0,
    min_image_height_px: float = 160.0,
) -> tuple[ImageSlot, ...]:
    if image_count <= 0:
        raise ValueError("image_count must be > 0")
    if image_count > 9:
        raise ValueError("image_count must be <= 9")
    if min_gap < 0:
        raise ValueError("min_gap must be >= 0")
    if min_height <= 0 or max_height < min_height:
        raise ValueError("invalid min_height/max_height")

    POINTS_PER_PIXEL = 72.0 / 96.0
    cols, rows, cell_size_px = compute_image_layout_constraints(
        area_width * (1.0 / POINTS_PER_PIXEL),
        area_height * (1.0 / POINTS_PER_PIXEL),
        image_count,
        margin_px=margin_px,
        gap_px=gap_px,
        min_image_width_px=min_image_width_px,
        min_image_height_px=min_image_height_px,
    )
    cell_size = cell_size_px * POINTS_PER_PIXEL
    min_gap_pt = min_gap * POINTS_PER_PIXEL if gap_px else min_gap

    total_w = cols * cell_size + (cols - 1) * min_gap_pt
    total_h = rows * cell_size + (rows - 1) * min_gap_pt
    offset_x = area_x + (area_width - total_w) / 2
    offset_y = area_y + (area_height - total_h) / 2

    slots: list[ImageSlot] = []
    for idx in range(image_count):
        col = idx % cols
        row = idx // cols
        slots.append(ImageSlot(
            x=offset_x + col * (cell_size + min_gap_pt),
            y=offset_y + row * (cell_size + min_gap_pt),
            width=cell_size,
            height=cell_size,
        ))

    return tuple(slots)


def lock_background_image(page, rect) -> None:  # type: ignore[no-untyped-def]
    """Place an invisible annotation on top of the background image so it is locked."""
    try:
        import pymupdf

        annot = page.add_rect_annot(rect)
        annot.set_colors(stroke=None, fill=None)
        annot.set_opacity(0)
        annot.set_flags(_PDF_ANNOT_FLAG_LOCKED | _PDF_ANNOT_FLAG_NO_VIEW)
    except Exception as exc:
        raise ImageLayoutError(f"Falha ao travar a imagem de fundo: {exc}") from exc


__all__ = [
    "ImageSlot",
    "ImageLayoutError",
    "layout_images",
    "compute_image_layout_constraints",
    "lock_background_image",
]

