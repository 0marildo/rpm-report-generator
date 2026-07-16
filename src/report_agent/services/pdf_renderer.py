"""PDF Renderer.

Low-level PDF compiler operations: opening and saving files with garbage collection.
"""

import fitz

class PDFRenderer:
    """Handles core PDF file open and save transactions."""
    
    def open_document(self, file_path: str) -> fitz.Document:
        return fitz.open(file_path)
        
    def save_document(self, doc: fitz.Document, output_path: str) -> str:
        doc.save(output_path, garbage=4, deflate=True)
        return output_path
