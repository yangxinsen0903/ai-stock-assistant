import SwiftUI

struct AssistantView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = AssistantViewModel()

    var body: some View {
        NavigationStack {
            VStack {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(viewModel.messages) { message in
                            Text(message.text)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                                .background(Color.gray.opacity(0.1))
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                    .padding()
                }

                HStack(spacing: 8) {
                    TextField("Ask about your portfolio...", text: $viewModel.input)
                        .textFieldStyle(.roundedBorder)
                    Button("Send") {
                        if let token = appState.token {
                            Task { await viewModel.send(token: token) }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding()
            }
            .navigationTitle("Assistant")
        }
    }
}
