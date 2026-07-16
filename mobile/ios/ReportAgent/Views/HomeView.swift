import SwiftUI

struct HomeView: View {
    @ObservedObject var viewModel: ReportViewModel

    var body: some View {
        NavigationStack {
            List {
                Section("Server") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("Server URL", text: $viewModel.serverURL)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                            .font(.body.monospaced())
                        Button("Connect") {
                            Task { await viewModel.connect() }
                        }
                        .disabled(viewModel.isLoading)
                    }

                    if viewModel.isLoading {
                        HStack {
                            ProgressView()
                            Text("Connecting...")
                                .foregroundColor(.secondary)
                        }
                    }

                    HStack {
                        Circle()
                            .fill(viewModel.isConnected ? Color.green : Color.red)
                            .frame(width: 10, height: 10)
                        Text(viewModel.isConnected ? "Connected" : "Disconnected")
                            .foregroundColor(.secondary)
                    }
                }

                if !viewModel.templates.isEmpty {
                    Section("Templates") {
                        ForEach(viewModel.templates, id: \.self) { tmpl in
                            Label(tmpl, systemImage: "doc.text")
                        }
                    }
                }

                Section("Steps") {
                    ForEach(stepDescriptions, id: \.self) { step in
                        Label(step, systemImage: "\(stepDescriptions.firstIndex(of: step)! + 1).circle")
                    }
                }

                if viewModel.isConnected {
                    Section {
                        NavigationLink("Start — Extract PDFs") {
                            ExtractView(viewModel: viewModel)
                        }
                    }
                }
            }
            .navigationTitle("Report Agent")
        }
    }
}
