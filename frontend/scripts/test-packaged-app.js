const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

console.log('🧪 Testing packaged app without installation...');

// Setup paths
const distPath = path.join(__dirname, '..', 'dist');
const platform = process.platform;

// Find the packaged app
let appPath;
if (platform === 'darwin') {
  // macOS - look for .app in the dmg mounted directory or extracted contents
  const dmgFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.dmg'));
  if (dmgFiles.length === 0) {
    console.error('❌ No DMG file found in dist directory');
    console.log('Run "npm run electron-pack" first');
    process.exit(1);
  }
  
  const dmgFile = dmgFiles[0];
  const dmgPath = path.join(distPath, dmgFile);
  console.log(`📦 Found DMG: ${dmgFile}`);
  
  // Mount the DMG
  const mountPoint = path.join(distPath, 'mounted');
  if (!fs.existsSync(mountPoint)) {
    fs.mkdirSync(mountPoint);
  }
  
  try {
    console.log('🔧 Mounting DMG...');
    execSync(`hdiutil attach "${dmgPath}" -mountpoint "${mountPoint}" -nobrowse -quiet`);
    
    // Find the .app file
    const appFiles = fs.readdirSync(mountPoint).filter(f => f.endsWith('.app'));
    if (appFiles.length === 0) {
      console.error('❌ No .app file found in mounted DMG');
      process.exit(1);
    }
    
    appPath = path.join(mountPoint, appFiles[0]);
    console.log(`📱 Found app: ${appFiles[0]}`);
    
    // Run the app
    console.log('🚀 Starting app...');
    const appProcess = spawn('open', [appPath], { 
      detached: true,
      stdio: 'ignore'
    });
    
    appProcess.unref();
    
    console.log('✅ App started successfully!');
    console.log('');
    console.log('🔍 To debug the app:');
    console.log('1. Open the app and check if it loads correctly');
    console.log('2. Check the console for any PGlite-related errors');
    console.log('3. If errors occur, run "npm run debug-asar" for more details');
    console.log('');
    console.log('⚠️  Note: The DMG will remain mounted for testing');
    console.log(`To unmount later: hdiutil detach "${mountPoint}"`);
    
  } catch (error) {
    console.error('❌ Failed to mount or run DMG:', error.message);
    process.exit(1);
  }
  
} else if (platform === 'win32') {
  // Windows - look for .exe
  const exeFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.exe'));
  if (exeFiles.length === 0) {
    console.error('❌ No EXE file found in dist directory');
    process.exit(1);
  }
  
  appPath = path.join(distPath, exeFiles[0]);
  console.log(`📦 Found EXE: ${exeFiles[0]}`);
  
  // Run the app
  console.log('🚀 Starting app...');
  const appProcess = spawn(appPath, [], { 
    detached: true,
    stdio: 'ignore'
  });
  
  appProcess.unref();
  console.log('✅ App started successfully!');
  
} else {
  // Linux - look for AppImage
  const appImageFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.AppImage'));
  if (appImageFiles.length === 0) {
    console.error('❌ No AppImage file found in dist directory');
    process.exit(1);
  }
  
  appPath = path.join(distPath, appImageFiles[0]);
  console.log(`📦 Found AppImage: ${appImageFiles[0]}`);
  
  // Make executable
  execSync(`chmod +x "${appPath}"`);
  
  // Run the app
  console.log('🚀 Starting app...');
  const appProcess = spawn(appPath, [], { 
    detached: true,
    stdio: 'ignore'
  });
  
  appProcess.unref();
  console.log('✅ App started successfully!');
} 