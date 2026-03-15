import SwiftUI
import UIKit

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var brokerConnected = false
    @State private var lastSyncedAt: String?
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
                    .disabled(isLoading || appState.token == nil)

                    if let lastSyncedAt {
                        Text("Last synced: \(lastSyncedAt)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

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
            lastSyncedAt = formatSyncTime(status.last_synced_at)
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
            // SnapTrade finishes in an external portal; allow user to tap Sync when returning.
            brokerConnected = true
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
            await refreshBrokerStatus()
            NotificationCenter.default.post(name: .portfolioDidSync, object: nil)
        } catch {
            brokerMessage = error.localizedDescription
        }
    }

    private func formatSyncTime(_ raw: String?) -> String? {
        guard let raw, !raw.isEmpty else { return nil }

        let iso = ISO8601DateFormatter()
        if let date = iso.date(from: raw) {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        return raw
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
