import Foundation

class IPCCommunicator {
    private let pipeName = "mirix-capture-helper"
    private var isRunning = false
    
    func startListening() async {
        isRunning = true
        print("Starting IPC communication on pipe: \(pipeName)")
        
        while isRunning {
            await handleIncomingRequests()
            try? await Task.sleep(for: .milliseconds(100))
        }
    }
    
    private func handleIncomingRequests() async {
        // Read from named pipe
        let pipePath = "/tmp/\(pipeName)"
        
        guard let data = readFromPipe(pipePath) else { return }
        
        do {
            let request = try JSONDecoder().decode(CaptureRequest.self, from: data)
            let response = await handleRequest(request)
            let responseData = try JSONEncoder().encode(response)
            writeToResponsePipe(responseData)
        } catch {
            print("Error handling request: \(error)")
        }
    }
    
    private func handleRequest(_ request: CaptureRequest) async -> CaptureResponse {
        print("Handling request: \(request.command)")
        
        switch request.command {
        case "list-windows":
            return await listWindows()
        case "capture-window":
            return await captureWindow(request.parameters)
        case "capture-app":
            return await captureApp(request.parameters)
        default:
            return CaptureResponse(
                success: false,
                error: "Unknown command: \(request.command)",
                data: nil
            )
        }
    }
    
    // MARK: - Capture Methods
    
    private func listWindows() async -> CaptureResponse {
        do {
            let windows = try await WindowEnumerator.getAllWindows()
            let windowsData = try JSONEncoder().encode(windows)
            
            return CaptureResponse(
                success: true,
                error: nil,
                data: windowsData
            )
        } catch {
            return CaptureResponse(
                success: false,
                error: "Failed to list windows: \(error)",
                data: nil
            )
        }
    }
    
    private func captureWindow(_ parameters: [String: Any]?) async -> CaptureResponse {
        guard let params = parameters,
              let windowId = params["windowId"] as? Int else {
            return CaptureResponse(
                success: false,
                error: "Missing windowId parameter",
                data: nil
            )
        }
        
        do {
            let imageData = try await WindowCapture.captureWindow(windowId: windowId)
            return CaptureResponse(
                success: true,
                error: nil,
                data: imageData
            )
        } catch {
            return CaptureResponse(
                success: false,
                error: "Failed to capture window: \(error)",
                data: nil
            )
        }
    }
    
    private func captureApp(_ parameters: [String: Any]?) async -> CaptureResponse {
        guard let params = parameters,
              let appName = params["appName"] as? String else {
            return CaptureResponse(
                success: false,
                error: "Missing appName parameter",
                data: nil
            )
        }
        
        do {
            let imageData = try await WindowCapture.captureApp(appName: appName)
            return CaptureResponse(
                success: true,
                error: nil,
                data: imageData
            )
        } catch {
            return CaptureResponse(
                success: false,
                error: "Failed to capture app: \(error)",
                data: nil
            )
        }
    }
    
    // MARK: - Pipe Communication
    
    private func readFromPipe(_ path: String) -> Data? {
        guard FileManager.default.fileExists(atPath: path) else { return nil }
        return try? Data(contentsOf: URL(fileURLWithPath: path))
    }
    
    private func writeToResponsePipe(_ data: Data) {
        let responsePath = "/tmp/\(pipeName)-response"
        try? data.write(to: URL(fileURLWithPath: responsePath))
    }
}

// MARK: - Data Structures

struct CaptureRequest: Codable {
    let command: String
    let parameters: [String: AnyCodable]?
}

struct CaptureResponse: Codable {
    let success: Bool
    let error: String?
    let dataBase64: String?
    
    init(success: Bool, error: String?, data: Data?) {
        self.success = success
        self.error = error
        self.dataBase64 = data?.base64EncodedString()
    }
}

struct AnyCodable: Codable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else {
            throw DecodingError.typeMismatch(AnyCodable.self, DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String {
            try container.encode(string)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let bool = value as? Bool {
            try container.encode(bool)
        } else {
            throw EncodingError.invalidValue(value, EncodingError.Context(codingPath: encoder.codingPath, debugDescription: "Unsupported type"))
        }
    }
}