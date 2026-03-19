import SwiftUI
import Charts

struct HoldingDetailView: View {
    @EnvironmentObject var appState: AppState
    let holding: Holding
    @StateObject private var viewModel = HoldingDetailViewModel()
    @State private var selectedPoint: HoldingChartPoint?

    private let ranges = ["1d", "1w", "1m", "3m", "ytd", "1y", "all"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(holding.symbol)
                    .font(.largeTitle.bold())

                if let chart = viewModel.chart {
                    Text("$\(displayPrice(chart), specifier: "%.2f")")
                        .font(.title2.bold())

                    Text(changeText(chart))
                        .foregroundStyle(displayChange(chart) >= 0 ? .green : .red)
                        .font(.subheadline)

                    if let selectedPoint {
                        Text(timeLabel(for: selectedPoint.date, range: chart.range))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Chart(Array(chart.points.enumerated()), id: \.element.id) { idx, point in
                        LineMark(
                            x: .value("Index", idx),
                            y: .value("Price", point.price)
                        )
                        .foregroundStyle(displayChange(chart) >= 0 ? .green : .red)
                        .lineStyle(StrokeStyle(lineWidth: 2.0, lineCap: .round, lineJoin: .round))
                        .interpolationMethod(.linear)

                        if let selectedPoint,
                           let selectedIndex = chart.points.firstIndex(where: { $0.id == selectedPoint.id }),
                           selectedPoint.id == point.id {
                            RuleMark(x: .value("Selected", selectedIndex))
                                .foregroundStyle(.gray.opacity(0.45))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))

                            PointMark(
                                x: .value("Selected", selectedIndex),
                                y: .value("Price", selectedPoint.price)
                            )
                            .foregroundStyle(.white)
                            .symbolSize(40)
                        }
                    }
                    .chartYScale(domain: yDomain(for: chart))
                    .chartXAxis(.hidden)
                    .chartYAxis(.hidden)
                    .chartPlotStyle { plot in
                        plot.background(Color.clear)
                    }
                    .chartOverlay { proxy in
                        GeometryReader { geometry in
                            Rectangle()
                                .fill(.clear)
                                .contentShape(Rectangle())
                                .gesture(
                                    DragGesture(minimumDistance: 0)
                                        .onChanged { value in
                                            let origin = geometry[proxy.plotAreaFrame].origin
                                            let x = value.location.x - origin.x
                                            guard x >= 0, x <= proxy.plotAreaSize.width,
                                                  let idx: Int = proxy.value(atX: x)
                                            else { return }
                                            let safeIdx = min(max(idx, 0), chart.points.count - 1)
                                            selectedPoint = chart.points[safeIdx]
                                        }
                                        .onEnded { _ in
                                            selectedPoint = nil
                                        }
                                )
                        }
                    }
                    .frame(height: 260)
                } else if viewModel.isLoading {
                    ProgressView("Loading chart...")
                        .frame(maxWidth: .infinity, alignment: .center)
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(ranges, id: \.self) { range in
                            Button(range.uppercased()) {
                                guard viewModel.selectedRange != range else { return }
                                viewModel.selectedRange = range
                                Task {
                                    selectedPoint = nil
                                    guard let token = appState.token else { return }
                                    await viewModel.load(symbol: holding.symbol, token: token)
                                }
                            }
                            .buttonStyle(.plain)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(viewModel.selectedRange == range ? Color.white.opacity(0.12) : Color.clear)
                            .clipShape(Capsule())
                            .foregroundStyle(viewModel.selectedRange == range ? Color.primary : Color.secondary)
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text("Your position")
                        .font(.headline)
                    Text("Shares: \(holding.shares, specifier: "%.4f")")
                    Text("Avg Cost: $\(holding.avg_cost, specifier: "%.2f")")
                }
                .padding(.top, 8)

                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .foregroundStyle(.red)
                }
            }
            .padding()
        }
        .navigationTitle("Details")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            guard let token = appState.token else { return }
            await viewModel.load(symbol: holding.symbol, token: token)
        }
        .refreshable {
            guard let token = appState.token else { return }
            await viewModel.load(symbol: holding.symbol, token: token)
        }
    }

    private func displayPrice(_ chart: HoldingChartResponse) -> Double {
        selectedPoint?.price ?? chart.current_price
    }

    private func displayChange(_ chart: HoldingChartResponse) -> Double {
        displayPrice(chart) - chart.reference_price
    }

    private func displayChangePercent(_ chart: HoldingChartResponse) -> Double {
        guard chart.reference_price != 0 else { return 0 }
        return (displayChange(chart) / chart.reference_price) * 100
    }

    private func changeText(_ chart: HoldingChartResponse) -> String {
        let delta = displayChange(chart)
        let pct = displayChangePercent(chart)
        let sign = delta >= 0 ? "+" : "-"
        let changeAbs = String(format: "%.2f", abs(delta))
        let pctAbs = String(format: "%.2f", abs(pct))
        let suffix = selectedPoint == nil ? chart.period_label : "Selected"
        return "\(sign)$\(changeAbs) (\(sign)\(pctAbs)%) \(suffix)"
    }

    private func yDomain(for chart: HoldingChartResponse) -> ClosedRange<Double> {
        let prices = chart.points.map { $0.price }
        guard let minPrice = prices.min(), let maxPrice = prices.max() else {
            return (chart.current_price - 1)...(chart.current_price + 1)
        }
        let span = maxPrice - minPrice
        let basePadding = Swift.max(maxPrice * 0.005, 0.1)
        let padding = Swift.max(span * 0.1, basePadding)
        return (minPrice - padding)...(maxPrice + padding)
    }

    private func timeLabel(for date: Date, range: String) -> String {
        let formatter = DateFormatter()
        switch range {
        case "1d", "1w":
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
        default:
            formatter.dateStyle = .medium
            formatter.timeStyle = .none
        }
        return formatter.string(from: date)
    }
}
