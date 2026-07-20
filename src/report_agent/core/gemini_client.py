import os
import base64
import mimetypes
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()


class GeminiClient:
    def __init__(self, model_name: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Create a .env file or export the variable."
            )
        self.model_name = model_name or os.getenv(
            "GEMINI_MODEL", "gemini-2.5-flash"
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
        mime_type = mimetypes.guess_type(pdf_path)[0] or "application/pdf"
        with open(pdf_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "media", "data": b64_data, "mime_type": mime_type},
                ]
            )
        )
        response = self.llm.invoke(messages)
        return response.content

    def classify_image(self, image_path: str, prompt: str) -> str:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "media", "data": b64_data, "mime_type": mime_type},
                ]
            )
        ]
        response = self.llm.invoke(messages)
        return response.content.strip()
