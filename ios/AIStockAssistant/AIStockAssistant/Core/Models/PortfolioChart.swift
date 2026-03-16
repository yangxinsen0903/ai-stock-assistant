import Foundation

struct PortfolioChartResponse: Codable {
    let range: String
    let period_label: String
    let currency: String
    let current_value: Double
    let reference_value: Double
    let change: Double
    let change_percent: Double
    let points: [HoldingChartPoint]
}
