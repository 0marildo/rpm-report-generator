"""FastAPI REST API server with Gradio UI mounted."""

import logging
import os
import tempfile

import fitz
import gradio as gr
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .pipeline.orchestrator import ExtractionOrchestrator
from .pipeline.document_merger import DocumentMerger
from .services.template_parser import DEFAULT_TEMPLATE

logger = logging.getLogger(__name__)

app = FastAPI(title="Report Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = ExtractionOrchestrator()
merger = DocumentMerger()

TEMPLATES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates")
)
STATIC_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "static")
)
os.makedirs(STATIC_DIR, exist_ok=True)

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "report-agent", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/template-layout")
async def get_template_layout():
    from .services.template_parser import parse_template
    try:
        tpl = parse_template()
        text_fields = {}
        for key, fd in tpl.text_fields.items():
            text_fields[key] = {
                "page": fd.page,
                "label": fd.label,
                "label_rect": list(fd.label_rect),
                "value_x": fd.value_x,
                "value_top": fd.value_top,
                "value_bottom": fd.value_bottom,
                "max_width": fd.max_width,
                "font_size": fd.font_size,
            }
        image_placeholders = {}
        for key, ph_list in tpl.image_placeholders.items():
            image_placeholders[key] = [
                {
                    "page": ph.page,
                    "category": ph.category,
                    "insert_text": ph.insert_text,
                    "insert_rect": list(ph.insert_rect),
                    "area_top": ph.area_top,
                    "area_bottom": ph.area_bottom,
                    "area_x0": ph.area_x0,
                    "area_x1": ph.area_x1,
                }
                for ph in ph_list
            ]
        return {
            "success": True,
            "page_count": tpl.page_count,
            "text_fields": text_fields,
            "image_placeholders": image_placeholders,
        }
    except Exception as e:
        logger.error("Failed to get template layout: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head>
            <title>Fire Safety Technical Report Generator</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f7f9fc; color: #333; }
                h1 { color: #d9383a; }
                .loader { border: 4px solid #f3f3f3; border-top: 4px solid #d9383a; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
        </head>
        <body>
            <h1>Fire Safety Technical Report Generator</h1>
            <div class="loader"></div>
            <p>Initializing premium user interface. Please refresh in a moment...</p>
        </body>
    </html>
    """


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json")
async def manifest():
    return JSONResponse(content={
        "name": "Report Agent",
        "short_name": "ReportAgent",
        "start_url": "/ui/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "icons": [],
    })


@app.get("/api/templates")
async def list_templates():
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith(".pdf"):
                templates.append(f)
    return {"templates": templates}


@app.post("/api/extract")
async def extract(
    files: list[UploadFile] = File(...),
    user_context: str = Form(""),
):
    if not files:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "No files provided"},
        )

    extractions = []
    errors = []

    for upload in files:
        try:
            file_data = await upload.read()
            filename = upload.filename or "document.pdf"

            result = orchestrator.extract_document(file_data, filename)

            if result["success"]:
                extractions.append(result)
            else:
                errors.append({
                    "document": filename,
                    "error": result.get("error", "Unknown error"),
                })
        except Exception as e:
            logger.error("Failed to process %s: %s", upload.filename, e)
            errors.append({
                "document": upload.filename,
                "error": str(e),
            })

    if not extractions:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "No documents could be processed",
                "details": errors,
            },
        )

    merged = merger.merge(extractions)

    methods_used = list(set(e.get("extraction_method", "unknown") for e in extractions))

    return {
        "success": True,
        "extractedFields": merged["fields"],
        "conflicts": merged.get("conflicts", []),
        "sources": merged.get("sources", {}),
        "documentCount": len(extractions),
        "extractionMethods": methods_used,
        "errors": errors if errors else None,
    }


@app.post("/api/generate-report")
async def generate_report(
    extracted_fields: str = Form(...),
    template_name: str = Form(DEFAULT_TEMPLATE),
    output_filename: str = Form("report.pdf"),
    images: list[UploadFile] = File(default=[]),
    image_categories: str = Form("{}"),
):
    import json

    try:
        fields = json.loads(extracted_fields)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid extracted_fields JSON"},
        )

    try:
        categories = json.loads(image_categories)
    except json.JSONDecodeError:
        categories = {}

    image_sections: dict[str, list[tuple[str, bytes]]] = {}
    for img in images:
        data = await img.read()
        filename = img.filename or "image.jpg"
        cat = categories.get(filename, "outro")
        if cat not in image_sections:
            image_sections[cat] = []
        image_sections[cat].append((filename, data))

    output_path = os.path.join(
        tempfile.gettempdir(), "report-agent", "technical_report.pdf"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        from .services.preview_renderer import PreviewRenderer
        preview_renderer = PreviewRenderer(template_name)
        output_path = preview_renderer.get_final_report_path(fields, image_sections)
        num_pages = fitz.open(output_path).page_count
    except Exception as e:
        logger.error("Report generation failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Generation failed: {e}"},
        )

    if os.path.exists(output_path):
        return JSONResponse(
            content={
                "success": True,
                "output_path": output_path,
                "num_pages": num_pages,
                "download_url": f"/download-report?path={output_path}",
            }
        )

    return JSONResponse(
        status_code=500,
        content={"error": "Report file not found after generation"},
    )


@app.post("/api/render-preview")
async def render_preview(
    extracted_fields: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    image_categories: str = Form("{}"),
    max_pages: int = Form(3),
):
    import json

    try:
        fields = json.loads(extracted_fields)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid extracted_fields JSON"},
        )

    try:
        categories = json.loads(image_categories)
    except json.JSONDecodeError:
        categories = {}

    image_sections: dict[str, list[dict]] = {}
    for img in images:
        data = await img.read()
        filename = img.filename or "image.jpg"
        cat = categories.get(filename, "outro")
        image_sections.setdefault(cat, []).append({
            "filename": filename,
            "data": data,
        })

    try:
        from .services.preview_renderer import PreviewRenderer
        renderer = PreviewRenderer()
        preview_paths = renderer.render_preview_pages(fields, image_sections, max_pages=max_pages)
        preview_urls = [f"/preview-image?path={p}" for p in preview_paths]
        return JSONResponse(content={"success": True, "preview_urls": preview_urls})
    except Exception as e:
        logger.error("Preview rendering failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@app.get("/preview-image")
async def serve_preview_image(path: str):
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "Preview not found"})
    return FileResponse(path, media_type="image/png")


@app.get("/download-report")
async def download_report(path: str, filename: str = "technical_report.pdf"):
    if not os.path.exists(path):
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return FileResponse(path, media_type="application/pdf", filename=filename)


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

FIELD_LABELS = [
    ("company_name", "Empresa / Company"),
    ("client_name", "Proprietario / Cliente"),
    ("cnpj", "CNPJ"),
    ("address", "Endereco"),
    ("classification", "Classificacao"),
    ("floors", "No de Pavimentos"),
    ("building_area", "Area Total"),
    ("process_number", "Processo"),
    ("report_number", "No do LE"),
    ("engineer", "Engenheiro"),
    ("crea", "CREA"),
    ("approved_systems", "Sistemas Aprovados"),
    ("specific_risks", "Riscos Especificos"),
    ("observations", "Observacoes"),
    ("fabricante", "Fabricante das Bombas"),
    ("serie", "Serie das Bombas"),
    ("modelo", "Modelo das Bombas"),
    ("vazao_nominal", "Vazao Nominal"),
    ("pressao_nominal", "Pressao Nominal"),
    ("rpm", "RPM"),
    ("diametro_rotor", "Diametro do Rotor"),
    ("potencia_cv", "Potencia (CV)"),
]

REPORT_SECTIONS = [
    ("Extintores", "extintor"),
    ("Hidrante de Recalque", "hidrante_recalque"),
    ("Hidrante Urbano", "hidrante_urbano"),
    ("Caixas de Mangueira", "hidrante_caixa"),
    ("Casa de Maquinas", "cmi"),
    ("Placa de Identificacao das Bombas", "bomba_placa"),
    ("Alarme de Incendio", "alarme"),
    ("Iluminacao de Emergencia", "iluminacao_emergencia"),
    ("Sprinklers", "sprinkler"),
    ("Sinalizacao", "sinalizacao"),
    ("Saidas de Emergencia", "saida_emergencia"),
    ("Riscos Especificos", "risco_especifico"),
    ("Visao Geral", "visao_geral"),
    ("Fotos de Inspecao Geral", "fotos_gerais"),
]


def on_pdf_upload(pdf_files):
    if not pdf_files:
        return [gr.update(visible=False)] * len(FIELD_LABELS) + ["No files selected."]

    if not isinstance(pdf_files, list):
        pdf_files = [pdf_files]

    extractions = []
    errors = []

    for pdf_file in pdf_files:
        file_path = pdf_file if isinstance(pdf_file, str) else (
            pdf_file.name if hasattr(pdf_file, "name") else str(pdf_file)
        )
        if not file_path or not os.path.exists(file_path):
            continue

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            filename = os.path.basename(file_path)
            result = orchestrator.extract_document(file_data, filename)
            if result["success"]:
                extractions.append(result)
            else:
                errors.append(f"{filename}: {result.get('error', 'failed')}")
        except Exception as e:
            errors.append(f"{file_path}: {e}")

    if not extractions:
        msg = "Extraction failed for all documents."
        if errors:
            msg += " " + "; ".join(errors)
        return [gr.update(visible=False)] * len(FIELD_LABELS) + [msg]

    merged = merger.merge(extractions)
    methods = list(set(e.get("extraction_method", "unknown") for e in extractions))
    n_fields = len([v for v in merged["fields"].values() if v])
    conflicts = merged.get("conflicts", [])

    updates = []
    for key, _ in FIELD_LABELS:
        val = merged["fields"].get(key, "")
        updates.append(gr.update(value=val, visible=True))

    status = f"Extracted {n_fields} fields from {len(extractions)} doc(s). Methods: {', '.join(methods)}."
    if conflicts:
        status += f" {len(conflicts)} conflict(s)."
    if errors:
        status += " Errors: " + "; ".join(errors)

    return updates + [status]


def handle_generate(pdf_files, *args):
    n_fields = len(FIELD_LABELS)
    field_values = args[:n_fields]
    file_values = args[n_fields:]

    if not pdf_files:
        return "Error: Upload PDF(s) first.", None

    fields = {}
    for i, (key, _) in enumerate(FIELD_LABELS):
        val = field_values[i] if i < len(field_values) else ""
        if val and str(val).strip():
            fields[key] = str(val).strip()

    image_sections = {}
    total_images = 0
    for idx, (_, key) in enumerate(REPORT_SECTIONS):
        files = file_values[idx] if idx < len(file_values) else None
        if not files:
            continue
        images = []
        for f in files:
            path = f if isinstance(f, str) else (f.get("path") if isinstance(f, dict) else str(f))
            if not path or not os.path.exists(path):
                continue
            fname = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            images.append((fname, data))
            total_images += 1
        if images:
            image_sections[key] = images

    output_path = os.path.join(UPLOAD_DIR, "technical_report.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        from .services.report_generator import ReportGenerator
        generator = ReportGenerator(template_name=DEFAULT_TEMPLATE)
        result = generator.generate(
            output_path=output_path,
            fields=fields,
            image_sections=image_sections,
        )
    except Exception as e:
        logger.error("Report generation failed: %s", e, exc_info=True)
        return f"Error: {e}", None

    if os.path.exists(output_path):
        return (
            f"Report generated - {result['num_pages']} pages, "
            f"{result.get('fields_filled', 0)} fields, "
            f"{total_images} images.",
            output_path,
        )
    return "Error: Report file not found.", None


CSS = """
.generate-btn { min-height: 60px !important; font-size: 18px !important; }
footer { display: none !important; }
"""


def build_gradio_ui() -> gr.Blocks:
    with gr.Blocks(title="Fire Safety Technical Report Generator") as ui:
        gr.Markdown(
            "# Fire Safety Technical Report Generator\n"
            "*Upload LE documents, review extracted data, assign photographs, generate report.*"
        )

        with gr.Row():
            with gr.Column(scale=4):
                gr.Markdown("### Documents")
                pdf_upload = gr.File(
                    label="Select LE PDFs (one or more)",
                    file_types=[".pdf"],
                    type="filepath",
                    file_count="multiple",
                )
                status_box = gr.Textbox(
                    label="Status", interactive=False, visible=True,
                    value="Upload PDF(s) to begin.",
                )

                textbox_list = []
                for key, label in FIELD_LABELS:
                    tb = gr.Textbox(
                        label=label, interactive=True, lines=1,
                        visible=False, elem_id=f"field_{key}",
                    )
                    textbox_list.append(tb)

                pdf_upload.change(
                    fn=on_pdf_upload,
                    inputs=[pdf_upload],
                    outputs=[*textbox_list, status_box],
                )

            with gr.Column(scale=6):
                gr.Markdown("### Photographs")
                gr.Markdown("*Upload images to each section.*")

                file_list = []
                for label, key in REPORT_SECTIONS:
                    with gr.Accordion(label, open=False):
                        f = gr.File(
                            label="Add images",
                            file_count="multiple",
                            file_types=[".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"],
                        )
                        g = gr.Gallery(
                            label="Preview", columns=4,
                            height=140, object_fit="contain",
                        )
                        file_list.append(f)
                        f.change(
                            fn=lambda files: files if files else [],
                            inputs=[f],
                            outputs=[g],
                        )

        gr.Markdown("---")

        generate_btn = gr.Button(
            "Generate Technical Report",
            variant="primary",
            size="lg",
            elem_classes=["generate-btn"],
        )
        gen_status = gr.Textbox(label="Generation Status", interactive=False)
        preview_gallery = gr.Gallery(label="Report Preview", visible=False, columns=1, height=720)
        preview_actions = gr.Row(visible=False)
        with preview_actions:
            approve_btn = gr.Button("Approve & Download", variant="primary")
            regenerate_btn = gr.Button("Regenerate", variant="secondary")
        gen_output = gr.File(label="Download Report", visible=False)

        state = gr.State({"approved": False, "preview_urls": [], "path": ""})

        def generate_with_preview(*inputs):
            status, out_path = handle_generate(*inputs)
            if not out_path or not isinstance(out_path, str) or not os.path.exists(out_path):
                return (
                    status,
                    gr.update(value=None, visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    {"approved": False, "preview_urls": [], "path": ""},
                )
            from urllib.parse import quote
            download_url = f"/download-report?path={quote(out_path)}&filename=technical_report.pdf"
            doc = fitz.open(out_path)
            pages = []
            preview_dir = os.path.join(tempfile.gettempdir(), "report-agent", "previews")
            os.makedirs(preview_dir, exist_ok=True)
            for i in range(len(doc)):
                pix = doc[i].get_pixmap(dpi=150)
                path = os.path.join(preview_dir, f"preview_{i}.png")
                pix.save(path)
                pages.append(path)
            doc.close()
            return (
                status,
                gr.update(value=pages, visible=True),
                gr.update(visible=True),
                download_url,
                {"approved": False, "preview_urls": pages, "path": out_path},
            )

        def approve_download(state):
            path = state.get("path", "") if isinstance(state, dict) else ""
            if not path or not os.path.exists(path):
                return (
                    "Report not found. Please generate again.",
                    gr.update(value=None, visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    {"approved": False, "preview_urls": [], "path": ""},
                )
            return (
                "Report approved. Use the file component below to download.",
                gr.update(value=None, visible=False),
                gr.update(visible=False),
                path,
                {"approved": True, "preview_urls": [], "path": path},
            )

        all_inputs = [pdf_upload] + textbox_list + file_list

        generate_btn.click(
            fn=generate_with_preview,
            inputs=all_inputs,
            outputs=[gen_status, preview_gallery, preview_actions, gen_output, state],
        )
        approve_btn.click(
            fn=approve_download,
            inputs=[state],
            outputs=[gen_status, preview_gallery, preview_actions, gen_output, state],
        )

    return ui


# Mount Gradio at /ui
gradio_app = build_gradio_ui()
gr.mount_gradio_app(
    app, gradio_app, path="/ui",
    css=CSS, pwa=False,
)


def create_api_app() -> FastAPI:
    return app


def main():
    import uvicorn
    # Managed container platforms (including Cloud Run) inject the port via
    # this environment variable. Keep 8766 as the local-development default.
    port = int(os.getenv("PORT", "8766"))
    uvicorn.run(
        "report_agent.api_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
