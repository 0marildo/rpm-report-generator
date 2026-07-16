import SwiftUI

struct GenerateView: View {
    @ObservedObject var viewModel: ReportViewModel

    var body: some View {
        List {
            if viewModel.isLoading {
                Section {
                    HStack {
                        ProgressView()
                        Text("Generating report...")
                    }
                }
            }

            if viewModel.generationSuccess {
                Section {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Report generated!", systemImage: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .font(.headline)

                        HStack {
                            Text("Pages:")
                            Text("\(viewModel.numPages)")
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            Text("Images placed:")
                            Text("\(viewModel.numImages)")
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            Text("Fields filled:")
                            Text("\(viewModel.extractedFields.count)")
                                .foregroundColor(.secondary)
                        }

                        if let data = viewModel.generatedPDFData {
                            ShareLink(
                                item: TransferablePDF(data: data),
                                preview: SharePreview("Report.pdf")
                            ) {
                                Label("Share PDF", systemImage: "square.and.arrow.up")
                            }
                        }
                    }
                }
            }

            Section {
                Button("Start Over") {
                    viewModel.reset()
                }
                .foregroundColor(.blue)
            }
        }
        .navigationTitle("Generate")
    }
}

struct TransferablePDF: Transferable {
    let data: Data

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .pdf) { pdf in
            pdf.data
        }
    }
}
