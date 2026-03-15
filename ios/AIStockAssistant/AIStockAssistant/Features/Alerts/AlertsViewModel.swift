import Foundation

@MainActor
final class AlertsViewModel: ObservableObject {
    @Published var alerts: [AlertRule] = []
    @Published var symbol = ""
    @Published var targetPrice = ""
    @Published var direction = "above"
    @Published var errorMessage = ""

    func fetch(token: String) async {
        do {
            let response: [AlertRule] = try await APIClient.shared.request(path: "/alerts", token: token)
            alerts = response
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addAlert(token: String) async {
        guard let target = Double(targetPrice), !symbol.isEmpty else {
            errorMessage = "Enter a valid symbol and target price."
            return
        }

        let payload: [String: Any] = [
            "symbol": symbol,
            "target_price": target,
            "direction": direction
        ]

        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            let _: AlertRule = try await APIClient.shared.request(path: "/alerts", method: "POST", body: body, token: token)
            symbol = ""
            targetPrice = ""
            direction = "above"
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteAlert(id: Int, token: String) async {
        do {
            let _: BasicResponse = try await APIClient.shared.request(path: "/alerts/\(id)", method: "DELETE", token: token)
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
