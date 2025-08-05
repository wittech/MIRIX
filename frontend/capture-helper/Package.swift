// swift-tools-version: 5.8
import PackageDescription

let package = Package(
    name: "MirixCaptureHelper",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(
            name: "mirix-capture-helper",
            targets: ["MirixCaptureHelper"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "MirixCaptureHelper"
        ),
    ]
)