"""Template-driven Multi-pass Extractor using Gemini."""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_FIELDS = {
    "company_name": "Razão social da empresa responsável pela edificação (se disponível).",
    "client_name": "Nome do proprietário ou responsável técnico do imóvel.",
    "cnpj": "CNPJ da empresa ou CPF do proprietário no formato padrão.",
    "address": "Endereço completo da edificação (logradouro, número, bairro, cidade, UF).",
    "process_number": "Número do processo no CBMERJ (ex: E-27/... ou E27/...).",
    "report_number": "Número do Laudo de Exigências (ex: LE-XXXXX/XX).",
    "classification": "Classificação da edificação de acordo com o COSCIP / Decreto Estadual (ex: A-1, F-3, E-1).",
    "building_area": "Área total construída em metros quadrados (m²).",
    "floors": "Número de pavimentos da edificação.",
    "engineer": "Nome do engenheiro civil ou profissional técnico que assina o laudo.",
    "crea": "Número de registro no CREA do engenheiro responsável.",
    "approved_systems": "Sistemas de segurança contra incêndio e pânico aprovados (ex: extintores, hidrantes, sinalização, alarmes).",
    "specific_risks": "Riscos específicos listados no laudo (ex: gerador, gás canalizado, subestação elétrica, pressurização de escadas).",
    "observations": "Observações gerais adicionais contidas no laudo de exigências.",
    "fabricante": "Fabricante da bomba de incêndio principal/jockey.",
    "serie": "Número de série da bomba de incêndio.",
    "modelo": "Modelo da bomba de incêndio.",
    "vazao_nominal": "Vazão nominal da bomba de incêndio (ex: em m³/h, L/min, gpm).",
    "pressao_nominal": "Pressão nominal da bomba de incêndio (ex: em mca, bar, psi).",
    "rpm": "RPM (Rotações por Minuto) de regime da bomba.",
    "diametro_rotor": "Diâmetro do rotor da bomba de incêndio (ex: em mm ou polegadas).",
    "potencia_cv": "Potência do motor da bomba em CV (Cavalos-Vapor) ou HP."
}

class MultiPassExtractor:
    def __init__(self, gemini=None):
        self.gemini = gemini

    def _get_gemini(self):
        if self.gemini is None:
            from ..core.gemini_client import GeminiClient
            self.gemini = GeminiClient()
        return self.gemini

    def extract(self, pdf_path: str, raw_text: Optional[str] = None) -> dict[str, str]:
        gemini = self._get_gemini()
        is_scanned = raw_text is None or len(raw_text.strip()) < 100
        
        context_desc = "OCR do PDF Digital" if not is_scanned else "Multimodal Visão do PDF"
        logger.info("Iniciando extração multi-passo (%s) de %s", context_desc, pdf_path)

        # ----------------------------------------------------
        # PASS 1: EXTRAÇÃO INICIAL
        # ----------------------------------------------------
        logger.info("Passo 1: Extração inicial de campos estruturados")
        schema_desc = json.dumps(SCHEMA_FIELDS, indent=2, ensure_ascii=False)
        
        prompt_p1 = f"""Você é um engenheiro especialista em segurança contra incêndio e pânico e analista de documentos do CBMERJ.
Sua missão é ler o documento fornecido e preencher os seguintes campos necessários para o relatório técnico final:

Campos requeridos e suas descrições:
{schema_desc}

Retorne um objeto JSON contendo todas as chaves acima. Preencha com null ou string vazia se o campo correspondente não for encontrado.
Não resuma nem ignore campos. Retorne APENAS um JSON válido."""

        if is_scanned:
            raw_p1 = gemini.generate_with_pdf(
                prompt=prompt_p1,
                pdf_path=pdf_path,
                system_instruction="Analista de PDF multimodal especializado. Extraia informações textuais e visuais com precisão absoluta. Retorne APENAS JSON."
            )
        else:
            raw_p1 = gemini.generate(
                prompt=f"{prompt_p1}\n\nDocumento (Texto):\n{raw_text}",
                system_instruction="Analista de texto estruturado. Extraia dados do texto do Laudo de Exigências com precisão absoluta. Retorne APENAS JSON."
            )

        fields = self._parse_json(raw_p1)
        
        # Clean nulls
        fields = {k: str(v).strip() for k, v in fields.items() if v is not None and str(v).strip() != ""}

        # ----------------------------------------------------
        # PASS 2 & 3: ANÁLISE DE CAMPOS AUSENTES E BUSCA DIRECIONADA
        # ----------------------------------------------------
        missing_keys = [k for k in SCHEMA_FIELDS.keys() if not fields.get(k)]
        
        if missing_keys:
            logger.info("Passo 2 e 3: Identificados %d campos ausentes. Iniciando busca direcionada.", len(missing_keys))
            missing_schema = {k: SCHEMA_FIELDS[k] for k in missing_keys}
            missing_schema_desc = json.dumps(missing_schema, indent=2, ensure_ascii=False)
            
            prompt_p3 = f"""Temos os seguintes dados já extraídos:
{json.dumps(fields, indent=2, ensure_ascii=False)}

Entretanto, precisamos obrigatoriamente preencher os seguintes campos que estão faltando:
{missing_schema_desc}

Por favor, faça uma busca detalhada e profunda em todo o documento para localizar essas informações faltantes. Correlacione dados de diferentes seções ou tabelas se necessário (por exemplo, informações sobre bombas costumam ficar em tabelas de testes na casa de máquinas).
Retorne um objeto JSON contendo apenas os campos que você conseguir encontrar agora com seus respectivos valores. Retorne null para os que continuam ausentes. Retorne APENAS JSON válido."""

            if is_scanned:
                raw_p3 = gemini.generate_with_pdf(
                    prompt=prompt_p3,
                    pdf_path=pdf_path,
                    system_instruction="Analista focado em recuperação de dados perdidos em PDFs. Faça busca minuciosa nos detalhes visuais e tabelas."
                )
            else:
                raw_p3 = gemini.generate(
                    prompt=f"{prompt_p3}\n\nDocumento (Texto):\n{raw_text}",
                    system_instruction="Analista focado em recuperação de dados perdidos. Faça busca minuciosa no texto do Laudo."
                )

            extra_fields = self._parse_json(raw_p3)
            for k, v in extra_fields.items():
                if v is not None and str(v).strip() != "" and k in missing_keys:
                    fields[k] = str(v).strip()
                    logger.info("Campo ausente recuperado no Passo 3: %s = %s", k, v)
        else:
            logger.info("Nenhum campo ausente identificado para o Passo 3.")

        # ----------------------------------------------------
        # PASS 4: CONSISTÊNCIA, VALIDAÇÃO E FORMATAÇÃO
        # ----------------------------------------------------
        logger.info("Passo 4: Validação de consistência e formatação de dados")
        prompt_p4 = f"""Você é o validador de dados finais do relatório técnico.
Aqui estão os campos que extraímos até agora:
{json.dumps(fields, indent=2, ensure_ascii=False)}

Por favor, faça uma revisão de qualidade e consistência nesses dados para garantir que estão prontos para publicação:
1. CNPJ/CPF: Garanta a formatação padrão XX.XXX.XXX/XXXX-XX ou CPF equivalente.
2. Área total: Garanta a unidade em m² (ex: "1.250 m²").
3. Número de pavimentos: Deve conter apenas o número de pavimentos (ex: "3" ou "Térreo + 2").
4. Processo / Laudo de Exigências: Remova ruídos ou formatações inconsistentes.
5. Bombas de incêndio: Certifique-se de que os valores numéricos de vazão, pressão, rotor e potência têm suas respectivas unidades se mencionadas no texto.

Retorne o JSON final formatado contendo todos os 22 campos da especificação inicial (use string vazia se o campo não existir de fato no documento). Retorne APENAS o JSON válido."""

        raw_p4 = gemini.generate(
            prompt=prompt_p4,
            system_instruction="Revisor final de dados estruturados. Formate e limpe os campos com precisão profissional. Retorne APENAS JSON válido."
        )
        
        final_fields = self._parse_json(raw_p4)
        
        # Fallback to fields if final parsing fails
        if not final_fields:
            final_fields = fields

        # Final sanitization
        cleaned_final = {}
        for k in SCHEMA_FIELDS.keys():
            val = final_fields.get(k) or fields.get(k) or ""
            cleaned_final[k] = str(val).strip()

        logger.info("Extração multi-passo concluída com sucesso! Total de campos preenchidos: %d", 
                    len([v for v in cleaned_final.values() if v]))
        return cleaned_final

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
        logger.warning("Erro ao decodificar JSON do Gemini: %.200s", text)
        return {}
