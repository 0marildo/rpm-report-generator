import Foundation
import UniformTypeIdentifiers

enum ApiError: LocalizedError {
    case invalidURL
    case noData
    case serverError(String)
    case decodingError

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid server URL"
        case .noData: return "No data received"
        case .serverError(let msg): return msg
        case .decodingError: return "Failed to parse response"
        }
    }
}

actor ApiService {
    private var baseURL: String
    private let session: URLSession
    private let decoder = JSONDecoder()

    init(baseURL: String = "http://localhost:8766") {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 180
        self.session = URLSession(configuration: config)
    }

    func updateBaseURL(_ url: String) {
        baseURL = url
    }

    // MARK: - Health

    func health() async throws -> HealthResponse {
        let data = try await get("/health")
        return try decoder.decode(HealthResponse.self, from: data)
    }

    // MARK: - Templates

    func templates() async throws -> TemplatesResponse {
        let data = try await get("/api/templates")
        return try decoder.decode(TemplatesResponse.self, from: data)
    }

    // MARK: - Extract

    func extract(pdfData: [Data], userContext: String = "") async throws -> ExtractResponse {
        let url = URL(string: baseURL + "/api/extract")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        for (i, data) in pdfData.enumerated() {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"doc_\(i).pdf\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: application/pdf\r\n\r\n".data(using: .utf8)!)
            body.append(data)
            body.append("\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"user_context\"\r\n\r\n".data(using: .utf8)!)
        body.append(userContext.data(using: .utf8)!)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (responseData, _) = try await session.data(for: request)
        return try decoder.decode(ExtractResponse.self, from: responseData)
    }

    // MARK: - Generate

    func generate(extractedFields: [String: String], images: [(data: Data, filename: String, category: String)], templateName: String = "template final.pdf") async throws -> Data {
        let url = URL(string: baseURL + "/api/generate-report")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fieldsJSON = try JSONSerialization.data(withJSONObject: extractedFields)
        var catMap = [String: String]()
        for img in images {
            catMap[img.filename] = img.category
        }
        let catsJSON = try JSONSerialization.data(withJSONObject: catMap)

        var body = Data()
        // extracted_fields
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"extracted_fields\"\r\n\r\n".data(using: .utf8)!)
        body.append(fieldsJSON)
        body.append("\r\n".data(using: .utf8)!)

        // template_name
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"template_name\"\r\n\r\n".data(using: .utf8)!)
        body.append(templateName.data(using: .utf8)!)
        body.append("\r\n".data(using: .utf8)!)

        // images
        for img in images {
            let mimeType = Self.detectMIMEType(data: img.data, filename: img.filename)
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"images\"; filename=\"\(img.filename)\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
            body.append(img.data)
            body.append("\r\n".data(using: .utf8)!)
        }

        // image_categories
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"image_categories\"\r\n\r\n".data(using: .utf8)!)
        body.append(catsJSON)
        body.append("\r\n".data(using: .utf8)!)

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (responseData, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ApiError.serverError("Invalid response")
        }
        guard httpResponse.statusCode == 200 else {
            let msg = String(data: responseData, encoding: .utf8) ?? "HTTP \(httpResponse.statusCode)"
            throw ApiError.serverError(msg)
        }
        return responseData
    }

    // MARK: - MIME Type Detection

    static func detectMIMEType(data: Data, filename: String) -> String {
        if data.count >= 4 {
            let header = [UInt8](data.prefix(4))
            if header.count >= 4 {
                // JPEG: FF D8 FF
                if header[0] == 0xFF && header[1] == 0xD8 && header[2] == 0xFF {
                    return "image/jpeg"
                }
                // PNG: 89 50 4E 47
                if header[0] == 0x89 && header[1] == 0x50 && header[2] == 0x4E && header[3] == 0x47 {
                    return "image/png"
                }
                // WebP: RIFF....WEBP
                if data.count >= 12 {
                    let riff = String(data: data[0..<4], encoding: .ascii) ?? ""
                    let webp = String(data: data[8..<12], encoding: .ascii) ?? ""
                    if riff == "RIFF" && webp == "WEBP" {
                        return "image/webp"
                    }
                }
                // GIF: 47 49 46 38
                if header[0] == 0x47 && header[1] == 0x49 && header[2] == 0x46 && header[3] == 0x38 {
                    return "image/gif"
                }
                // TIFF: 49 49 or 4D 4D
                if (header[0] == 0x49 && header[1] == 0x49) || (header[0] == 0x4D && header[1] == 0x4D) {
                    return "image/tiff"
                }
                // BMP: 42 4D
                if header[0] == 0x42 && header[1] == 0x4D {
                    return "image/bmp"
                }
            }
        }

        let ext = (filename as NSString).pathExtension.lowercased()
        switch ext {
        case "jpg", "jpeg": return "image/jpeg"
        case "png": return "image/png"
        case "webp": return "image/webp"
        case "gif": return "image/gif"
        case "tiff", "tif": return "image/tiff"
        case "bmp": return "image/bmp"
        default: return "image/jpeg"
        }
    }

    // MARK: - Private

    private func get(_ path: String) async throws -> Data {
        guard let url = URL(string: baseURL + path) else {
            throw ApiError.invalidURL
        }
        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw ApiError.serverError("HTTP error")
        }
        return data
    }
}
