"""Deterministic grid measurement for inspection photos.

This module deliberately has no knowledge of PDF templates.  A caller gives it
the usable flow region and it returns a measured grid; placeholder rectangles
are therefore incapable of limiting image size.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import math
from statistics import median

from PIL import Image


GRID_GAP = 10.0
CAPTION_HEIGHT = 14.0
CAPTION_GAP = 4.0
CAPTION_RESERVE = CAPTION_HEIGHT + CAPTION_GAP
SINGLE_IMAGE_WIDTH_RATIO = 0.90
MAX_IMAGES_PER_PAGE = 4


@dataclass(frozen=True)
class ImagePlacement:
    """A measured image box and its caption baseline, relative to a flow box."""

    rect_coords: tuple[float, float, float, float]
    caption_point_coords: tuple[float, float]
    data: bytes | str
    filename: str


@dataclass(frozen=True)
class GridLayout:
    placed: list[ImagePlacement]
    remaining: list[dict]
    required_height: float
    page_break_recommendation: bool


class ImageLayoutEngine:
    """Measure specialized, aspect-ratio-preserving image grids.

    The returned rectangles are equally sized inside each multi-image grid.
    PyMuPDF's ``keep_proportion`` rendering then contains each source image in
    that common box without distortion.
    """

    def calculate_layout(
        self,
        images: list[dict],
        available_width: float,
        available_height: float,
        page_margins: dict | None = None,
        remaining_page_height: float | None = None,
    ) -> dict:
        """Compatibility wrapper returning the historic dictionary shape."""
        left = (page_margins or {}).get("left", 0.0)
        layout = self.solve(
            images,
            x=left,
            y=0.0,
            width=available_width,
            height=remaining_page_height if remaining_page_height is not None else available_height,
        )
        return {
            "placed": [placement.__dict__ for placement in layout.placed],
            "remaining": layout.remaining,
            "required_height": layout.required_height,
            "page_break_recommendation": layout.page_break_recommendation,
        }

    def solve(
        self,
        images: list[dict],
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        require_full_width: bool = False,
    ) -> GridLayout:
        """Measure the next page-sized batch in the supplied flow region.

        More than four images are intentionally left in ``remaining``; the
        paginator creates a continuation page instead of shrinking a grid into
        thumbnails.
        """
        if not images:
            return GridLayout([], [], 0.0, False)
        if width <= 0 or height <= 0:
            return GridLayout([], images, 0.0, True)

        batch = images[:MAX_IMAGES_PER_PAGE]
        count = len(batch)
        cols, rows = self._grid_shape(count)
        cell_width = (
            width * SINGLE_IMAGE_WIDTH_RATIO
            if count == 1
            else (width - (cols - 1) * GRID_GAP) / cols
        )
        max_image_height = (height - (rows - 1) * GRID_GAP) / rows - CAPTION_RESERVE
        if cell_width <= 0 or max_image_height <= 0:
            return GridLayout([], images, 0.0, True)

        # A common box gives the grid a deliberate visual rhythm.  Its aspect
        # is based on the batch, not on a template sample-image rectangle.
        aspects = [self._aspect(image.get("data") or image.get("path")) for image in batch]
        representative_aspect = max(0.25, min(4.0, float(median(aspects))))
        preferred_image_height = cell_width / representative_aspect
        # On an anchored template page, do not narrow a grid merely to squeeze
        # it before the next text block. The paginator will put it on a clean
        # continuation page, where vertical space is genuinely available.
        if require_full_width and max_image_height + 0.01 < preferred_image_height:
            return GridLayout([], images, 0.0, True)
        image_height = min(max_image_height, preferred_image_height)
        if image_height <= 0:
            return GridLayout([], images, 0.0, True)

        cell_height = image_height + CAPTION_RESERVE
        required_height = rows * cell_height + (rows - 1) * GRID_GAP
        if required_height > height + 0.01:
            return GridLayout([], images, 0.0, True)

        placements: list[ImagePlacement] = []
        for index, image in enumerate(batch):
            row, column = divmod(index, cols)
            row_count = min(cols, count - row * cols)
            row_width = row_count * cell_width + (row_count - 1) * GRID_GAP
            row_x = x + (width - row_width) / 2
            cell_x = row_x + column * (cell_width + GRID_GAP)
            cell_y = y + row * (cell_height + GRID_GAP)
            placements.append(
                ImagePlacement(
                    rect_coords=(cell_x, cell_y, cell_x + cell_width, cell_y + image_height),
                    caption_point_coords=(cell_x + cell_width / 2, cell_y + image_height + CAPTION_HEIGHT),
                    data=image.get("data") or image.get("path"),
                    filename=image.get("filename") or "image.jpg",
                )
            )
        return GridLayout(placements, images[count:], required_height, False)

    @staticmethod
    def _grid_shape(count: int) -> tuple[int, int]:
        # Explicit compositions keep the visual result stable and intentional.
        if count == 1:
            return 1, 1
        if count == 2:
            return 2, 1
        # Three uses a centered final item; four is a symmetric 2x2.
        return 2, 2

    @staticmethod
    def _aspect(source: bytes | str | None) -> float:
        try:
            image = Image.open(source) if isinstance(source, str) else Image.open(io.BytesIO(source or b""))
            width, height = image.size
            orientation = image.getexif().get(0x0112, 1)
            if orientation in (6, 8):
                width, height = height, width
            return width / height if height else 1.0
        except Exception:
            return 1.0
