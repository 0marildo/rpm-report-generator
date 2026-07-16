import SwiftUI
import UniformTypeIdentifiers

struct ExtractView: View {
    @ObservedObject var viewModel: ReportViewModel
    @State private var showFilePicker = false

    var body: some View {
        List {
            Section("Upload PDFs") {
                Button("Select PDF Files") { showFilePicker = true }
                    .disabled(viewModel.isLoading)

                if !viewModel.pdfData.isEmpty {
                    Text("\(viewModel.pdfData.count) PDF(s) selected")
                        .foregroundColor(.secondary)
                }

                if viewModel.isLoading {
                    HStack {
                        ProgressView()
                        Text("Extracting...")
                    }
                }
            }

            if !viewModel.extractedFields.isEmpty {
                Section("Extracted Fields (\(viewModel.extractedFields.count))") {
                    ForEach(Array(viewModel.extractedFields.sorted(by: { $0.key < $1.key })), id: \.key) { key, value in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(key)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(value)
                                .font(.body)
                        }
                    }
                }
            }

            if viewModel.extractionSuccess {
                Section {
                    NavigationLink("Next — Categorize Photos") {
                        ImagesView(viewModel: viewModel)
                    }
                }
            }
        }
        .navigationTitle("Extract")
        .fileImporter(
            isPresented: $showFilePicker,
            allowedContentTypes: [UTType.pdf],
            allowsMultipleSelection: true
        ) { result in
            switch result {
            case .success(let urls):
                let datas = urls.compactMap { try? Data(contentsOf: $0) }
                Task { await viewModel.extract(pdfDataList: datas) }
            case .failure(let error):
                viewModel.error = "File picker error: \(error.localizedDescription)"
            }
        }
    }
}
