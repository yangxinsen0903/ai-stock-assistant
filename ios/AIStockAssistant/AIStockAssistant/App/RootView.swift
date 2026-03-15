import SwiftUI

struct RootView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Group {
            if appState.token == nil {
                LoginView()
            } else {
                MainTabView()
            }
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            PortfolioView()
                .tabItem { Label("Portfolio", systemImage: "chart.pie") }

            WatchlistView()
                .tabItem { Label("Watchlist", systemImage: "star") }

            AssistantView()
                .tabItem { Label("Assistant", systemImage: "sparkles") }

            AlertsView()
                .tabItem { Label("Alerts", systemImage: "bell") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
