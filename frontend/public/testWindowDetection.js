const { exec } = require('child_process');

// Test script to debug window detection
const testScript = `
ObjC.import('Cocoa');
ObjC.import('CoreGraphics');

function getWindowList() {
    const windows = [];
    
    // Get ALL windows without any filtering first
    const windowList = $.CGWindowListCopyWindowInfo(
        $.kCGWindowListOptionAll | $.kCGWindowListExcludeDesktopElements,
        $.kCGNullWindowID
    );
    
    const count = $.CFArrayGetCount(windowList);
    console.log('Total windows found: ' + count);
    
    for (let i = 0; i < count; i++) {
        const windowInfo = $.CFArrayGetValueAtIndex(windowList, i);
        const dict = ObjC.deepUnwrap(windowInfo);
        
        // Log every window for debugging
        if (dict.kCGWindowOwnerName) {
            windows.push({
                appName: dict.kCGWindowOwnerName,
                windowTitle: dict.kCGWindowName || '(no title)',
                windowId: dict.kCGWindowNumber,
                layer: dict.kCGWindowLayer,
                bounds: dict.kCGWindowBounds,
                isOnScreen: dict.kCGWindowIsOnscreen,
                ownerPID: dict.kCGWindowOwnerPID
            });
        }
    }
    
    $.CFRelease(windowList);
    return windows;
}

JSON.stringify(getWindowList(), null, 2);
`;

console.log('Testing window detection...\n');

exec(`osascript -l JavaScript -e '${testScript}'`, { maxBuffer: 10 * 1024 * 1024 }, (error, stdout, stderr) => {
    if (error) {
        console.error('Error:', error);
        console.error('Stderr:', stderr);
        
        // Try alternate method using window server
        console.log('\nTrying alternate method...\n');
        exec('osascript -e "tell application \\"System Events\\" to get name of every process whose visible is true"', (err2, stdout2) => {
            if (!err2) {
                console.log('Visible processes:', stdout2);
            }
        });
        return;
    }
    
    try {
        const windows = JSON.parse(stdout);
        
        // Group by app
        const appGroups = {};
        windows.forEach(w => {
            if (!appGroups[w.appName]) {
                appGroups[w.appName] = [];
            }
            appGroups[w.appName].push(w);
        });
        
        console.log(`Found ${windows.length} windows from ${Object.keys(appGroups).length} apps:\n`);
        
        // Show summary
        Object.keys(appGroups).sort().forEach(app => {
            const windows = appGroups[app];
            console.log(`${app}: ${windows.length} window(s)`);
            windows.forEach(w => {
                console.log(`  - "${w.windowTitle}" (layer: ${w.layer}, onScreen: ${w.isOnScreen})`);
            });
        });
        
        // Look for specific apps
        console.log('\nLooking for specific apps:');
        ['Zoom', 'zoom.us', 'Microsoft PowerPoint', 'Notion', 'Slack'].forEach(appName => {
            const found = appGroups[appName];
            if (found) {
                console.log(`✓ ${appName}: Found ${found.length} window(s)`);
            } else {
                console.log(`✗ ${appName}: Not found`);
            }
        });
        
    } catch (parseError) {
        console.error('Parse error:', parseError);
        console.log('Raw output:', stdout);
    }
});

// Also try using standard macOS tools
console.log('\n\nChecking with system tools...\n');
exec('osascript -e "tell application \\"System Events\\" to get {name, bundle identifier} of every application process"', (err, stdout) => {
    if (!err) {
        console.log('All running applications:', stdout);
    }
});