"""Document selection panel — LE upload and editable extracted fields."""

import gradio as gr
from ..services.le_extractor import LEExtractor

FIELD_LABELS = [
    ("proprietario", "Proprietário / Cliente"),
    ("cnpj", "CNPJ"),
    ("endereco", "Endereço"),
    ("classificacao", "Classificação"),
    ("num_pavimentos", "Nº de Pavimentos"),
    ("area_total", "Área Total"),
    ("processo", "Processo"),
    ("laudo_exigencias", "Nº do LE"),
    ("fabricante", "Fabricante das Bombas"),
    ("serie", "Série das Bombas"),
    ("modelo", "Modelo das Bombas"),
    ("vazao_nominal", "Vazão Nominal"),
    ("pressao_nominal", "Pressão Nominal"),
    ("rpm", "RPM"),
    ("diametro_rotor", "Diâmetro do Rotor"),
    ("potencia_cv", "Potência (CV)"),
]


def handle_le_upload(pdf_file):
    if pdf_file is None:
        empty = {f[0]: "" for f in FIELD_LABELS}
        empty["__status"] = "No file selected."
        return [gr.update()] * len(FIELD_LABELS) + [empty, "No file selected."]

    try:
        extractor = LEExtractor()
        fields = extractor.extract(pdf_file)
    except Exception as e:
        empty = {f[0]: "" for f in FIELD_LABELS}
        empty["__status"] = f"Extraction failed: {e}"
        return [gr.update()] * len(FIELD_LABELS) + [empty, f"Extraction failed: {e}"]

    updates = []
    for key, _ in FIELD_LABELS:
        val = fields.get(key, "")
        updates.append(gr.update(value=val))

    state = {k: v for k, v in fields.items() if k in [f[0] for f in FIELD_LABELS]}
    state["__status"] = f"Extracted {len([v for v in state.values() if v])} fields."
    updates.append(state)
    updates.append(state["__status"])
    return updates


def build_document_panel() -> tuple:
    with gr.Column(scale=4):
        gr.Markdown("### Document")
        pdf_upload = gr.File(
            label="Select LE PDF",
            file_types=[".pdf"],
            type="filepath",
        )

        textboxes = {}
        textbox_components = []
        for key, label in FIELD_LABELS:
            tb = gr.Textbox(label=label, interactive=True, lines=1, visible=False)
            textboxes[key] = tb
            textbox_components.append(tb)

        status = gr.Textbox(label="Status", interactive=False, visible=False)
        extracted_state = gr.State(value={})

        def show_fields(pdf_file):
            return handle_le_upload(pdf_file)

        show_outputs = textbox_components + [extracted_state, status]

        pdf_upload.change(
            fn=show_fields,
            inputs=[pdf_upload],
            outputs=[
                *textbox_components,
                extracted_state,
                status,
            ],
        )

        def make_visible_handler(components):
            def handler(pdf_file):
                if pdf_file is not None:
                    return [gr.update(visible=True)] * len(components) + [gr.update(visible=True)]
                return [gr.update(visible=False)] * len(components) + [gr.update(visible=False)]
            return handler

        vis_handler = make_visible_handler(textbox_components)
        pdf_upload.change(
            fn=vis_handler,
            inputs=[pdf_upload],
            outputs=[*textbox_components, status],
        )

        def collect_fields(*values):
            return {FIELD_LABELS[i][0]: v for i, v in enumerate(values) if v}

        collect_btn = gr.Button("Apply Changes", size="sm", visible=False)
        final_state = gr.State(value={})

        def on_apply(*values):
            state = {FIELD_LABELS[i][0]: v for i, v in enumerate(values)}
            return state

        collect_btn.click(
            fn=on_apply,
            inputs=textbox_components,
            outputs=[final_state],
        )

    return pdf_upload, textboxes, extracted_state, textbox_components, status
