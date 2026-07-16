from pydantic import BaseModel, Field


class ReportData(BaseModel):
    company_name: str = ""
    client_name: str = ""
    cnpj: str = ""
    address: str = ""
    process_number: str = ""
    report_number: str = ""
    classification: str = ""
    building_area: str = ""
    floors: str = ""
    engineer: str = ""
    crea: str = ""
    approved_systems: str = ""
    specific_risks: str = ""
    observations: str = ""
    proprietario: str = ""
    num_pavimentos: str = ""
    area_total: str = ""
    processo: str = ""
    laudo_exigencias: str = ""
    fabricante: str = ""
    serie: str = ""
    modelo: str = ""
    vazao_nominal: str = ""
    pressao_nominal: str = ""
    rpm: str = ""
    diametro_rotor: str = ""
    potencia_cv: str = ""


class ExtractionResult(BaseModel):
    success: bool
    fields: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class DocumentExtractionResult(BaseModel):
    success: bool
    fields: dict[str, str] = Field(default_factory=dict)
    source_document: str = ""
    extraction_method: str = ""
    confidence: dict = Field(default_factory=dict)
    classification: dict = Field(default_factory=dict)
    error: str | None = None


class ConflictItem(BaseModel):
    field: str
    values: list[dict] = Field(default_factory=list)


class MergedExtractionResult(BaseModel):
    success: bool
    fields: dict[str, str] = Field(default_factory=dict)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    sources: dict[str, str] = Field(default_factory=dict)
    document_count: int = 0
    extraction_methods: list[str] = Field(default_factory=list)
    error: str | None = None


class GenerationResult(BaseModel):
    success: bool
    output_path: str = ""
    num_pages: int = 0
    num_images: int = 0
    error: str | None = None
