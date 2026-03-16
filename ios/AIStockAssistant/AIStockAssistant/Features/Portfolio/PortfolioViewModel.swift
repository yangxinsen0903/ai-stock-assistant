import Foundation

@MainActor
final class PortfolioViewModel: ObservableObject {
    @Published var holdings: [Holding] = []
    @Published var errorMessage = ""
    @Published var symbol = ""
    @Published var shares = ""
    @Published var avgCost = ""
    @Published var lastRefreshMessage = ""

    @Published var portfolioChart: PortfolioChartResponse?
    @Published var portfolioRange: String = "1d"

    func fetch(token: String) async {
        do {
            let response: [Holding] = try await APIClient.shared.request(
                path: "/portfolio/holdings",
                token: token
            )
            holdings = response
            if !response.isEmpty {
                lastRefreshMessage = "Updated \(Date().formatted(date: .omitted, time: .shortened))"
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func loadPortfolioChart(token: String, range: String? = nil) async {
        if let range { portfolioRange = range }
        do {
            let chart: PortfolioChartResponse = try await APIClient.shared.request(
                path: "/market/portfolio/chart?range=\(portfolioRange)",
                token: token
            )
            portfolioChart = chart
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refreshFromBroker(token: String) async {
        do {
            let response: BrokerSyncLite = try await APIClient.shared.request(
                path: "/broker/robinhood/sync",
                method: "POST",
                token: token
            )
            lastRefreshMessage = "Synced \(response.synced_positions) positions at \(Date().formatted(date: .omitted, time: .shortened))"
            await fetch(token: token)
            await loadPortfolioChart(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addHolding(token: String) async {
        guard let sharesValue = Double(shares), let avgCostValue = Double(avgCost), !symbol.isEmpty else {
            errorMessage = "Enter valid symbol, shares, and avg cost."
            return
        }

        let payload: [String: Any] = [
            "symbol": symbol,
            "shares": sharesValue,
            "avg_cost": avgCostValue
        ]

        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            let _: Holding = try await APIClient.shared.request(
                path: "/portfolio/holdings",
                method: "POST",
                body: body,
                token: token
            )
            symbol = ""
            shares = ""
            avgCost = ""
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteHolding(id: Int, token: String) async {
        do {
            let _: BasicResponse = try await APIClient.shared.request(
                path: "/portfolio/holdings/\(id)",
                method: "DELETE",
                token: token
            )
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct BasicResponse: Codable {
    let success: Bool
}

private struct BrokerSyncLite: Codable {
    let broker: String
    let synced_positions: Int
    let message: String
}
