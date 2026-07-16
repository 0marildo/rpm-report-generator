import SwiftUI

@main
struct ReportAgentApp: App {
    @StateObject private var viewModel = ReportViewModel()

    var body: some Scene {
        WindowGroup {
            HomeView(viewModel: viewModel)
        }
    }
}
