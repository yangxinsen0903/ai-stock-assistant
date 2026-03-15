import Foundation

@MainActor
final class WatchlistViewModel: ObservableObject {
    @Published var items: [WatchlistItem] = []
    @Published var symbol = ""
    @Published var errorMessage = ""

    func fetch(token: String) async {
        do {
            let response: [WatchlistItem] = try await APIClient.shared.request(path: "/watchlist", token: token)
            items = response
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addItem(token: String) async {
        guard !symbol.isEmpty else {
            errorMessage = "Enter a symbol."
            return
        }
        let payload = ["symbol": symbol]
        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            let _: WatchlistItem = try await APIClient.shared.request(path: "/watchlist", method: "POST", body: body, token: token)
            symbol = ""
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteItem(id: Int, token: String) async {
        do {
            let _: BasicResponse = try await APIClient.shared.request(path: "/watchlist/\(id)", method: "DELETE", token: token)
            await fetch(token: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
