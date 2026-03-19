import Foundation

@MainActor
final class HoldingDetailViewModel: ObservableObject {
    @Published var chart: HoldingChartResponse?
    @Published var selectedRange: String = "1d"
    @Published var position: PositionDetailResponse?
    @Published var stats: SymbolStatsResponse?
    @Published var history: [PositionHistoryItem] = []
    @Published var errorMessage = ""
    @Published var isLoading = false

    func load(symbol: String, token: String, range: String? = nil) async {
        if let range { selectedRange = range }
        isLoading = true
        defer { isLoading = false }

        do {
            async let chartReq: HoldingChartResponse = APIClient.shared.request(
                path: "/market/chart/\(symbol)?range=\(selectedRange)",
                token: token
            )
            async let detailReq: PositionDetailResponse = APIClient.shared.request(
                path: "/portfolio/position/\(symbol)",
                token: token
            )
            async let historyReq: PositionHistoryResponse = APIClient.shared.request(
                path: "/portfolio/position/\(symbol)/history?limit=30",
                token: token
            )
            async let statsReq: SymbolStatsResponse = APIClient.shared.request(
                path: "/market/stats/\(symbol)",
                token: token
            )

            let (chartResp, detailResp, historyResp, statsResp) = try await (chartReq, detailReq, historyReq, statsReq)
            chart = chartResp
            position = detailResp
            history = historyResp.items
            stats = statsResp
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct PositionDetailResponse: Codable {
    let symbol: String
    let currency: String
    let market_value: Double
    let average_cost: Double
    let shares: Double
    let portfolio_diversity_pct: Double
    let today_return: Double
    let today_return_pct: Double
    let total_return: Double
    let total_return_pct: Double
}

struct PositionHistoryItem: Codable, Identifiable {
    let timestamp: String
    let side: String
    let quantity: Double
    let price: Double?
    let order_type: String?

    var id: String { "\(timestamp)-\(side)-\(quantity)" }
}

struct PositionHistoryResponse: Codable {
    let symbol: String
    let items: [PositionHistoryItem]
}
