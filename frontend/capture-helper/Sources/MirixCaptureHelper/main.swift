import Foundation
import CoreGraphics
import AppKit
import ScreenCaptureKit

@main
struct MirixCaptureHelper {
    static func main() async {
        print("MIRIX Capture Helper starting...")
        
        let helper = CaptureHelper()
        await helper.start()
    }
}

class CaptureHelper {
    private let communicator = IPCCommunicator()
    
    func start() async {
        print("Initializing capture helper...")
        
        // Check for screen recording permissions
        await checkScreenRecordingPermissions()
        
        // Start IPC communication with Electron app
        await communicator.startListening()
        
        // Keep the helper running
        RunLoop.main.run()
    }
    
    private func checkScreenRecordingPermissions() async {
        let hasPermission = CGPreflightScreenCaptureAccess()
        if !hasPermission {
            print("❌ Screen recording permission not granted")
            let granted = CGRequestScreenCaptureAccess()
            if granted {
                print("✅ Screen recording permission granted")
            } else {
                print("❌ Screen recording permission denied")
                exit(1)
            }
        } else {
            print("✅ Screen recording permission already granted")
        }
    }
}