import SwiftUI

struct AlertsView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = AlertsViewModel()

    var body: some View {
        NavigationStack {
            VStack {
                Form {
                    Section("Add Alert") {
                        TextField("Symbol", text: $viewModel.symbol)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled(true)
                        TextField("Target Price", text: $viewModel.targetPrice)
                            .keyboardType(.decimalPad)
                        Picker("Direction", selection: $viewModel.direction) {
                            Text("Above").tag("above")
                            Text("Below").tag("below")
                        }
                        Button("Add") {
                            if let token = appState.token {
                                Task { await viewModel.addAlert(token: token) }
                            }
                        }
                    }

                    Section("Alert Rules") {
                        if viewModel.alerts.isEmpty {
                            Text("No alerts yet")
                                .foregroundStyle(.secondary)
                        }
                        ForEach(viewModel.alerts) { alert in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(alert.symbol).font(.headline)
                                Text("Target: $\(alert.target_price, specifier: "%.2f")")
                                Text("Direction: \(alert.direction)")
                            }
                        }
                        .onDelete { indexSet in
                            guard let token = appState.token else { return }
                            let ids = indexSet.map { viewModel.alerts[$0].id }
                            Task {
                                for id in ids {
                                    await viewModel.deleteAlert(id: id, token: token)
                                }
                            }
                        }
                    }
                }

                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .foregroundStyle(.red)
                        .padding(.bottom, 8)
                }
            }
            .navigationTitle("Alerts")
            .task {
                if let token = appState.token {
                    await viewModel.fetch(token: token)
                }
            }
        }
    }
}
