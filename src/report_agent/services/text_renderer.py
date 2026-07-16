"""Text Renderer.

Handles drawing of section titles and paragraphs on PDF pages.
"""

import fitz

class TextRenderer:
    """Helper to draw text blocks on a page."""
    
    def render_title(
        self,
        page: fitz.Page,
        text: str,
        x: float,
        y: float,
        font_size: float = 14.0,
        color: tuple[float, float, float] = (0.15, 0.15, 0.15)
    ) -> float:
        """Draw a bold section title and return its height + margin."""
        page.insert_text(
            fitz.Point(x, y + font_size),
            text,
            # Built-in Helvetica is portable across the PyMuPDF versions used
            # by the API; weight is handled by the surrounding template style.
            fontname="helv",
            fontsize=font_size,
            color=color
        )
        return font_size + 8.0
        
    def render_paragraph(
        self,
        page: fitz.Page,
        text: str,
        rect: fitz.Rect,
        font_size: float = 10.0,
        color: tuple[float, float, float] = (0.2, 0.2, 0.2),
        line_spacing: float = 1.2
    ) -> float:
        """Render a wrapped text block inside rect and return height."""
        # Using insert_textbox which handles word-wrap natively in PyMuPDF
        page.insert_textbox(
            rect,
            text,
            fontname="helv",
            fontsize=font_size,
            color=color,
            align=0 # Left aligned
        )
        return rect.height
