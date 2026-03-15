import SwiftUI

struct PortfolioView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = PortfolioViewModel()

    var body: some View {
        NavigationStack {
            VStack {
                Form {
                    Section("Add Holding") {
                        TextField("Symbol", text: $viewModel.symbol)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled(true)
                        TextField("Shares", text: $viewModel.shares)
                            .keyboardType(.decimalPad)
                        TextField("Average Cost", text: $viewModel.avgCost)
                            .keyboardType(.decimalPad)
                        Button("Add") {
                            if let token = appState.token {
                                Task { await viewModel.addHolding(token: token) }
                            }
                        }
                    }

                    Section("Current Holdings") {
                        if viewModel.holdings.isEmpty {
                            Text("No holdings yet")
                                .foregroundStyle(.secondary)
                        }
                        ForEach(viewModel.holdings) { item in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.symbol)
                                    .font(.headline)
                                Text("Shares: \(item.shares, specifier: "%.2f")")
                                Text("Avg Cost: $\(item.avg_cost, specifier: "%.2f")")
                            }
                        }
                        .onDelete { indexSet in
                            guard let token = appState.token else { return }
                            let ids = indexSet.map { viewModel.holdings[$0].id }
                            Task {
                                for id in ids {
                                    await viewModel.deleteHolding(id: id, token: token)
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
            .navigationTitle("Portfolio")
            .task {
                if let token = appState.token {
                    await viewModel.fetch(token: token)
                }
            }
        }
    }
}
