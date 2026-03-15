import SwiftUI
import UIKit

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var brokerConnected = false
    @State private var brokerMessage = ""
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Broker") {
                    HStack {
                        Text("Robinhood")
                        Spacer()
                        Text(brokerConnected ? "Connected" : "Not connected")
                            .foregroundStyle(brokerConnected ? .green : .secondary)
                    }

                    Button("Connect Robinhood") {
                        Task { await connectRobinhood() }
                    }
                    .disabled(isLoading || appState.token == nil)

                    Button("Sync Portfolio") {
                        Task { await syncPortfolio() }
                    }
                    .disabled(isLoading || appState.token == nil || !brokerConnected)

                    if !brokerMessage.isEmpty {
                        Text(brokerMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Session") {
                    Button("Logout", role: .destructive) {
                        SessionStore.shared.clearToken()
                        appState.token = nil
                    }
                }
            }
            .navigationTitle("Settings")
            .task {
                await refreshBrokerStatus()
            }
        }
    }

    private func refreshBrokerStatus() async {
        guard let token = appState.token else { return }
        do {
            let status: BrokerStatus = try await APIClient.shared.request(
                path: "/broker/robinhood/status",
                token: token
            )
            brokerConnected = status.connected
        } catch {
            brokerMessage = error.localizedDescription
        }
    }

    private func connectRobinhood() async {
        guard let token = appState.token else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let response: BrokerConnect = try await APIClient.shared.request(
                path: "/broker/robinhood/connect",
                token: token
            )

            guard let url = URL(string: response.connect_url) else {
                brokerMessage = "Invalid connect URL"
                return
            }

            await MainActor.run {
                UIApplication.shared.open(url)
            }
            brokerMessage = "Complete authentication in browser, then tap Sync Portfolio."
        } catch {
            brokerMessage = error.localizedDescription
        }
    }

    private func syncPortfolio() async {
        guard let token = appState.token else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let response: BrokerSync = try await APIClient.shared.request(
                path: "/broker/robinhood/sync",
                method: "POST",
                token: token
            )
            brokerConnected = true
            brokerMessage = "Synced \(response.synced_positions) positions."
            NotificationCenter.default.post(name: .portfolioDidSync, object: nil)
        } catch {
            brokerMessage = error.localizedDescription
        }
    }
}

private struct BrokerStatus: Codable {
    let broker: String
    let connected: Bool
    let last_synced_at: String?
}

private struct BrokerConnect: Codable {
    let broker: String
    let connect_url: String
}

private struct BrokerSync: Codable {
    let broker: String
    let synced_positions: Int
    let message: String
}

extension Notification.Name {
    static let portfolioDidSync = Notification.Name("portfolioDidSync")
}
