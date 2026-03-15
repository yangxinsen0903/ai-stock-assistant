import Foundation

enum AppConfig {
    // For iOS Simulator, 127.0.0.1 points to your Mac running the backend.
    // For a real iPhone, replace this with your Mac's LAN IP.
    static let apiBaseURL = "http://127.0.0.1:8000/api/v1"
}
