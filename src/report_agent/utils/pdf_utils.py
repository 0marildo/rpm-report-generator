import fitz


def get_page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def get_text_length(text: str, fontname: str = "helv", fontsize: float = 10.0) -> float:
    return fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
