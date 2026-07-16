import Foundation

// MARK: - API Models

struct HealthResponse: Codable {
    let status: String
}

struct TemplatesResponse: Codable {
    let templates: [String]
}

struct ExtractResponse: Codable {
    let success: Bool
    let extractedFields: [String: String]
    let error: String?
}

struct GenerateResponse: Codable {
    let outputPath: String
    let numPages: Int
    let numImages: Int
    let fieldsFilled: Int
}

// MARK: - App Models

struct ImageItem: Identifiable {
    let id = UUID()
    let data: Data
    let filename: String
    var category: String
}

struct ExtractedField: Identifiable {
    let id = UUID()
    let key: String
    let value: String
}

let categoryOptions = [
    "extintor", "hidrante_recalque", "hidrante_urbano", "hidrante_caixa",
    "cmi", "bomba", "alarme", "sinalizacao", "sprinkler",
    "iluminacao_emergencia", "saida_emergencia", "risco_especifico",
    "fachada", "le_print", "pressurizacao", "outro",
]

let stepDescriptions = [
    "1. Upload PDFs — Extract inspection data from report PDFs",
    "2. Add Photos — Upload images and assign categories",
    "3. Generate Report — Create the final PDF with placed images",
]
