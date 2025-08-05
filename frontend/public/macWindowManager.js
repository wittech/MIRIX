const { exec } = require('child_process');

// Function to get all running applications using System Events
async function getRunningApplications() {
  return new Promise((resolve, reject) => {
    const script = 'tell application "System Events" to get name of every application process whose visible is true';
    
    exec(`osascript -e '${script}'`, (error, stdout, stderr) => {
      if (error) {
        reject(error);
        return;
      }
      
      try {
        const apps = stdout.trim().split(', ').map(app => app.trim());
        resolve(apps);
      } catch (parseError) {
        reject(parseError);
      }
    });
  });
}

// Function to get windows for a specific application
async function getWindowsForApp(appName) {
  return new Promise((resolve) => {
    const script = `tell application "System Events" to tell application process "${appName}" to get title of every window`;
    
    exec(`osascript -e '${script}'`, (error, stdout, stderr) => {
      if (error) {
        resolve([]);
        return;
      }
      
      try {
        if (!stdout.trim()) {
          resolve([]);
          return;
        }
        
        const windows = stdout.trim().split(', ').map(title => title.trim()).filter(title => title !== '');
        resolve(windows);
      } catch (parseError) {
        resolve([]);
      }
    });
  });
}

// Function to get actual window information with real IDs using Python script
async function getWindowsWithRealIds() {
  return new Promise((resolve, reject) => {
    // Create a temporary Python script that uses Quartz to get window information
    const pythonScript = `
import sys
try:
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionAll, kCGNullWindowID
    import json
    
    # Get all windows including off-screen ones
    window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)
    
    windows = []
    important_apps = ['zoom.us', 'Zoom', 'Microsoft PowerPoint', 'Notion', 'Slack', 
                     'Microsoft Teams', 'MSTeams', 'Teams', 'Discord', 'Google Chrome',
                     'Microsoft Word', 'Microsoft Excel', 'Keynote', 'Figma',
                     'Sketch', 'Adobe Photoshop', 'Visual Studio Code', 'Cursor',
                     'Safari', 'Firefox', 'WeChat', 'Obsidian']
    
    for window in window_list:
        if window.get('kCGWindowOwnerName') and window.get('kCGWindowNumber'):
            app_name = window['kCGWindowOwnerName']
            
            # Skip system apps
            if app_name in ['SystemUIServer', 'Dock', 'ControlCenter', 'WindowManager', 'MIRIX', 'Electron']:
                continue
            
            # Only include important apps or windows with content
            is_important = any(app.lower() in app_name.lower() for app in important_apps)
            has_content = window.get('kCGWindowName', '').strip() != ''
            
            if not (is_important or has_content):
                continue
                
            # Get bounds - be more permissive with size
            bounds = window.get('kCGWindowBounds', {})
            if bounds.get('Width', 0) < 10 or bounds.get('Height', 0) < 10:
                continue
            
            # Be more permissive with layers for important apps
            layer = window.get('kCGWindowLayer', 0)
            if layer > 100:  # Very high layers are usually system elements
                continue
                
            windows.append({
                'windowId': window['kCGWindowNumber'],
                'appName': app_name,
                'windowTitle': window.get('kCGWindowName', ''),
                'bounds': bounds,
                'isOnScreen': window.get('kCGWindowIsOnscreen', False),
                'layer': layer,
                'isImportant': is_important
            })
    
    # Sort by importance and then by app name
    windows.sort(key=lambda x: (not x['isImportant'], x['appName']))
    
    print(json.dumps(windows))
    
except ImportError:
    # Fallback if Quartz is not available
    print("[]")
except Exception as e:
    print("[]")
`;

    // Write the Python script to a temporary file
    const fs = require('fs');
    const os = require('os');
    const path = require('path');
    
    const tempFile = path.join(os.tmpdir(), 'get_windows.py');
    fs.writeFileSync(tempFile, pythonScript);
    
    exec(`python3 "${tempFile}"`, (error, stdout, stderr) => {
      // Clean up temp file
      try {
        fs.unlinkSync(tempFile);
      } catch (e) {}
      
      if (error) {
        resolve([]);
        return;
      }
      
      try {
        const windows = JSON.parse(stdout);
        resolve(windows);
      } catch (parseError) {
        resolve([]);
      }
    });
  });
}

// Function to get all windows using the best available method
async function getAllWindows() {
  try {
    // First try to get windows with real IDs using Python/Quartz
    let windowsWithIds = await getWindowsWithRealIds();
    
    if (windowsWithIds.length > 0) {
      
      // Filter and process the windows
      const allWindows = [];
      const importantApps = [
        'zoom.us', 'Zoom', 'Microsoft PowerPoint', 'Notion', 'Slack', 
        'Microsoft Teams', 'MSTeams', 'Teams', 'Discord', 'Google Chrome',
        'Microsoft Word', 'Microsoft Excel', 'Keynote', 'Figma',
        'Sketch', 'Adobe Photoshop', 'Visual Studio Code', 'Cursor',
        'Safari', 'Firefox', 'WeChat', 'Obsidian', 'Roam Research'
      ];
      
      for (const window of windowsWithIds) {
        const appName = window.appName;
        
        // Skip system apps and our own app
        if (appName === 'MIRIX' || appName === 'Electron' || 
            appName === 'SystemUIServer' || appName === 'Dock' ||
            appName === 'ControlCenter' || appName === 'WindowManager' ||
            appName === 'NotificationCenter' || appName === 'Spotlight') {
          continue;
        }
        
        const isImportant = importantApps.some(app => 
          appName.toLowerCase().includes(app.toLowerCase()) ||
          app.toLowerCase().includes(appName.toLowerCase())
        );
        
        // Include windows that have titles or are from important apps
        if (window.windowTitle || isImportant) {
          let finalTitle = window.windowTitle;
          
          if (!finalTitle || finalTitle.trim() === '') {
            if (appName.includes('zoom')) finalTitle = 'Zoom Meeting';
            else if (appName.includes('PowerPoint')) finalTitle = 'PowerPoint Presentation';
            else if (appName.includes('Notion')) finalTitle = 'Notion Workspace';
            else if (appName.includes('Slack')) finalTitle = 'Slack Workspace';
            else if (appName.includes('Teams')) finalTitle = 'Teams Meeting';
            else finalTitle = appName + ' Window';
          }
          
          allWindows.push({
            windowId: window.windowId, // Real window ID from Core Graphics
            appName: appName,
            windowTitle: finalTitle,
            isOnScreen: window.isOnScreen,
            bounds: window.bounds,
            isImportantApp: isImportant,
            layer: window.layer
          });
        }
      }
      
      // Sort to put important apps first
      allWindows.sort((a, b) => {
        if (a.isImportantApp && !b.isImportantApp) return -1;
        if (!a.isImportantApp && b.isImportantApp) return 1;
        return a.appName.localeCompare(b.appName);
      });
      
      return allWindows;
    }
    
    // Fallback to the original method if Python approach fails
    const runningApps = await getRunningApplications();
    const allWindows = [];
    
    const importantApps = [
      'zoom.us', 'Zoom', 'Microsoft PowerPoint', 'Notion', 'Slack', 
      'Microsoft Teams', 'MSTeams', 'Teams', 'Discord', 'Google Chrome',
      'Microsoft Word', 'Microsoft Excel', 'Keynote', 'Figma',
      'Sketch', 'Adobe Photoshop', 'Visual Studio Code', 'Cursor',
      'Safari', 'Firefox', 'WeChat', 'Obsidian', 'Roam Research'
    ];
    
    for (const appName of runningApps) {
      if (appName === 'MIRIX' || appName === 'Electron' || 
          appName === 'SystemUIServer' || appName === 'Dock' ||
          appName === 'ControlCenter' || appName === 'WindowManager' ||
          appName === 'NotificationCenter' || appName === 'Spotlight') {
        continue;
      }
      
      const isImportant = importantApps.some(app => 
        appName.toLowerCase().includes(app.toLowerCase()) ||
        app.toLowerCase().includes(appName.toLowerCase())
      );
      
      if (isImportant) {
        let defaultTitle;
        if (appName.includes('zoom')) defaultTitle = 'Zoom Meeting';
        else if (appName.includes('PowerPoint')) defaultTitle = 'PowerPoint Presentation';
        else if (appName.includes('Notion')) defaultTitle = 'Notion Workspace';
        else if (appName.includes('Slack')) defaultTitle = 'Slack Workspace';
        else if (appName.includes('Teams')) defaultTitle = 'Teams Meeting';
        else defaultTitle = appName + ' Window';
        
        allWindows.push({
          windowId: Math.floor(Math.random() * 1000000),
          appName: appName,
          windowTitle: defaultTitle,
          isOnScreen: false,
          isImportantApp: true
        });
      }
    }
    
    return allWindows;
    
  } catch (error) {
    console.error('Error getting windows:', error);
    return [];
  }
}

// Function to capture window using different methods - DEPRECATED
// This function is no longer used as we've switched to desktopCapturer
async function captureWindowById(windowId, appName = null) {
  // Always reject since we no longer use this method
  throw new Error('captureWindowById is deprecated - use desktopCapturer instead');
}

// Function to get app icon (simplified)
async function getAppIcon(appName, bundleId) {
  return null;
}

module.exports = {
  getAllWindows,
  captureWindowById,
  getAppIcon
};