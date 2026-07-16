"""Measurement Engine.

Pre-calculates precise visual heights for titles, wrapped text blocks, 
tables, and dynamic image grids.
"""

import math
import fitz

class MeasurementEngine:
    """Pre-computes heights of components to ensure robust layout pagination."""
    
    def measure_title(self, text: str, font_size: float = 14.0, spacing_before: float = 10.0, spacing_after: float = 8.0) -> float:
        if not text:
            return 0.0
        return font_size + spacing_before + spacing_after
        
    def measure_text(
        self,
        text: str,
        font_name: str = "helv",
        font_size: float = 10.0,
        max_width: float = 525.0,
        line_spacing: float = 1.2
    ) -> float:
        if not text:
            return 0.0
            
        words = text.replace("\n", " \n ").split(" ")
        lines = 0
        current_line = ""
        
        for word in words:
            if word == "\n":
                lines += 1
                current_line = ""
                continue
                
            test_line = current_line + " " + word if current_line else word
            line_w = fitz.get_text_length(test_line, fontname=font_name, fontsize=font_size)
            
            if line_w > max_width:
                lines += 1
                current_line = word
            else:
                current_line = test_line
                
        if current_line:
            lines += 1
            
        return max(1, lines) * font_size * line_spacing

    def measure_table(self, num_rows: int, row_height: float = 18.0, spacing_before: float = 10.0, spacing_after: float = 10.0) -> float:
        return (num_rows + 1) * row_height + spacing_before + spacing_after
