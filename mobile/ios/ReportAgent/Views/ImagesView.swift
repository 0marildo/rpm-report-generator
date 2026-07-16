import SwiftUI
import UniformTypeIdentifiers
import PhotosUI

struct ImagesView: View {
    @ObservedObject var viewModel: ReportViewModel
    @State private var showPhotoPicker = false

    var body: some View {
        List {
            Section("Add Photos") {
                Button("Select Photos") { showPhotoPicker = true }
                    .disabled(viewModel.isLoading)

                if viewModel.isLoading {
                    HStack {
                        ProgressView()
                        Text("Generating report...")
                    }
                }
            }

            if viewModel.images.isEmpty {
                Section {
                    Text("No images added yet. Tap 'Select Photos' to add images from your library.")
                        .foregroundColor(.secondary)
                }
            } else {
                Section("Images (\(viewModel.images.count))") {
                    ForEach(viewModel.images) { item in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                if let uiImage = UIImage(data: item.data) {
                                    Image(uiImage: uiImage)
                                        .resizable()
                                        .scaledToFill()
                                        .frame(width: 60, height: 60)
                                        .clipShape(RoundedRectangle(cornerRadius: 6))
                                } else {
                                    RoundedRectangle(cornerRadius: 6)
                                        .fill(Color.gray.opacity(0.3))
                                        .frame(width: 60, height: 60)
                                        .overlay(
                                            Image(systemName: "photo")
                                                .foregroundColor(.gray)
                                        )
                                }

                                VStack(alignment: .leading) {
                                    Text(item.filename)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Picker("Category", selection: Binding(
                                        get: { item.category },
                                        set: { viewModel.updateImageCategory(id: item.id, category: $0) }
                                    )) {
                                        ForEach(categoryOptions, id: \.self) { cat in
                                            Text(cat).tag(cat)
                                        }
                                    }
                                    .pickerStyle(.menu)
                                }
                            }
                        }
                    }
                    .onDelete { indexSet in
                        for idx in indexSet {
                            viewModel.removeImage(id: viewModel.images[idx].id)
                        }
                    }
                }
            }

            if !viewModel.images.isEmpty {
                Section {
                    Button("Generate Report") {
                        Task { await viewModel.generate() }
                    }
                    .disabled(viewModel.isLoading)
                }
            }
        }
        .navigationTitle("Photos")
        .sheet(isPresented: $showPhotoPicker) {
            PHPickerViewControllerRepresentable(
                selectionLimit: 0
            ) { results in
                processPickerResults(results)
            }
        }
    }

    private func processPickerResults(_ results: [PHPickerResult]) {
        for result in results {
            let provider = result.itemProvider
            if provider.canLoadObject(ofClass: UIImage.self) {
                provider.loadObject(ofClass: UIImage.self) { image, error in
                    DispatchQueue.main.async {
                        if let image = image as? UIImage,
                           let data = image.jpegData(compressionQuality: 1.0) {
                            let filename = "image_\(UUID().uuidString.prefix(8)).jpg"
                            viewModel.addImage(data: data, filename: filename)
                        }
                    }
                }
            } else if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                provider.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { data, error in
                    DispatchQueue.main.async {
                        if let data = data {
                            let filename = Self.filenameFromProvider(provider) ?? "image_\(UUID().uuidString.prefix(8)).jpg"
                            viewModel.addImage(data: data, filename: filename)
                        }
                    }
                }
            }
        }
    }

    private static func filenameFromProvider(_ provider: NSItemProvider) -> String? {
        if let suggested = provider.suggestedItemName {
            let ext = (suggested as NSString).pathExtension.lowercased()
            if ["jpg", "jpeg", "png", "webp", "gif", "tiff", "bmp"].contains(ext) {
                return suggested
            }
        }
        return nil
    }
}

struct PHPickerViewControllerRepresentable: UIViewControllerRepresentable {
    let selectionLimit: Int
    let onPick: ([PHPickerResult]) -> Void

    func makeUIViewController(context: Context) -> PHPickerViewController {
        var config = PHPickerConfiguration()
        config.filter = .images
        config.selectionLimit = selectionLimit
        config.preferredAssetRepresentationMode = .current

        let picker = PHPickerViewController(configuration: config)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: PHPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick)
    }

    class Coordinator: NSObject, PHPickerViewControllerDelegate {
        let onPick: ([PHPickerResult]) -> Void

        init(onPick: @escaping ([PHPickerResult]) -> Void) {
            self.onPick = onPick
        }

        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            picker.dismiss(animated: true)
            onPick(results)
        }
    }
}
