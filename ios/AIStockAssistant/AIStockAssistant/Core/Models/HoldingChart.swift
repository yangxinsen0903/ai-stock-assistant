import Foundation

struct HoldingChartResponse: Codable {
    let symbol: String
    let range: String
    let currency: String
    let current_price: Double
    let previous_close: Double
    let change: Double
    let change_percent: Double
    let points: [HoldingChartPoint]
}

struct HoldingChartPoint: Codable, Identifiable {
    let ts: Int
    let price: Double

    var id: Int { ts }
    var date: Date { Date(timeIntervalSince1970: TimeInterval(ts)) }
}
