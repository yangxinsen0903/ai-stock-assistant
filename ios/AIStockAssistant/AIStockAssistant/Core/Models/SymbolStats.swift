import Foundation

struct SymbolStatsResponse: Codable {
    let symbol: String
    let currency: String
    let previous_close: Double?
    let day_low: Double?
    let day_high: Double?
    let fifty_two_week_low: Double?
    let fifty_two_week_high: Double?
    let volume: Int?
    let avg_volume: Int?
    let market_cap: Double?
    let pe_ratio: Double?
}
