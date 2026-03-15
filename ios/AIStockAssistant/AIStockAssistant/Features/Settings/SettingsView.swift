import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        NavigationStack {
            Form {
                Section("Session") {
                    Button("Logout", role: .destructive) {
                        SessionStore.shared.clearToken()
                        appState.token = nil
                    }
                }
            }
            .navigationTitle("Settings")
        }
    }
}
