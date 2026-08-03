import json
import os
import base64
import io
import mimetypes
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()


PAGE_IMAGE_DPI = 200
MAX_PAGES_PER_CALL = 6
MAX_IMAGE_SIDE = 1024


def _downscale_image(data: bytes, mime_type: str = "image/png") -> bytes:
    """Downscale large images to reduce token usage during vision calls."""
    try:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        mime_for_ext = {
            "image/png": "PNG",
            "image/jpeg": "JPEG",
            "image/webp": "WEBP",
        }
        if width <= MAX_IMAGE_SIDE and height <= MAX_IMAGE_SIDE:
            return data
        ratio = min(MAX_IMAGE_SIDE / width, MAX_IMAGE_SIDE / height)
        new_size = (int(width * ratio), int(height * ratio))
        downscaled = image.resize(new_size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        fmt = mime_for_ext.get(mime_type.lower().split(";")[0], "PNG")
        downscaled.save(out, format=fmt)
        return out.getvalue()
    except Exception:
        return data


def pdf_page_images(
    pdf_path: str,
    *,
    start_page: int | None = None,
    end_page: int | None = None,
    dpi: int = PAGE_IMAGE_DPI,
) -> Iterable[tuple[int, bytes, str]]:
    """Render PDF pages as PNG bytes."""
    doc = fitz.open(pdf_path)
    total = len(doc)
    begin = start_page if start_page is not None else 0
    end = end_page if end_page is not None else total
    for page_index in range(begin, min(end, total)):
        page = doc[page_index]
        mime_type = "image/png"
        pix = page.get_pixmap(dpi=dpi)
        data = pix.tobytes("png")
        data = _downscale_image(data, mime_type)
        yield page_index + 1, data, mime_type
    doc.close()


class GeminiClient:
    def __init__(self, model_name: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Create a .env file or export the variable."
            )
        self.model_name = model_name or os.getenv(
            "GEMINI_MODEL", "gemini-3.1-flash"
        )
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
        )

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))
        response = self.llm.invoke(messages)
        return response.content

    def generate_with_pdf(
        self, prompt: str, pdf_path: str, system_instruction: str | None = None
    ) -> str:
        pages = list(pdf_page_images(pdf_path))
        if not pages:
            raise ValueError(f"No pages rendered from {pdf_path}")
        text_parts = []
        for page_num, image_data, mime_type in pages:
            text_parts.append(f"[Page {page_num}]")
            b64_data = base64.b64encode(image_data).decode("utf-8")
            text_parts.append(
                json.dumps(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_data}",
                        },
                    }
                )
            )
        payload = "\n".join(text_parts)
        response = self.llm.invoke(
            [
                SystemMessage(content=system_instruction or "You are a document vision assistant."),
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {"type": "text", "text": payload},
                    ]
                ),
            ]
        )
        return response.content

    def classify_image(self, image_path: str, prompt: str) -> str:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}},
                ]
            )
        ]
        response = self.llm.invoke(messages)
        return response.content.strip()
