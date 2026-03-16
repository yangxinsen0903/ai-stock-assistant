import Foundation

enum AppConfig {
    // Temporary hardcoded endpoint for real-device testing via Tailscale.
    // We can switch back to Info.plist based config after stabilization.
    static var apiBaseURL: String {
        "http://100.99.145.120:8000/api/v1"
    }
}
