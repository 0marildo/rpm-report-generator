"""Main Gradio application."""

import logging
import os
import tempfile

import gradio as gr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FIELD_LABELS = [
    ("company_name", "Empresa / Company"),
    ("client_name", "Proprietário / Cliente"),
    ("cnpj", "CNPJ"),
    ("address", "Endereço"),
    ("classification", "Classificação"),
    ("floors", "Nº de Pavimentos"),
    ("building_area", "Área Total"),
    ("process_number", "Processo"),
    ("report_number", "Nº do LE"),
    ("engineer", "Engenheiro"),
    ("crea", "CREA"),
    ("approved_systems", "Sistemas Aprovados"),
    ("specific_risks", "Riscos Específicos"),
    ("observations", "Observações"),
    ("fabricante", "Fabricante das Bombas"),
    ("serie", "Série das Bombas"),
    ("modelo", "Modelo das Bombas"),
    ("vazao_nominal", "Vazão Nominal"),
    ("pressao_nominal", "Pressão Nominal"),
    ("rpm", "RPM"),
    ("diametro_rotor", "Diâmetro do Rotor"),
    ("potencia_cv", "Potência (CV)"),
]

REPORT_SECTIONS = [
    ("Extintores", "extintor"),
    ("Hidrante de Recalque", "hidrante_recalque"),
    ("Hidrante Urbano", "hidrante_urbano"),
    ("Caixas de Mangueira", "hidrante_caixa"),
    ("Casa de Máquinas", "cmi"),
    ("Placa de Identificação das Bombas", "bomba_placa"),
    ("Alarme de Incêndio", "alarme"),
    ("Iluminação de Emergência", "iluminacao_emergencia"),
    ("Sprinklers", "sprinkler"),
    ("Sinalização", "sinalizacao"),
    ("Saídas de Emergência", "saida_emergencia"),
    ("Riscos Específicos", "risco_especifico"),
    ("Visão Geral", "visao_geral"),
    ("Fotos de Inspeção Geral", "fotos_gerais"),
]


def on_pdf_upload(pdf_files):
    if not pdf_files:
        return [gr.update(visible=False)] * len(FIELD_LABELS) + ["No files selected."]

    if not isinstance(pdf_files, list):
        pdf_files = [pdf_files]

    try:
        from ..pipeline.orchestrator import ExtractionOrchestrator
        from ..pipeline.document_merger import DocumentMerger

        orchestrator = ExtractionOrchestrator()
        merger = DocumentMerger()

        extractions = []
        for pdf_file in pdf_files:
            file_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
            if not file_path or not os.path.exists(file_path):
                continue

            with open(file_path, "rb") as f:
                file_data = f.read()

            filename = os.path.basename(file_path)
            result = orchestrator.extract_document(file_data, filename)

            if result["success"]:
                extractions.append(result)

        if not extractions:
            return [gr.update(visible=False)] * len(FIELD_LABELS) + ["Extraction failed for all documents."]

        merged = merger.merge(extractions)

        methods = list(set(e.get("extraction_method", "unknown") for e in extractions))
        n_fields = len([v for v in merged["fields"].values() if v])
        conflicts = merged.get("conflicts", [])

        updates = []
        for key, _ in FIELD_LABELS:
            val = merged["fields"].get(key, "")
            updates.append(gr.update(value=val, visible=True))

        status = f"Extracted {n_fields} fields from {len(extractions)} document(s). Methods: {', '.join(methods)}."
        if conflicts:
            status += f" {len(conflicts)} field conflict(s) detected."

        return updates + [status]

    except Exception as e:
        logger.error("Extraction failed: %s", e, exc_info=True)
        return [gr.update(visible=False)] * len(FIELD_LABELS) + [f"Extraction failed: {e}"]


def handle_generate_with_images(pdf_files, *args):
    n_fields = len(FIELD_LABELS)
    field_values = args[:n_fields]
    file_values = args[n_fields:]

    if not pdf_files:
        return "Error: Please upload PDF(s) first.", None

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

    output_path = os.path.join(tempfile.gettempdir(), "report-agent", "technical_report.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        from ..services.report_generator import ReportGenerator
        generator = ReportGenerator()
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
            f"Report generated — {result['num_pages']} pages, "
            f"{result.get('fields_filled', 0)} fields, "
            f"{total_images} images in {len(image_sections)} sections.",
            output_path,
        )
    return "Error: Report file not found.", None


CSS = """
.generate-btn { min-height: 60px !important; font-size: 18px !important; }
footer { display: none !important; }
"""


def create_app() -> gr.Blocks:
    with gr.Blocks(title="Fire Safety Technical Report Generator") as app:
        gr.Markdown(
            "# Fire Safety Technical Report Generator\n"
            "*Select LE documents, review extracted data, assign photographs, then generate the report.*"
        )

        with gr.Row():
            with gr.Column(scale=4):
                gr.Markdown("### Documents")
                pdf_upload = gr.File(
                    label="Select LE PDFs",
                    file_types=[".pdf"],
                    type="filepath",
                    file_count="multiple",
                )
                status_box = gr.Textbox(label="Status", interactive=False, visible=True, value="Upload PDF(s) to begin.")

                textbox_list = []
                for key, label in FIELD_LABELS:
                    tb = gr.Textbox(label=label, interactive=True, lines=1, visible=False, elem_id=f"field_{key}")
                    textbox_list.append(tb)

                pdf_upload.change(
                    fn=on_pdf_upload,
                    inputs=[pdf_upload],
                    outputs=[*textbox_list, status_box],
                )

            with gr.Column(scale=6):
                gr.Markdown("### Photographs")
                gr.Markdown("*Upload images to each section. Order is preserved in the report.*")

                gallery_comps = {}
                file_list = []
                for label, key in REPORT_SECTIONS:
                    with gr.Accordion(label, open=False):
                        f = gr.File(
                            label="Add images",
                            file_count="multiple",
                            file_types=["image/*"],
                        )
                        g = gr.Gallery(label="Preview", columns=4, height=140, object_fit="contain")
                        gallery_comps[key] = (f, g)
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
            status, out_path = handle_generate_with_images(*inputs)
            if not out_path or not isinstance(out_path, str) or not os.path.exists(out_path):
                return (
                    status,
                    gr.update(value=None, visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    {"approved": False, "preview_urls": [], "path": ""},
                )
            from urllib.parse import quote
            download_url = f"/download-report?path={quote(out_path)}&filename=technical_report.pdf"
            import fitz
            preview_dir = os.path.join(tempfile.gettempdir(), "report-agent", "previews")
            os.makedirs(preview_dir, exist_ok=True)
            doc = fitz.open(out_path)
            pages = []
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
                gr.update(visible=True),
                download_url,
                {"approved": False, "preview_urls": pages, "path": out_path},
            )

        def approve_download(state):
            path = state.get("path", "") if isinstance(state, dict) else ""
            if not path or not os.path.exists(path):
                return (
                    gr.update(value=None, visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    {"approved": False, "preview_urls": [], "path": ""},
                    "Report not found. Please generate again.",
                )
            return (
                gr.update(value=None, visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                path,
                {"approved": True, "preview_urls": [], "path": path},
                "Report approved. Use the file component below to download.",
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
            outputs=[preview_gallery, preview_actions, gen_output, preview_actions, gen_output, state, gen_status],
        )

    return app


def main():
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7866,
        share=False,
        prevent_thread_lock=False,
    )


if __name__ == "__main__":
    main()
