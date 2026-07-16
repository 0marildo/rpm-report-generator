"""Layout Blocks.

Defines independent content blocks that represent sections of the report.
Each block exposes a deterministic measure() interface.
"""

import fitz
import math

class LayoutBlock:
    """Base class for all printable blocks in the document flow."""
    def measure(self, available_width: float, available_height: float) -> dict:
        return {
            "width": available_width,
            "height": 0.0,
            "minimumHeight": 0.0,
            "preferredHeight": 0.0,
            "spacingBefore": 0.0,
            "spacingAfter": 0.0,
            "pageBreakPolicy": "none"
        }

class TitleBlock(LayoutBlock):
    def __init__(self, text: str, font_size: float = 14.0, spacing_before: float = 10.0, spacing_after: float = 8.0):
        self.text = text
        self.font_size = font_size
        self.spacing_before = spacing_before
        self.spacing_after = spacing_after
        
    def measure(self, available_width: float, available_height: float) -> dict:
        h = self.font_size + self.spacing_before + self.spacing_after
        return {
            "width": available_width,
            "height": h,
            "minimumHeight": h,
            "preferredHeight": h,
            "spacingBefore": self.spacing_before,
            "spacingAfter": self.spacing_after,
            "pageBreakPolicy": "avoid"
        }

class TextBlock(LayoutBlock):
    def __init__(self, text: str, font_size: float = 10.0, spacing_before: float = 4.0, spacing_after: float = 4.0):
        self.text = text
        self.font_size = font_size
        self.spacing_before = spacing_before
        self.spacing_after = spacing_after
        
    def measure(self, available_width: float, available_height: float) -> dict:
        from .measurement_engine import MeasurementEngine
        me = MeasurementEngine()
        h_text = me.measure_text(self.text, font_size=self.font_size, max_width=available_width)
        h = h_text + self.spacing_before + self.spacing_after
        return {
            "width": available_width,
            "height": h,
            "minimumHeight": self.font_size * 1.2 + self.spacing_before + self.spacing_after,
            "preferredHeight": h,
            "spacingBefore": self.spacing_before,
            "spacingAfter": self.spacing_after,
            "pageBreakPolicy": "none"
        }

class ImageGridBlock(LayoutBlock):
    def __init__(self, images: list[dict], category: str, spacing_before: float = 8.0, spacing_after: float = 8.0):
        self.images = images
        self.category = category
        self.spacing_before = spacing_before
        self.spacing_after = spacing_after
        
    def measure(self, available_width: float, available_height: float) -> dict:
        if not self.images:
            return super().measure(available_width, available_height)
            
        from .image_layout_engine import ImageLayoutEngine
        engine = ImageLayoutEngine()
        margins = {"left": 35.0, "right": 35.0, "top": 55.0, "bottom": 55.0}
        
        # Calculate full size needed on a blank page
        res = engine.calculate_layout(self.images, available_width, 732.0, margins, 732.0)
        h = res["required_height"] + self.spacing_before + self.spacing_after
        return {
            "width": available_width,
            "height": h,
            "minimumHeight": 110.0,
            "preferredHeight": h,
            "spacingBefore": self.spacing_before,
            "spacingAfter": self.spacing_after,
            "pageBreakPolicy": "avoid"
        }

class TableBlock(LayoutBlock):
    def __init__(self, fields: dict[str, str], spacing_before: float = 10.0, spacing_after: float = 10.0):
        self.fields = fields
        self.spacing_before = spacing_before
        self.spacing_after = spacing_after
        
    def measure(self, available_width: float, available_height: float) -> dict:
        h = len(self.fields) * 18.0 + 10.0 + self.spacing_before + self.spacing_after
        return {
            "width": available_width,
            "height": h,
            "minimumHeight": h,
            "preferredHeight": h,
            "spacingBefore": self.spacing_before,
            "spacingAfter": self.spacing_after,
            "pageBreakPolicy": "avoid"
        }
