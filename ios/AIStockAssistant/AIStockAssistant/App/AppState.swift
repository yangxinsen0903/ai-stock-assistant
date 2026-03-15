import Foundation

final class AppState: ObservableObject {
    @Published var token: String? = SessionStore.shared.getToken()
}
