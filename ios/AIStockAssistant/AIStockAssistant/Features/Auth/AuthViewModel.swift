import Foundation

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var errorMessage = ""
    @Published var isLoading = false

    func login(appState: AppState) async {
        isLoading = true
        defer { isLoading = false }

        let payload = ["email": email, "password": password]

        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            let response: TokenResponse = try await APIClient.shared.request(
                path: "/auth/login",
                method: "POST",
                body: body
            )
            SessionStore.shared.saveToken(response.access_token)
            appState.token = response.access_token
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func register(appState: AppState) async {
        isLoading = true
        defer { isLoading = false }

        let payload = ["email": email, "password": password]

        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            let response: TokenResponse = try await APIClient.shared.request(
                path: "/auth/register",
                method: "POST",
                body: body
            )
            SessionStore.shared.saveToken(response.access_token)
            appState.token = response.access_token
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
