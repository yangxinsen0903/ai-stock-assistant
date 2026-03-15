import SwiftUI

struct PortfolioView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = PortfolioViewModel()

    var body: some View {
        NavigationStack {
            VStack {
                Form {
                    Section("Mode") {
                        Text("Read-only portfolio mode: holdings are display-only and can only come from broker sync.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Section("Current Holdings") {
                        if viewModel.holdings.isEmpty {
                            Text("No holdings yet")
                                .foregroundStyle(.secondary)
                        }
                        ForEach(viewModel.holdings) { item in
                            NavigationLink {
                                HoldingDetailView(holding: item)
                                    .environmentObject(appState)
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.symbol)
                                        .font(.headline)
                                    Text("Shares: \(item.shares, specifier: "%.2f")")
                                    Text("Avg Cost: $\(item.avg_cost, specifier: "%.2f")")
                                }
                            }
                        }
                    }
                }
                .refreshable {
                    guard let token = appState.token else { return }
                    await viewModel.fetch(token: token)
                }

                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .foregroundStyle(.red)
                        .padding(.bottom, 8)
                }
            }
            .navigationTitle("Portfolio")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        guard let token = appState.token else { return }
                        Task { await viewModel.fetch(token: token) }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .task {
                if let token = appState.token {
                    await viewModel.fetch(token: token)
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .portfolioDidSync)) { _ in
                guard let token = appState.token else { return }
                Task { await viewModel.fetch(token: token) }
            }
        }
    }
}
