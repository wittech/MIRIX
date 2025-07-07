const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('🔍 Debugging asar archive and PGlite unpacking...');

// Setup paths
const distPath = path.join(__dirname, '..', 'dist');
const platform = process.platform;

// Find the packaged app
let appPath;
if (platform === 'darwin') {
  // macOS - look for .app in the dmg or extracted contents
  const dmgFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.dmg'));
  if (dmgFiles.length === 0) {
    console.error('❌ No DMG file found in dist directory');
    console.log('Run "npm run electron-pack" first');
    process.exit(1);
  }
  
  const dmgFile = dmgFiles[0];
  const dmgPath = path.join(distPath, dmgFile);
  console.log(`📦 Found DMG: ${dmgFile}`);
  
  // Mount the DMG if not already mounted
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
    
    // Debug the app structure
    debugAppStructure(appPath);
    
  } catch (error) {
    console.error('❌ Failed to mount DMG:', error.message);
    process.exit(1);
  }
  
} else {
  console.log('ℹ️  This debug script currently supports macOS only');
  console.log('For other platforms, manually inspect the packaged app structure');
  process.exit(0);
}

function debugAppStructure(appPath) {
  console.log('\n📂 App structure analysis:');
  
  const resourcesPath = path.join(appPath, 'Contents', 'Resources');
  const asarPath = path.join(resourcesPath, 'app.asar');
  const unpackedPath = path.join(resourcesPath, 'app.asar.unpacked');
  
  console.log(`\n📊 Resources directory: ${resourcesPath}`);
  console.log(`- exists: ${fs.existsSync(resourcesPath)}`);
  
  if (fs.existsSync(resourcesPath)) {
    const contents = fs.readdirSync(resourcesPath);
    console.log('- contents:', contents.join(', '));
  }
  
  console.log(`\n📦 app.asar file: ${asarPath}`);
  console.log(`- exists: ${fs.existsSync(asarPath)}`);
  
  if (fs.existsSync(asarPath)) {
    const stats = fs.statSync(asarPath);
    console.log(`- size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
  }
  
  console.log(`\n📂 app.asar.unpacked directory: ${unpackedPath}`);
  console.log(`- exists: ${fs.existsSync(unpackedPath)}`);
  
  if (fs.existsSync(unpackedPath)) {
    console.log('\n🔍 Unpacked directory contents:');
    try {
      const unpackedContents = fs.readdirSync(unpackedPath);
      console.log(`- root level: ${unpackedContents.join(', ')}`);
      
      // Check for node_modules
      const nodeModulesPath = path.join(unpackedPath, 'node_modules');
      if (fs.existsSync(nodeModulesPath)) {
        console.log('\n📦 node_modules found in unpacked directory');
        
        // Check for @electric-sql
        const electricSqlPath = path.join(nodeModulesPath, '@electric-sql');
        if (fs.existsSync(electricSqlPath)) {
          console.log('✅ @electric-sql found');
          
          // Check for pglite
          const pglitePath = path.join(electricSqlPath, 'pglite');
          if (fs.existsSync(pglitePath)) {
            console.log('✅ pglite package found');
            
            // Check pglite structure
            const pgliteContents = fs.readdirSync(pglitePath);
            console.log(`- pglite contents: ${pgliteContents.join(', ')}`);
            
            // Check for dist directory
            const distPath = path.join(pglitePath, 'dist');
            if (fs.existsSync(distPath)) {
              console.log('✅ pglite/dist found');
              
              const distContents = fs.readdirSync(distPath);
              console.log(`- dist contents: ${distContents.join(', ')}`);
              
              // Check for pglite.data (v0.3.x)
              const pgliteDataPath = path.join(distPath, 'pglite.data');
              if (fs.existsSync(pgliteDataPath)) {
                console.log('✅ pglite.data found');
                
                const pgliteDataStats = fs.statSync(pgliteDataPath);
                if (pgliteDataStats.isFile()) {
                  const fileSizeInMB = (pgliteDataStats.size / (1024 * 1024)).toFixed(2);
                  console.log(`✅ pglite.data is a file (${fileSizeInMB} MB) - this is correct for v0.3.x`);
                } else {
                  console.log('❌ pglite.data is not a file (this might be the problem!)');
                }
              } else {
                console.log('❌ pglite.data not found');
              }
              
              // Check for pglite.wasm
              const pgliteWasmPath = path.join(distPath, 'pglite.wasm');
              if (fs.existsSync(pgliteWasmPath)) {
                console.log('✅ pglite.wasm found');
                
                const wasmStats = fs.statSync(pgliteWasmPath);
                const wasmSizeInMB = (wasmStats.size / (1024 * 1024)).toFixed(2);
                console.log(`✅ pglite.wasm is a file (${wasmSizeInMB} MB)`);
              } else {
                console.log('❌ pglite.wasm not found');
              }
            } else {
              console.log('❌ pglite/dist not found');
            }
          } else {
            console.log('❌ pglite package not found');
          }
        } else {
          console.log('❌ @electric-sql not found');
        }
      } else {
        console.log('❌ node_modules not found in unpacked directory');
      }
    } catch (error) {
      console.error('❌ Error reading unpacked directory:', error.message);
    }
  } else {
    console.log('❌ app.asar.unpacked directory not found');
    console.log('');
    console.log('🔧 This suggests the asarUnpack configuration is not working properly.');
    console.log('Check the "asarUnpack" section in package.json build configuration.');
  }
  
  console.log('\n🎯 Debug summary:');
  console.log('For the app to work properly with PGlite v0.3.x, you need:');
  console.log('1. ✅ app.asar.unpacked directory exists');
  console.log('2. ✅ node_modules/@electric-sql/pglite exists in unpacked');
  console.log('3. ✅ pglite/dist/pglite.data exists as a file');
  console.log('4. ✅ pglite/dist/pglite.wasm exists as a file');
  console.log('');
  console.log('If any of these are missing, the PGlite error will occur.');
  
  // Cleanup
  setTimeout(() => {
    try {
      execSync(`hdiutil detach "${path.dirname(appPath)}" -quiet`);
      console.log('\n🧹 DMG unmounted');
    } catch (error) {
      console.log('\n⚠️  Could not unmount DMG automatically');
    }
  }, 1000);
} 