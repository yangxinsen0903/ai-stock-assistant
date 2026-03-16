import SwiftUI
import Charts

struct HoldingDetailView: View {
    @EnvironmentObject var appState: AppState
    let holding: Holding
    @StateObject private var viewModel = HoldingDetailViewModel()
    @State private var selectedPoint: HoldingChartPoint?

    private let ranges = ["1d", "1w", "1m", "3m", "ytd", "1y"]

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

                    Chart(chart.points) { point in
                        LineMark(
                            x: .value("Time", point.date),
                            y: .value("Price", point.price)
                        )
                        .foregroundStyle(displayChange(chart) >= 0 ? .green : .red)
                        .interpolationMethod(.catmullRom)

                        if let selectedPoint, selectedPoint.id == point.id {
                            RuleMark(x: .value("Selected", selectedPoint.date))
                                .foregroundStyle(.gray.opacity(0.45))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))

                            PointMark(
                                x: .value("Selected", selectedPoint.date),
                                y: .value("Price", selectedPoint.price)
                            )
                            .foregroundStyle(.white)
                            .symbolSize(40)
                        }
                    }
                    .chartYScale(domain: yDomain(for: chart))
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
                                                  let date: Date = proxy.value(atX: x)
                                            else { return }
                                            selectedPoint = nearestPoint(to: date, in: chart.points)
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

                Picker("Range", selection: $viewModel.selectedRange) {
                    ForEach(ranges, id: \.self) { range in
                        Text(range.uppercased()).tag(range)
                    }
                }
                .pickerStyle(.segmented)
                .onChange(of: viewModel.selectedRange) { _, _ in
                    Task {
                        selectedPoint = nil
                        guard let token = appState.token else { return }
                        await viewModel.load(symbol: holding.symbol, token: token)
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
        guard let min = prices.min(), let max = prices.max() else {
            return (chart.current_price - 1)...(chart.current_price + 1)
        }
        let span = max - min
        let base = max(max * 0.005, 0.1)
        let padding = max(span * 0.1, base)
        return (min - padding)...(max + padding)
    }

    private func nearestPoint(to date: Date, in points: [HoldingChartPoint]) -> HoldingChartPoint? {
        points.min(by: {
            abs($0.date.timeIntervalSince1970 - date.timeIntervalSince1970) <
            abs($1.date.timeIntervalSince1970 - date.timeIntervalSince1970)
        })
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
