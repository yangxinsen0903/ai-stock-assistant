import Foundation

struct Holding: Codable, Identifiable {
    let id: Int
    let symbol: String
    let shares: Double
    let avg_cost: Double
}
