"""Page Renderer.

Manages page creation, background artwork copy, and layout boundaries.
"""

import fitz

class PageRenderer:
    """Handles page-level operations and background layouts."""
    
    def duplicate_template_page(
        self,
        doc: fitz.Document,
        src_page_index: int,
        target_position: int
    ) -> fitz.Page:
        """Create a new page by copying background artwork from an existing template page."""
        # ``insert_pdf`` cannot use the same document as both source and target
        # in current PyMuPDF versions.  ``fullcopy_page`` is the corresponding
        # in-document operation and preserves the source page artwork.
        doc.fullcopy_page(src_page_index, to=target_position)
        return doc[target_position]
        
    def get_printable_area(self) -> fitz.Rect:
        """Return the standard margins and printable bounds for A4 pages."""
        # Standard A4 size: 595.0 x 842.0
        # margins: left=35, top=55, right=35, bottom=55
        return fitz.Rect(35.0, 55.0, 560.0, 787.0)
