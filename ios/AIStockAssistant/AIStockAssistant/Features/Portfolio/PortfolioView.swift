import SwiftUI
import Charts

struct PortfolioView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = PortfolioViewModel()
    @State private var selectedPoint: HoldingChartPoint?

    private let ranges = ["1d", "1w", "1m", "3m", "ytd", "1y", "all"]

    var body: some View {
        NavigationStack {
            VStack {
                Form {
                    Section("Portfolio") {
                        if let chart = viewModel.portfolioChart {
                            Text("$\(displayValue(chart), specifier: "%.2f")")
                                .font(.title2.bold())
                            Text(changeText(chart))
                                .foregroundStyle(displayChange(chart) >= 0 ? .green : .red)
                                .font(.subheadline)

                            if let summary = viewModel.portfolioSummary {
                                Text("Net deposits: $\(summary.net_deposits, specifier: "%.2f")")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            if let selectedPoint {
                                Text(timeLabel(for: selectedPoint.date, range: chart.range))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            Chart(Array(chart.points.enumerated()), id: \.element.id) { idx, point in
                                LineMark(
                                    x: .value("Index", idx),
                                    y: .value("Value", point.price)
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
                                        y: .value("Value", selectedPoint.price)
                                    )
                                    .foregroundStyle(.white)
                                    .symbolSize(36)
                                }
                            }
                            .chartYScale(domain: yDomain(for: chart.points.map { $0.price }))
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
                                                .onEnded { _ in selectedPoint = nil }
                                        )
                                }
                            }
                            .frame(height: 220)

                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(ranges, id: \.self) { range in
                                        Button(range.uppercased()) {
                                            guard viewModel.portfolioRange != range else { return }
                                            viewModel.portfolioRange = range
                                            Task {
                                                selectedPoint = nil
                                                guard let token = appState.token else { return }
                                                await viewModel.loadPortfolioChart(token: token)
                                            }
                                        }
                                        .buttonStyle(.plain)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 6)
                                        .background(viewModel.portfolioRange == range ? Color.white.opacity(0.12) : Color.clear)
                                        .clipShape(Capsule())
                                        .foregroundStyle(viewModel.portfolioRange == range ? Color.primary : Color.secondary)
                                    }
                                }
                            }
                        } else {
                            Text("Loading portfolio chart...")
                                .foregroundStyle(.secondary)
                        }
                    }

                    Section("Mode") {
                        Text("Read-only portfolio mode: holdings are display-only and can only come from broker sync.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        if !viewModel.lastRefreshMessage.isEmpty {
                            Text(viewModel.lastRefreshMessage)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Section("Current Holdings") {
                        if viewModel.holdings.isEmpty {
                            Text("No holdings yet")
                                .foregroundStyle(.secondary)
                        }
                        ForEach(viewModel.holdings) { item in
                            NavigationLink {
                                HoldingDetailView(holding: item)
                                    .environmentObject(appState)
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.symbol)
                                        .font(.headline)
                                    Text("Shares: \(item.shares, specifier: "%.2f")")
                                    Text("Avg Cost: $\(item.avg_cost, specifier: "%.2f")")
                                }
                            }
                        }
                    }
                }
                .refreshable {
                    guard let token = appState.token else { return }
                    await viewModel.refreshFromBroker(token: token)
                }

                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .foregroundStyle(.red)
                        .padding(.bottom, 8)
                }
            }
            .navigationTitle("Portfolio")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        guard let token = appState.token else { return }
                        Task { await viewModel.refreshFromBroker(token: token) }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .task {
                if let token = appState.token {
                    await viewModel.fetch(token: token)
                    await viewModel.loadSummary(token: token)
                    await viewModel.loadPortfolioChart(token: token)
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .portfolioDidSync)) { _ in
                guard let token = appState.token else { return }
                Task {
                    await viewModel.fetch(token: token)
                    await viewModel.loadSummary(token: token)
                    await viewModel.loadPortfolioChart(token: token)
                }
            }
        }
    }

    private func displayValue(_ chart: PortfolioChartResponse) -> Double {
        if chart.range == "all", let summary = viewModel.portfolioSummary, selectedPoint == nil {
            return summary.total_value
        }
        return selectedPoint?.price ?? chart.current_value
    }

    private func displayChange(_ chart: PortfolioChartResponse) -> Double {
        if chart.range == "all", let summary = viewModel.portfolioSummary, selectedPoint == nil {
            return summary.total_return
        }
        return displayValue(chart) - chart.reference_value
    }

    private func displayChangePercent(_ chart: PortfolioChartResponse) -> Double {
        if chart.range == "all", let summary = viewModel.portfolioSummary, selectedPoint == nil {
            return summary.total_return_pct
        }
        guard chart.reference_value != 0 else { return 0 }
        return (displayChange(chart) / chart.reference_value) * 100
    }

    private func changeText(_ chart: PortfolioChartResponse) -> String {
        let delta = displayChange(chart)
        let pct = displayChangePercent(chart)
        let sign = delta >= 0 ? "+" : "-"
        let changeAbs = String(format: "%.2f", abs(delta))
        let pctAbs = String(format: "%.2f", abs(pct))
        let suffix = selectedPoint == nil ? chart.period_label : "Selected"
        return "\(sign)$\(changeAbs) (\(sign)\(pctAbs)%) \(suffix)"
    }

    private func yDomain(for prices: [Double]) -> ClosedRange<Double> {
        guard let minPrice = prices.min(), let maxPrice = prices.max() else {
            return 0...1
        }
        let span = maxPrice - minPrice
        let basePadding = Swift.max(maxPrice * 0.003, 1.0)
        let padding = Swift.max(span * 0.15, basePadding)
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
