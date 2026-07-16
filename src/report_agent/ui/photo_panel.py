"""Photo assignment panel — one upload section per report category."""

import gradio as gr

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


def build_photo_panel() -> tuple:
    components = {}
    file_components = []

    with gr.Column(scale=6):
        gr.Markdown("### Photographs")
        gr.Markdown("*Upload images to each section. Order of upload is preserved in the report.*")

        for label, key in REPORT_SECTIONS:
            with gr.Accordion(label, open=False):
                f = gr.File(
                    label=f"Add images to {label}",
                    file_count="multiple",
                    file_types=["image/*"],
                    type="filepath",
                )
                g = gr.Gallery(label=f"Preview — {label}", columns=4, height=160, object_fit="contain")
                components[key] = (f, g)
                file_components.append(f)

                f.change(
                    fn=lambda files: files if files else [],
                    inputs=[f],
                    outputs=[g],
                )

    return components, file_components
