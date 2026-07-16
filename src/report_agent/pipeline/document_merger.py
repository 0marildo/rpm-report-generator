"""Merge extracted data from multiple documents into a single structured object."""

import logging

logger = logging.getLogger(__name__)

ALL_FIELDS = [
    "company_name", "client_name", "cnpj", "address",
    "process_number", "report_number", "classification",
    "building_area", "floors", "engineer", "crea",
    "approved_systems", "specific_risks", "observations",
    "proprietario", "cnpj", "endereco", "classificacao",
    "num_pavimentos", "area_total", "processo", "laudo_exigencias",
    "fabricante", "serie", "modelo", "vazao_nominal",
    "pressao_nominal", "rpm", "diametro_rotor", "potencia_cv",
]


class DocumentMerger:
    def merge(self, extractions: list[dict]) -> dict:
        if not extractions:
            return {"fields": {}, "conflicts": [], "sources": {}}

        merged: dict[str, str] = {}
        sources: dict[str, str] = {}
        conflicts: list[dict] = []

        for ext in extractions:
            fields = ext.get("fields", {})
            doc_name = ext.get("source_document", "unknown")

            for key, value in fields.items():
                if not value or str(value).strip() == "":
                    continue

                value = str(value).strip()

                if key not in merged:
                    merged[key] = value
                    sources[key] = doc_name
                elif merged[key] != value:
                    existing_source = sources.get(key, "unknown")
                    conflicts.append({
                        "field": key,
                        "values": [
                            {"value": merged[key], "source": existing_source},
                            {"value": value, "source": doc_name},
                        ],
                    })
                    merged[key] = value
                    sources[key] = doc_name

        logger.info(
            "Merged %d documents: %d fields, %d conflicts",
            len(extractions), len(merged), len(conflicts),
        )

        return {
            "fields": merged,
            "conflicts": conflicts,
            "sources": sources,
        }

    def merge_with_priority(self, extractions: list[dict]) -> dict:
        if not extractions:
            return {"fields": {}, "conflicts": [], "sources": {}}

        merged: dict[str, str] = {}
        sources: dict[str, str] = {}
        conflicts: list[dict] = []
        priority_order = [
            "report_number", "process_number", "classification",
            "proprietario", "client_name", "company_name",
            "cnpj", "endereco", "address",
            "num_pavimentos", "floors", "area_total", "building_area",
            "fabricante", "serie", "modelo",
            "vazao_nominal", "pressao_nominal", "rpm",
            "diametro_rotor", "potencia_cv",
            "engineer", "crea", "approved_systems",
            "specific_risks", "observations",
        ]

        for ext in extractions:
            fields = ext.get("fields", {})
            doc_name = ext.get("source_document", "unknown")

            for key in ALL_FIELDS:
                value = fields.get(key, "")
                if not value or str(value).strip() == "":
                    continue

                value = str(value).strip()

                if key not in merged:
                    merged[key] = value
                    sources[key] = doc_name
                elif merged[key] != value:
                    existing_source = sources.get(key, "unknown")
                    existing_priority = (
                        priority_order.index(key)
                        if key in priority_order
                        else len(priority_order)
                    )
                    conflicts.append({
                        "field": key,
                        "values": [
                            {"value": merged[key], "source": existing_source},
                            {"value": value, "source": doc_name},
                        ],
                    })
                    merged[key] = value
                    sources[key] = doc_name

        return {
            "fields": merged,
            "conflicts": conflicts,
            "sources": sources,
        }
