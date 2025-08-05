import Foundation
import CoreGraphics
import AppKit

struct WindowInfo: Codable {
    let windowId: Int
    let appName: String
    let windowTitle: String
    let bounds: CGRect
    let isOnScreen: Bool
    let ownerPID: Int
    let isFullScreen: Bool
}

class WindowEnumerator {
    static func getAllWindows() async throws -> [WindowInfo] {
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    let windows = try self.enumerateWindows()
                    continuation.resume(returning: windows)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
    
    private static func enumerateWindows() throws -> [WindowInfo] {
        guard let windowList = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) else {
            throw CaptureError.windowEnumerationFailed
        }
        
        let windowArray = windowList as NSArray
        var windows: [WindowInfo] = []
        
        for item in windowArray {
            guard let windowDict = item as? [String: Any],
                  let windowNumber = windowDict[kCGWindowNumber as String] as? Int,
                  let ownerName = windowDict[kCGWindowOwnerName as String] as? String,
                  let ownerPID = windowDict[kCGWindowOwnerPID as String] as? Int else {
                continue
            }
            
            // Skip system processes and our own app
            let systemApps = ["WindowServer", "Dock", "SystemUIServer", "ControlCenter", "NotificationCenter"]
            if systemApps.contains(ownerName) || ownerName == "MIRIX" {
                continue
            }
            
            let windowTitle = windowDict[kCGWindowName as String] as? String ?? ""
            let isOnScreen = windowDict[kCGWindowIsOnscreen as String] as? Bool ?? false
            
            // Get window bounds
            var bounds = CGRect.zero
            if let boundsDict = windowDict[kCGWindowBounds as String] as? [String: Any] {
                bounds = CGRect(
                    x: boundsDict["X"] as? CGFloat ?? 0,
                    y: boundsDict["Y"] as? CGFloat ?? 0,
                    width: boundsDict["Width"] as? CGFloat ?? 0,
                    height: boundsDict["Height"] as? CGFloat ?? 0
                )
            }
            
            // Skip tiny windows (likely UI elements)
            if bounds.width < 50 || bounds.height < 50 {
                continue
            }
            
            // Check if window is full-screen
            let isFullScreen = checkIfFullScreen(bounds: bounds, pid: ownerPID)
            
            let windowInfo = WindowInfo(
                windowId: windowNumber,
                appName: ownerName,
                windowTitle: windowTitle,
                bounds: bounds,
                isOnScreen: isOnScreen,
                ownerPID: ownerPID,
                isFullScreen: isFullScreen
            )
            
            windows.append(windowInfo)
        }
        
        // Sort by importance (full-screen and visible windows first)
        windows.sort { first, second in
            if first.isFullScreen && !second.isFullScreen {
                return true
            }
            if !first.isFullScreen && second.isFullScreen {
                return false
            }
            if first.isOnScreen && !second.isOnScreen {
                return true
            }
            if !first.isOnScreen && second.isOnScreen {
                return false
            }
            return first.appName < second.appName
        }
        
        return windows
    }
    
    private static func checkIfFullScreen(bounds: CGRect, pid: Int) -> Bool {
        // Get all screens
        let screens = NSScreen.screens
        
        // Check if window bounds match any screen bounds (indicating full-screen)
        for screen in screens {
            let screenFrame = screen.frame
            
            // Allow for small differences due to menu bar, dock, etc.
            let tolerance: CGFloat = 50
            
            if abs(bounds.width - screenFrame.width) < tolerance &&
               abs(bounds.height - screenFrame.height) < tolerance {
                return true
            }
        }
        
        // Also check if the app is in a full-screen space
        return checkIfAppInFullScreenSpace(pid: pid)
    }
    
    private static func checkIfAppInFullScreenSpace(pid: Int) -> Bool {
        // Use AppleScript to check if app is in full-screen mode
        let script = """
        tell application "System Events"
            try
                set appProcess to first process whose unix id is \(pid)
                return (value of attribute "AXFullScreen" of first window of appProcess)
            on error
                return false
            end try
        end tell
        """
        
        var error: NSDictionary?
        if let scriptObject = NSAppleScript(source: script) {
            let result = scriptObject.executeAndReturnError(&error)
            if error == nil {
                return result.booleanValue
            }
        }
        
        return false
    }
}

enum CaptureError: Error {
    case windowEnumerationFailed
    case windowNotFound
    case capturePermissionDenied
    case captureFailed
    case invalidWindowId
}