"""Table Renderer.

Renders and populates table cells for tabular data.
"""

import fitz

class TableRenderer:
    """Helper to populate table-structured field values."""
    
    def fill_table_cells(
        self,
        page: fitz.Page,
        fields: dict[str, str],
        field_defs: dict,
        color: tuple[float, float, float] = (0.15, 0.15, 0.15)
    ) -> None:
        """Draw text values inside pre-drawn template table boundaries."""
        for field_name, value in fields.items():
            if not value:
                continue
            fd = field_defs.get(field_name)
            if fd is None:
                continue
                
            full_text = str(value).strip()
            font_size = fd.font_size
            text_w = fitz.get_text_length(full_text, fontname="helv", fontsize=font_size)
            
            # Scale down font size if it overflows cell width
            if text_w > fd.max_width:
                font_size = max(5, int(font_size * (fd.max_width / text_w)))
                
            center_y = (fd.value_top + fd.value_bottom) / 2
            page.insert_text(
                fitz.Point(fd.value_x, center_y),
                full_text,
                fontname="helv",
                fontsize=font_size,
                color=color
            )
