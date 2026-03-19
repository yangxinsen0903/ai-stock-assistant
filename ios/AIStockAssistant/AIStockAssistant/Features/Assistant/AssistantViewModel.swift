import Foundation

@MainActor
final class AssistantViewModel: ObservableObject {
    @Published var messages: [String] = []
    @Published var input = ""
    @Published var isLoading = false

    func send(token: String) async {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        messages.append("You: \(trimmed)")
        input = ""
        isLoading = true
        defer { isLoading = false }

        do {
            let body = try JSONEncoder().encode(ChatRequest(message: trimmed))
            let response: ChatResponse = try await APIClient.shared.request(
                path: "/assistant/chat",
                method: "POST",
                body: body,
                token: token
            )
            messages.append("AI: \(response.reply)")
        } catch {
            let msg = error.localizedDescription.lowercased()
            if msg.contains("401") || msg.contains("unauthorized") {
                messages.append("AI Error: Session expired. Please re-login.")
            } else if msg.contains("timed out") {
                messages.append("AI Error: Request timed out. Please retry.")
            } else {
                messages.append("AI Error: \(error.localizedDescription)")
            }
        }
    }
}
