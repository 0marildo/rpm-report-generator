import Foundation
import SwiftUI

@MainActor
class ReportViewModel: ObservableObject {
    @Published var serverURL: String = "http://localhost:8766"
    @Published var isConnected: Bool = false
    @Published var isLoading: Bool = false
    @Published var error: String?

    @Published var templates: [String] = []

    @Published var pdfData: [Data] = []
    @Published var extractedFields: [String: String] = [:]
    @Published var extractionSuccess: Bool = false

    @Published var images: [ImageItem] = []
    @Published var generationSuccess: Bool = false
    @Published var generatedPDFData: Data?
    @Published var numPages: Int = 0
    @Published var numImages: Int = 0

    private var api: ApiService?

    private func getAPI() -> ApiService {
        if let api = api { return api }
        let newAPI = ApiService(baseURL: serverURL)
        api = newAPI
        return newAPI
    }

    func connect() async {
        isLoading = true
        error = nil
        do {
            let api = getAPI()
            let health = try await api.health()
            let tmpl = try await api.templates()
            isConnected = health.status == "ok"
            templates = tmpl.templates
        } catch {
            self.error = "Connection failed: \(error.localizedDescription)"
            isConnected = false
        }
        isLoading = false
    }

    func extract(pdfDataList: [Data]) async {
        isLoading = true
        error = nil
        pdfData = pdfDataList
        do {
            let api = getAPI()
            let response = try await api.extract(pdfData: pdfDataList)
            extractedFields = response.extractedFields
            extractionSuccess = response.success
            if !response.success {
                error = response.error ?? "Extraction failed"
            }
        } catch {
            self.error = "Extraction failed: \(error.localizedDescription)"
        }
        isLoading = false
    }

    func addImage(data: Data, filename: String) {
        images.append(ImageItem(data: data, filename: filename, category: "outro"))
    }

    func updateImageCategory(id: UUID, category: String) {
        if let index = images.firstIndex(where: { $0.id == id }) {
            images[index].category = category
        }
    }

    func removeImage(id: UUID) {
        images.removeAll(where: { $0.id == id })
    }

    func generate() async {
        isLoading = true
        error = nil
        generationSuccess = false
        do {
            let api = getAPI()
            let imgTuples = images.map { (data: $0.data, filename: $0.filename, category: $0.category) }
            let pdfData = try await api.generate(
                extractedFields: extractedFields,
                images: imgTuples
            )
            generatedPDFData = pdfData
            generationSuccess = true
            numImages = images.count
        } catch {
            self.error = "Generation failed: \(error.localizedDescription)"
        }
        isLoading = false
    }

    func reset() {
        isConnected = false
        templates = []
        pdfData = []
        extractedFields = [:]
        extractionSuccess = false
        images = []
        generationSuccess = false
        generatedPDFData = nil
        error = nil
        api = nil
    }
}
