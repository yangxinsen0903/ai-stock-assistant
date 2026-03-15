import SwiftUI

struct WatchlistView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = WatchlistViewModel()

    var body: some View {
        NavigationStack {
            VStack {
                Form {
                    Section("Add Watchlist Symbol") {
                        TextField("Symbol", text: $viewModel.symbol)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled(true)
                        Button("Add") {
                            if let token = appState.token {
                                Task { await viewModel.addItem(token: token) }
                            }
                        }
                    }

                    Section("Watchlist") {
                        if viewModel.items.isEmpty {
                            Text("No watchlist items yet")
                                .foregroundStyle(.secondary)
                        }
                        ForEach(viewModel.items) { item in
                            Text(item.symbol)
                        }
                        .onDelete { indexSet in
                            guard let token = appState.token else { return }
                            let ids = indexSet.map { viewModel.items[$0].id }
                            Task {
                                for id in ids {
                                    await viewModel.deleteItem(id: id, token: token)
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
            .navigationTitle("Watchlist")
            .task {
                if let token = appState.token {
                    await viewModel.fetch(token: token)
                }
            }
        }
    }
}
