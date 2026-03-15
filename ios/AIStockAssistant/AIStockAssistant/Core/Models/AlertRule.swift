import Foundation

struct AlertRule: Codable, Identifiable {
    let id: Int
    let symbol: String
    let target_price: Double
    let direction: String
    let is_enabled: Bool
}
