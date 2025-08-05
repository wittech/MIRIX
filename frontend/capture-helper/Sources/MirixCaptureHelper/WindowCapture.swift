import Foundation
import CoreGraphics
import AppKit
import ScreenCaptureKit

class WindowCapture {
    
    static func captureWindow(windowId: Int) async throws -> Data {
        print("Capturing window with ID: \(windowId)")
        
        // Method 1: Try ScreenCaptureKit (macOS 12.3+)
        if #available(macOS 12.3, *) {
            do {
                return try await captureWindowWithScreenCaptureKit(windowId: windowId)
            } catch {
                print("ScreenCaptureKit failed: \(error), falling back to Core Graphics")
            }
        }
        
        // Method 2: Fallback to Core Graphics
        return try captureWindowWithCoreGraphics(windowId: windowId)
    }
    
    static func captureApp(appName: String) async throws -> Data {
        print("Capturing app: \(appName)")
        
        // First, find windows for this app
        let allWindows = try await WindowEnumerator.getAllWindows()
        let appWindows = allWindows.filter { window in
            window.appName.lowercased().contains(appName.lowercased()) ||
            appName.lowercased().contains(window.appName.lowercased())
        }
        
        guard let targetWindow = appWindows.first else {
            throw CaptureError.windowNotFound
        }
        
        print("Found window for \(appName): \(targetWindow.windowId)")
        return try await captureWindow(windowId: targetWindow.windowId)
    }
    
    // MARK: - ScreenCaptureKit Method (macOS 12.3+)
    
    @available(macOS 12.3, *)
    private static func captureWindowWithScreenCaptureKit(windowId: Int) async throws -> Data {
        // Get available content
        let availableContent = try await SCShareableContent.excludingDesktopWindows(
            false,
            onScreenWindowsOnly: false
        )
        
        // Find the specific window
        guard let targetWindow = availableContent.windows.first(where: { $0.windowID == windowId }) else {
            throw CaptureError.windowNotFound
        }
        
        // Create filter for this specific window
        let filter = SCContentFilter(desktopIndependentWindow: targetWindow)
        
        // Configure capture
        let configuration = SCStreamConfiguration()
        configuration.width = Int(targetWindow.frame.width) * 2 // Retina scaling
        configuration.height = Int(targetWindow.frame.height) * 2
        configuration.scalesToFit = true
        configuration.showsCursor = false
        configuration.backgroundColor = .clear
        
        // Perform capture
        let image = try await SCScreenshotManager.captureImage(
            contentFilter: filter,
            configuration: configuration
        )
        
        // Convert to PNG data
        guard let cgImage = image.cgImage else {
            throw CaptureError.captureFailed
        }
        
        let bitmap = NSBitmapImageRep(cgImage: cgImage)
        guard let pngData = bitmap.representation(using: .png, properties: [:]) else {
            throw CaptureError.captureFailed
        }
        
        print("✅ ScreenCaptureKit capture successful: \(pngData.count) bytes")
        return pngData
    }
    
    // MARK: - Core Graphics Method (Fallback)
    
    private static func captureWindowWithCoreGraphics(windowId: Int) throws -> Data {
        print("Using Core Graphics fallback for window \(windowId)")
        
        // Create window image
        guard let windowImage = CGWindowListCreateImage(
            .null,
            .optionIncludingWindow,
            CGWindowID(windowId),
            [.boundsIgnoreFraming, .shouldBeOpaque]
        ) else {
            throw CaptureError.captureFailed
        }
        
        // Convert to PNG data
        let bitmap = NSBitmapImageRep(cgImage: windowImage)
        guard let pngData = bitmap.representation(using: .png, properties: [:]) else {
            throw CaptureError.captureFailed
        }
        
        print("✅ Core Graphics capture successful: \(pngData.count) bytes")
        return pngData
    }
    
    // MARK: - App-Specific Capture Methods
    
    static func captureFullScreenApp(appName: String) async throws -> Data {
        print("Attempting to capture full-screen app: \(appName)")
        
        // Method 1: Try to find the app's full-screen window
        let allWindows = try await WindowEnumerator.getAllWindows()
        let fullScreenWindow = allWindows.first { window in
            window.isFullScreen && 
            (window.appName.lowercased().contains(appName.lowercased()) ||
             appName.lowercased().contains(window.appName.lowercased()))
        }
        
        if let window = fullScreenWindow {
            print("Found full-screen window for \(appName)")
            return try await captureWindow(windowId: window.windowId)
        }
        
        // Method 2: Try to activate the app and capture its main window
        print("Attempting to activate \(appName) and capture")
        try await activateAppAndCapture(appName: appName)
        
        // Wait a moment for app to come to front
        try await Task.sleep(for: .milliseconds(500))
        
        // Try to find the app's window again
        let updatedWindows = try await WindowEnumerator.getAllWindows()
        guard let appWindow = updatedWindows.first(where: { window in
            window.appName.lowercased().contains(appName.lowercased()) ||
            appName.lowercased().contains(window.appName.lowercased())
        }) else {
            throw CaptureError.windowNotFound
        }
        
        return try await captureWindow(windowId: appWindow.windowId)
    }
    
    private static func activateAppAndCapture(appName: String) async throws {
        let script = """
        tell application "\(appName)"
            activate
        end tell
        """
        
        var error: NSDictionary?
        if let scriptObject = NSAppleScript(source: script) {
            scriptObject.executeAndReturnError(&error)
            if let error = error {
                print("AppleScript error: \(error)")
                throw CaptureError.captureFailed
            }
        }
    }
}