import SwiftUI
import Charts

struct HoldingDetailView: View {
    @EnvironmentObject var appState: AppState
    let holding: Holding
    @StateObject private var viewModel = HoldingDetailViewModel()

    private let ranges = ["1d", "1w", "1m", "3m", "ytd", "1y"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(holding.symbol)
                    .font(.largeTitle.bold())

                if let chart = viewModel.chart {
                    Text("$\(chart.current_price, specifier: "%.2f")")
                        .font(.title2.bold())

                    Text(changeText(chart))
                        .foregroundStyle(chart.change >= 0 ? .green : .red)
                        .font(.subheadline)

                    Chart(chart.points) { point in
                        LineMark(
                            x: .value("Time", point.date),
                            y: .value("Price", point.price)
                        )
                        .foregroundStyle(chart.change >= 0 ? .green : .red)
                        .interpolationMethod(.catmullRom)
                    }
                    .frame(height: 240)
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

    private func changeText(_ chart: HoldingChartResponse) -> String {
        let sign = chart.change >= 0 ? "+" : ""
        return "\(sign)$\(chart.change, specifier: "%.2f") (\(sign)\(chart.change_percent, specifier: "%.2f")%) Today"
    }
}
