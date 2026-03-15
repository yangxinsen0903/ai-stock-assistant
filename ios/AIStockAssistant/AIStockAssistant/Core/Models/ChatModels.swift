import Foundation

struct ChatRequest: Codable {
    let message: String
}

struct ChatResponse: Codable {
    let reply: String
}

struct TokenResponse: Codable {
    let access_token: String
    let token_type: String
}
