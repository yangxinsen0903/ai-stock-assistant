import Foundation

enum AppConfig {
    // Priority order:
    // 1) Xcode Run Scheme Environment Variable: API_BASE_URL
    // 2) Info.plist key: API_BASE_URL (optional)
    // 3) hardcoded fallback below
    static var apiBaseURL: String {
        if let fromEnv = ProcessInfo.processInfo.environment["API_BASE_URL"], !fromEnv.isEmpty {
            return fromEnv
        }
        if let fromPlist = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
           !fromPlist.isEmpty {
            return fromPlist
        }
        // Safe default for simulator/local tunnel
        return "http://127.0.0.1:8000/api/v1"
    }
}
