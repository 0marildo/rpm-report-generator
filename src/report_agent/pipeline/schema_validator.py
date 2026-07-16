"""Validate extraction results against the unified output schema."""

import logging

logger = logging.getLogger(__name__)

UNIFIED_SCHEMA = {
    "company_name": {"type": "string", "required": False},
    "client_name": {"type": "string", "required": False},
    "cnpj": {"type": "string", "required": False},
    "address": {"type": "string", "required": False},
    "process_number": {"type": "string", "required": False},
    "report_number": {"type": "string", "required": False},
    "classification": {"type": "string", "required": False},
    "building_area": {"type": "string", "required": False},
    "floors": {"type": "string", "required": False},
    "engineer": {"type": "string", "required": False},
    "crea": {"type": "string", "required": False},
    "approved_systems": {"type": "string", "required": False},
    "specific_risks": {"type": "string", "required": False},
    "observations": {"type": "string", "required": False},
    "proprietario": {"type": "string", "required": False},
    "num_pavimentos": {"type": "string", "required": False},
    "area_total": {"type": "string", "required": False},
    "processo": {"type": "string", "required": False},
    "laudo_exigencias": {"type": "string", "required": False},
    "fabricante": {"type": "string", "required": False},
    "serie": {"type": "string", "required": False},
    "modelo": {"type": "string", "required": False},
    "vazao_nominal": {"type": "string", "required": False},
    "pressao_nominal": {"type": "string", "required": False},
    "rpm": {"type": "string", "required": False},
    "diametro_rotor": {"type": "string", "required": False},
    "potencia_cv": {"type": "string", "required": False},
}


class SchemaValidator:
    def validate(self, fields: dict[str, str]) -> dict:
        errors = []
        warnings = []
        validated_fields = {}

        for field_name, spec in UNIFIED_SCHEMA.items():
            value = fields.get(field_name, "")

            if value is None:
                value = ""

            value = str(value).strip()

            if spec["required"] and not value:
                errors.append(f"Required field missing: {field_name}")

            if value and spec["type"] == "string":
                validated_fields[field_name] = value
            elif value:
                validated_fields[field_name] = str(value)

        unknown_fields = set(fields.keys()) - set(UNIFIED_SCHEMA.keys())
        if unknown_fields:
            warnings.append(f"Unknown fields ignored: {', '.join(sorted(unknown_fields))}")

        is_valid = len(errors) == 0

        logger.info(
            "Schema validation: %s (%d fields, %d errors, %d warnings)",
            "valid" if is_valid else "invalid",
            len(validated_fields), len(errors), len(warnings),
        )

        return {
            "is_valid": is_valid,
            "fields": validated_fields,
            "errors": errors,
            "warnings": warnings,
        }

    def normalize_fields(self, fields: dict[str, str]) -> dict[str, str]:
        normalized = {}

        alias_map = {
            "razao_social": "company_name",
            "razão_social": "company_name",
            "nome_empresa": "company_name",
            "nome_cliente": "client_name",
            "logradouro": "address",
            "endereco_completo": "address",
            "endereco": "address",
            "num_processo": "process_number",
            "processo": "process_number",
            "numero_processo": "process_number",
            "num_laudo": "report_number",
            "laudo_exigencias": "report_number",
            "numero_laudo": "report_number",
            "classificacao": "classification",
            "tipo_edificacao": "classification",
            "area_construida": "building_area",
            "area_total": "building_area",
            "qtd_pavimentos": "floors",
            "num_pavimentos": "floors",
            "numero_pavimentos": "floors",
        }

        for key, value in fields.items():
            if not value or str(value).strip() == "":
                continue

            normalized_key = alias_map.get(key, key)
            normalized[normalized_key] = str(value).strip()

        return normalized
