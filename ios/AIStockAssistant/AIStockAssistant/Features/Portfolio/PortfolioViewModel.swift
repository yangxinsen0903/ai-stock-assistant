import Foundation

@MainActor
final class PortfolioViewModel: ObservableObject {
    @Published var holdings: [Holding] = []
    @Published var errorMessage = ""
    @Published var symbol = ""
    @Published var shares = ""
    @Published var avgCost = ""

    func fetch(token: String) async {
        do {
            let response: [Holding] = try await APIClient.shared.request(
                path: "/portfolio/holdings",
                token: token
            )
            holdings = response
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
