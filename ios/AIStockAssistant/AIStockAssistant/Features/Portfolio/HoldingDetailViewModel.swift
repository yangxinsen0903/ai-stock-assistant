import Foundation

@MainActor
final class HoldingDetailViewModel: ObservableObject {
    @Published var chart: HoldingChartResponse?
    @Published var selectedRange: String = "1d"
    @Published var errorMessage = ""
    @Published var isLoading = false

    func load(symbol: String, token: String, range: String? = nil) async {
        if let range { selectedRange = range }
        isLoading = true
        defer { isLoading = false }

        do {
            let response: HoldingChartResponse = try await APIClient.shared.request(
                path: "/market/chart/\(symbol)?range=\(selectedRange)",
                token: token
            )
            chart = response
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
