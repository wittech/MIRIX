const { app, BrowserWindow, Menu, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const isDev = require('electron-is-dev');
// Override isDev for packaged apps - if we're running from a packaged app, we're in production
// Check multiple indicators to determine if we're in a packaged app
const isPackaged = app.isPackaged || 
                  process.mainModule.filename.indexOf('app.asar') !== -1 ||
                  process.execPath.indexOf('MIRIX.app') !== -1 ||
                  __dirname.indexOf('app.asar') !== -1;
const actuallyDev = isDev && !isPackaged;
const { spawn } = require('child_process');
const screenshot = require('screenshot-desktop');
const http = require('http');
// Dynamic PGlite import - will be set in initialization
let PGlite;
const express = require('express');

// Safe console logging that only works in development mode
// Packaging detection completed

const safeLog = {
  log: (...args) => {
    if (actuallyDev) {
      console.log(...args);
    }
  },
  error: (...args) => {
    // Always log errors for debugging backend issues
    console.error(...args);
  },
  warn: (...args) => {
    if (actuallyDev) {
      console.warn(...args);
    }
  }
};

let mainWindow;
let backendProcess = null;
let pgliteDb = null;
let dbBridgeServer = null;
const backendPort = 8000; // Fixed backend port
const dbBridgePort = 8001; // Database bridge port

// Create screenshots directory
function ensureScreenshotDirectory() {
    const mirixDir = path.join(os.homedir(), '.mirix');
    const tmpDir = path.join(mirixDir, 'tmp');
  const imagesDir = path.join(tmpDir, 'images');
    
    if (!fs.existsSync(mirixDir)) {
      fs.mkdirSync(mirixDir, { recursive: true });
    }
    if (!fs.existsSync(tmpDir)) {
      fs.mkdirSync(tmpDir, { recursive: true });
    }
  if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
  }
  
  return imagesDir;
}

// Create database directory
function ensureDatabaseDirectory() {
  const mirixDir = path.join(os.homedir(), '.mirix');
  const dbDir = path.join(mirixDir, 'database');
  
  if (!fs.existsSync(mirixDir)) {
    fs.mkdirSync(mirixDir, { recursive: true });
  }
  if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
  }
  
  return dbDir;
}

// Initialize PGlite database
async function initializePGliteDatabase() {
  try {
    const dbDir = ensureDatabaseDirectory();
    const dbPath = path.join(dbDir, 'mirix.db');
    
    safeLog.log(`Initializing PGlite database at: ${dbPath}`);
    
    // Load PGlite from the correct location
    if (!PGlite) {
      safeLog.log(`Loading PGlite - actuallyDev: ${actuallyDev}`);
      if (!actuallyDev) {
        // In production, load from unpacked location
        safeLog.log('Loading PGlite from unpacked location (production mode)');
        
        // Fix resourcesPath for packaged apps
        let actualResourcesPath = process.resourcesPath;
        if (__dirname.indexOf('app.asar') !== -1) {
          const appAsarPath = __dirname.substring(0, __dirname.indexOf('app.asar'));
          actualResourcesPath = appAsarPath;
        }
        safeLog.log(`Using actualResourcesPath: ${actualResourcesPath}`);
        
        const unpackedPath = path.join(actualResourcesPath, 'app.asar.unpacked', 'node_modules', '@electric-sql', 'pglite');
        const pgliteMainPath = path.join(unpackedPath, 'dist', 'index.cjs');
        
        safeLog.log(`Loading PGlite from unpacked location: ${pgliteMainPath}`);
        
        if (fs.existsSync(pgliteMainPath)) {
          // Load PGlite from unpacked location
          const pgliteModule = require(pgliteMainPath);
          PGlite = pgliteModule.PGlite;
          safeLog.log('✅ PGlite loaded from unpacked location');
        } else {
          safeLog.error(`❌ PGlite not found at unpacked location: ${pgliteMainPath}`);
          safeLog.log('Falling back to regular require...');
          const { PGlite: FallbackPGlite } = require('@electric-sql/pglite');
          PGlite = FallbackPGlite;
        }
      } else {
        // In development, use regular require
        safeLog.log('Development mode: Loading PGlite normally');
        safeLog.log('WARNING: This should not happen in packaged app!');
        const { PGlite: DevPGlite } = require('@electric-sql/pglite');
        PGlite = DevPGlite;
      }
    }
    
    // Handle asar unpacked location for PGlite
    let pgliteOptions = {
      // Add any extensions here if needed
      // extensions: {
      //   vector: vector()  // pgvector support when available
      // }
    };
    
    // In production, set environment variables to help PGlite find its files
    if (!actuallyDev) {
      // Fix resourcesPath for packaged apps - when running via npx electron, process.resourcesPath points to dev electron
      let actualResourcesPath = process.resourcesPath;
      if (__dirname.indexOf('app.asar') !== -1) {
        // Extract the actual app path from __dirname
        const appAsarPath = __dirname.substring(0, __dirname.indexOf('app.asar'));
        actualResourcesPath = appAsarPath;
      }
      safeLog.log(`Fixed resourcesPath: ${actualResourcesPath}`);
      
      const unpackedPath = path.join(actualResourcesPath, 'app.asar.unpacked', 'node_modules', '@electric-sql', 'pglite');
      const distPath = path.join(unpackedPath, 'dist');
      
      if (fs.existsSync(unpackedPath)) {
        // Set environment variables to help PGlite find its native files
        process.env.PGLITE_PATH = unpackedPath;
        process.env.PGLITE_DIST_PATH = distPath;
        process.env.PGLITE_WASM_PATH = path.join(distPath, 'pglite.wasm');
        process.env.PGLITE_DATA_PATH = path.join(distPath, 'pglite.data');
        
        safeLog.log('✅ PGlite environment variables configured');
        safeLog.log(`- Unpacked path: ${unpackedPath}`);
        safeLog.log(`- Dist path: ${distPath}`);
        
        // Verify critical files exist
        const wasmPath = path.join(distPath, 'pglite.wasm');
        const dataPath = path.join(distPath, 'pglite.data');
        
        safeLog.log(`- WASM file exists: ${fs.existsSync(wasmPath)}`);
        safeLog.log(`- Data file exists: ${fs.existsSync(dataPath)}`);
      } else {
        safeLog.error(`❌ PGlite unpacked directory not found at: ${unpackedPath}`);
      }
    }
    
    // Initialize PGlite with persistent storage
    pgliteDb = new PGlite(`file://${dbPath}`, pgliteOptions);
    
    // Test database connection
    await pgliteDb.query('SELECT 1 as test');
    safeLog.log('PGlite database initialized successfully');
    
    // Setup initial database schema
    await setupDatabaseSchema();
    
    return pgliteDb;
  } catch (error) {
    safeLog.error('Failed to initialize PGlite database:', error);
    
    // More detailed error information for debugging
    if (error.message && (error.message.includes('postgres.data') || error.message.includes('pglite.data'))) {
      safeLog.error('');
      safeLog.error('🔧 PGlite packaging issue detected:');
      safeLog.error('This error occurs when PGlite native files are not properly unpacked from the asar archive.');
      safeLog.error('');
      safeLog.error('Debug information:');
      safeLog.error(`- actuallyDev: ${actuallyDev}`);
      safeLog.error(`- resourcesPath: ${process.resourcesPath}`);
      safeLog.error(`- __dirname: ${__dirname}`);
      
      // Check if asar unpacked directory exists
      const unpackedPath = path.join(process.resourcesPath, 'app.asar.unpacked');
      safeLog.error(`- unpackedPath exists: ${fs.existsSync(unpackedPath)}`);
      
      if (fs.existsSync(unpackedPath)) {
        const pglitePath = path.join(unpackedPath, 'node_modules', '@electric-sql', 'pglite');
        safeLog.error(`- PGlite unpacked exists: ${fs.existsSync(pglitePath)}`);
        
        if (fs.existsSync(pglitePath)) {
          const distPath = path.join(pglitePath, 'dist');
          safeLog.error(`- PGlite dist exists: ${fs.existsSync(distPath)}`);
          
          if (fs.existsSync(distPath)) {
            const pgliteDataPath = path.join(distPath, 'pglite.data');
            const pgliteWasmPath = path.join(distPath, 'pglite.wasm');
            const postgresDataPath = path.join(distPath, 'postgres.data');  // Legacy check
            
            safeLog.error(`- pglite.data exists: ${fs.existsSync(pgliteDataPath)}`);
            safeLog.error(`- pglite.wasm exists: ${fs.existsSync(pgliteWasmPath)}`);
            safeLog.error(`- postgres.data (legacy) exists: ${fs.existsSync(postgresDataPath)}`);
            
            // List some dist contents for debugging
            try {
              const distContents = fs.readdirSync(distPath);
              safeLog.error(`- Dist directory contents (first 10): ${distContents.slice(0, 10).join(', ')}`);
            } catch (e) {
              safeLog.error(`- Could not read dist directory: ${e.message}`);
            }
          }
        }
      }
      safeLog.error('');
    }
    
    throw error;
  }
}

// Setup database schema
async function setupDatabaseSchema() {
  try {
    safeLog.log('Setting up database schema...');
    
    // Full Mirix database schema for PGlite
    const schema = `
-- Basic PGlite Schema for Mirix
-- Essential tables for core functionality

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    timezone VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    memory TEXT,
    tools TEXT,
    agent_type VARCHAR DEFAULT 'mirix_agent',
    llm_config TEXT,
    embedding_config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    text TEXT,
    content TEXT,
    model VARCHAR,
    name VARCHAR,
    tool_calls TEXT,
    tool_call_id VARCHAR,
    tool_return TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Tools table
CREATE TABLE IF NOT EXISTS tools (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    tool_type VARCHAR DEFAULT 'custom',
    return_char_limit INTEGER,
    description TEXT,
    tags TEXT,
    source_type VARCHAR DEFAULT 'json',
    source_code TEXT,
    json_schema TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Blocks table (for core memory)
CREATE TABLE IF NOT EXISTS blocks (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    template_name VARCHAR,
    description TEXT,
    label VARCHAR NOT NULL,
    is_template BOOLEAN DEFAULT FALSE,
    value TEXT NOT NULL,
    char_limit INTEGER DEFAULT 2000,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Providers table
CREATE TABLE IF NOT EXISTS providers (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    api_key VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Knowledge vault table
CREATE TABLE IF NOT EXISTS knowledge_vault (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    entry_type VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    sensitivity VARCHAR NOT NULL,
    secret_value TEXT NOT NULL,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Semantic memory table
CREATE TABLE IF NOT EXISTS semantic_memory (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL,
    source VARCHAR,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Episodic memory table
CREATE TABLE IF NOT EXISTS episodic_memory (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    last_modify TEXT NOT NULL,
    actor VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    details TEXT NOT NULL,
    tree_path TEXT NOT NULL,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Procedural memory table
CREATE TABLE IF NOT EXISTS procedural_memory (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    entry_type VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    steps TEXT NOT NULL,
    tree_path TEXT NOT NULL,
    last_modify TEXT NOT NULL,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Resource memory table
CREATE TABLE IF NOT EXISTS resource_memory (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    resource_type VARCHAR NOT NULL,
    content TEXT NOT NULL,
    tree_path TEXT NOT NULL,
    last_modify TEXT NOT NULL,
    metadata_ TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

-- Files table
CREATE TABLE IF NOT EXISTS files (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    source_id VARCHAR,
    file_name VARCHAR,
    file_path VARCHAR,
    source_url VARCHAR,
    google_cloud_url VARCHAR,
    file_type VARCHAR,
    file_size INTEGER,
    file_creation_date VARCHAR,
    file_last_modified_date VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
`;

    await pgliteDb.exec(schema);
    
    // Create indexes for better performance (separate execution to avoid issues)
    const indexes = `
CREATE INDEX IF NOT EXISTS idx_messages_agent_created_at ON messages(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at, id);
CREATE INDEX IF NOT EXISTS idx_agents_organization ON agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_tools_organization ON tools(organization_id);
CREATE INDEX IF NOT EXISTS idx_blocks_organization ON blocks(organization_id);
CREATE INDEX IF NOT EXISTS idx_semantic_memory_organization ON semantic_memory(organization_id);
CREATE INDEX IF NOT EXISTS idx_episodic_memory_organization ON episodic_memory(organization_id);
CREATE INDEX IF NOT EXISTS idx_procedural_memory_organization ON procedural_memory(organization_id);
CREATE INDEX IF NOT EXISTS idx_resource_memory_organization ON resource_memory(organization_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_vault_organization ON knowledge_vault(organization_id);
CREATE INDEX IF NOT EXISTS idx_files_organization ON files(organization_id);
`;

    await pgliteDb.exec(indexes);

    // Insert default data if needed
    const defaultData = `
INSERT INTO organizations (id, name) 
VALUES ('default-org', 'Default Organization') 
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, organization_id, name, timezone) 
VALUES ('default-user', 'default-org', 'Default User', 'UTC') 
ON CONFLICT (id) DO NOTHING;
`;

    await pgliteDb.exec(defaultData);
    
    safeLog.log('Database schema setup complete');
  } catch (error) {
    safeLog.error('Failed to setup database schema:', error);
    throw error;
  }
}

// Create HTTP bridge server for Python backend to communicate with PGlite
async function startDatabaseBridge() {
  return new Promise((resolve, reject) => {
    try {
      const app = express();
      app.use(express.json({ limit: '10mb' }));
      
      // Health check endpoint
      app.get('/health', (req, res) => {
        res.json({ status: 'ok', database: 'pglite' });
      });
      
      // Execute query endpoint
      app.post('/query', async (req, res) => {
        try {
          const { query, params } = req.body;
          safeLog.log(`Executing query: ${query}`);
          
          const result = await pgliteDb.query(query, params || []);
          res.json({
            success: true,
            rows: result.rows,
            rowCount: result.rowCount,
            fields: result.fields
          });
        } catch (error) {
          safeLog.error('Database query error:', error);
          res.status(500).json({
            success: false,
            error: error.message
          });
        }
      });
      
      // Execute multiple queries (transaction)
      app.post('/exec', async (req, res) => {
        try {
          const { sql } = req.body;
          safeLog.log(`Executing SQL: ${sql}`);
          
          const result = await pgliteDb.exec(sql);
          res.json({
            success: true,
            result: result
          });
        } catch (error) {
          safeLog.error('Database exec error:', error);
          res.status(500).json({
            success: false,
            error: error.message
          });
        }
      });
      
      // Start the bridge server
      dbBridgeServer = app.listen(dbBridgePort, 'localhost', () => {
        safeLog.log(`Database bridge server running on port ${dbBridgePort}`);
        resolve();
      });
      
      dbBridgeServer.on('error', (error) => {
        safeLog.error('Database bridge server error:', error);
        reject(error);
      });
      
    } catch (error) {
      safeLog.error('Failed to start database bridge:', error);
      reject(error);
    }
  });
}

// Stop database bridge server
function stopDatabaseBridge() {
  if (dbBridgeServer) {
    dbBridgeServer.close();
    dbBridgeServer = null;
    safeLog.log('Database bridge server stopped');
  }
}

// Modified backend startup function
function startBackendServer() {
  if (actuallyDev) {
    // In development, assume backend is running separately
    safeLog.log('Development mode: Backend should be running separately');
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    try {
      // In production, start the bundled backend executable
      const executableName = 'main'; // Our pre-built executable name
      
      // Fix resourcesPath for packaged apps
      let actualResourcesPath = process.resourcesPath;
      if (__dirname.indexOf('app.asar') !== -1) {
        const appAsarPath = __dirname.substring(0, __dirname.indexOf('app.asar'));
        actualResourcesPath = appAsarPath;
      }
      
              const backendPath = path.join(actualResourcesPath, 'backend', executableName);
        
        safeLog.log(`Looking for backend executable at: ${backendPath}`);
        safeLog.log(`actualResourcesPath: ${actualResourcesPath}`);
        safeLog.log(`Backend executable exists: ${fs.existsSync(backendPath)}`);
      
              // Check if backend executable exists
        if (!fs.existsSync(backendPath)) {
          const error = `Backend executable not found at: ${backendPath}`;
          safeLog.error(error);
          safeLog.error('Available files in backend directory:');
          const backendDir = path.join(actualResourcesPath, 'backend');
        if (fs.existsSync(backendDir)) {
          const files = fs.readdirSync(backendDir);
          files.forEach(file => safeLog.error(`  - ${file}`));
        } else {
          safeLog.error('Backend directory does not exist');
        }
        reject(new Error(error));
        return;
      }
      
              safeLog.log(`Starting backend server on port ${backendPort}: ${backendPath}`);
        
        // Set working directory to the backend directory (where configs are located)
        const workingDir = path.join(actualResourcesPath, 'backend');
      
              // Start backend with SQLite configuration (default)
        safeLog.log(`Starting backend process with command: ${backendPath} --host 0.0.0.0 --port ${backendPort.toString()}`);
        safeLog.log(`Working directory: ${workingDir}`);
        safeLog.log(`Working directory exists: ${fs.existsSync(workingDir)}`);
        
        backendProcess = spawn(backendPath, ['--host', '0.0.0.0', '--port', backendPort.toString()], {
          stdio: ['pipe', 'pipe', 'pipe'],
          detached: false,
          cwd: workingDir,
          env: {
            ...process.env,
            PORT: backendPort.toString(),
            PYTHONPATH: workingDir,
            // Clear any PostgreSQL URI to force SQLite fallback
            MIRIX_PG_URI: '',
          }
        });

      let startupOutput = '';
      let errorOutput = '';
      let healthCheckStarted = false;

      backendProcess.stdout.on('data', (data) => {
        const output = data.toString().trim();
        startupOutput += output;
        safeLog.log(`Backend STDOUT: ${output}`);
        
        // Check if the server has started successfully
        if (output.includes('Uvicorn running on') || 
            output.includes('Application startup complete') ||
            output.includes('Started server process')) {
          
          if (!healthCheckStarted) {
            healthCheckStarted = true;
            safeLog.log('Backend server startup detected, starting health check...');
            setTimeout(() => {
              checkBackendHealth().then(() => {
                safeLog.log('Backend health check passed, resolving startup');
                resolve();
              }).catch((healthError) => {
                safeLog.error('Backend health check failed:', healthError);
                reject(healthError);
              });
            }, 3000);
          }
        }
      });

      backendProcess.stderr.on('data', (data) => {
        const output = data.toString();
        errorOutput += output;
        safeLog.error(`Backend STDERR: ${output}`);
        
        // Check for specific error patterns
        if (output.includes('Address already in use') || output.includes('EADDRINUSE')) {
          safeLog.error('❌ Port conflict detected - another process is using the port');
        }
        if (output.includes('Permission denied') || output.includes('EACCES')) {
          safeLog.error('❌ Permission denied - check file permissions');
        }
        if (output.includes('No such file or directory') || output.includes('ENOENT')) {
          safeLog.error('❌ File not found - missing dependency or executable');
        }
      });

      backendProcess.on('close', (code) => {
        safeLog.log(`Backend process exited with code ${code}`);
        if (code !== 0 && !healthCheckStarted) {
          reject(new Error(`Backend process exited with code ${code}. Error output: ${errorOutput}`));
        }
      });

      backendProcess.on('error', (error) => {
        safeLog.error('Failed to start backend process:', error);
        reject(error);
      });

      // Timeout fallback
      setTimeout(() => {
        if (backendProcess && backendProcess.exitCode === null && !healthCheckStarted) {
          safeLog.warn('Backend startup timeout, trying health check...');
          checkBackendHealth().then(() => {
            safeLog.log('Health check passed despite timeout');
            resolve();
          }).catch((healthError) => {
            safeLog.error('Backend health check failed after timeout:', healthError);
            reject(new Error(`Backend startup timeout: ${healthError.message}`));
          });
        }
      }, 30000); // 30 second timeout

      safeLog.log('Backend server started');
    } catch (error) {
      safeLog.error('Failed to start backend server:', error);
      reject(error);
    }
  });
}

async function checkBackendHealth() {
  const maxRetries = 5;
  const retryDelay = 1000;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      safeLog.log(`Health check attempt ${i + 1}/${maxRetries} - checking http://127.0.0.1:${backendPort}/health`);
      
      const healthCheckResult = await new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${backendPort}/health`, { timeout: 5000 }, (res) => {
          let data = '';
          
          res.on('data', chunk => {
            data += chunk;
          });
          
          res.on('end', () => {
            if (res.statusCode === 200) {
              safeLog.log(`Health check response: ${data}`);
              resolve(data);
            } else {
              reject(new Error(`Health check failed with status: ${res.statusCode}, response: ${data}`));
            }
          });
        });
        
        req.on('error', (error) => {
          safeLog.error(`Health check request error:`, error);
          reject(error);
        });
        
        req.setTimeout(5000, () => {
          req.destroy();
          reject(new Error('Health check timeout after 5 seconds'));
        });
      });
      
      safeLog.log('✅ Backend health check passed');
      return healthCheckResult;
      
    } catch (error) {
      safeLog.warn(`❌ Health check attempt ${i + 1} failed:`, {
        message: error.message,
        code: error.code,
        errno: error.errno
      });
      
      if (i < maxRetries - 1) {
        safeLog.log(`Retrying in ${retryDelay}ms...`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      } else {
        safeLog.error(`All health check attempts failed. Final error:`, error);
        throw error;
      }
    }
  }
}

function stopBackendServer() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
    safeLog.log('Backend server stopped');
  }
}

function createWindow() {
  // Ensure screenshot directory exists
  ensureScreenshotDirectory();

  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'icon.png'), // Add your app icon here
    titleBarStyle: 'default',
    show: false
  });

  // Load the app
  const startUrl = actuallyDev 
    ? 'http://localhost:3000' 
    : `file://${path.join(__dirname, '../build/index.html')}`;
  
  mainWindow.loadURL(startUrl);

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    safeLog.log('MainWindow is ready to show');
  });

  // Open DevTools in development
  if (actuallyDev) {
    mainWindow.webContents.openDevTools();
  }

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(async () => {
  safeLog.log('Electron ready - creating window immediately and starting backend in parallel...');
  
  // Create window immediately for better UX
  createWindow();
  
  // Start backend in the background (don't wait for it)
  startBackendInBackground();
  
  // On macOS, re-create window when dock icon is clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Helper function to cleanup old tmp images
async function cleanupOldTmpImages(maxAge = 7 * 24 * 60 * 60 * 1000) {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const files = fs.readdirSync(imagesDir);
    const now = Date.now();
    let deletedCount = 0;

    for (const file of files) {
      // Clean up any image files older than maxAge, but skip screenshot files
      if (!file.startsWith('screenshot-') && 
          (file.endsWith('.png') || file.endsWith('.jpg') || file.endsWith('.jpeg') || 
           file.endsWith('.gif') || file.endsWith('.bmp') || file.endsWith('.webp'))) {
        const filepath = path.join(imagesDir, file);
        const stats = fs.statSync(filepath);
        const age = now - stats.mtime.getTime();
        
        if (age > maxAge) {
          fs.unlinkSync(filepath);
          deletedCount++;
        }
      }
    }

    return {
      success: true,
      deletedCount: deletedCount
    };
  } catch (error) {
    safeLog.error('Failed to cleanup tmp images:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Start backend in background with SQLite (no PGlite needed)
async function startBackendInBackground() {
  safeLog.log('Starting backend server in background...');
  
  try {
    // Mirix backend will automatically use SQLite when PostgreSQL is not available
    safeLog.log('Step 1: Starting backend server with SQLite...');
    await startBackendServer();
    safeLog.log('✅ Backend server started successfully');
    
    safeLog.log('🎉 Backend initialization complete');
    
    // Cleanup old tmp images on startup
    setTimeout(async () => {
      try {
        const result = await cleanupOldTmpImages();
        if (result.success && result.deletedCount > 0) {
          safeLog.log(`Cleaned up ${result.deletedCount} old tmp images on startup`);
        }
      } catch (error) {
        safeLog.error('Failed to cleanup tmp images on startup:', error);
      }
    }, 5000); // Wait 5 seconds after backend starts
    
  } catch (error) {
    safeLog.error('❌ Backend initialization failed:', error);
    safeLog.error('Error details:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
    
    // Show error dialog in production
    if (!actuallyDev) {
      let errorMessage = error.message || 'Unknown error';
      
      // Add more specific error context
      if (error.message && error.message.includes('ECONNREFUSED')) {
        errorMessage = 'Backend server failed to start - connection refused';
      } else if (error.message && error.message.includes('EADDRINUSE')) {
        errorMessage = 'Backend server failed to start - port already in use';
      } else if (error.message && error.message.includes('Backend process exited')) {
        errorMessage = 'Backend server crashed during startup';
      }
      
      dialog.showErrorBox(
        'Backend Startup Error', 
        `Failed to start the backend server: ${errorMessage}`
      );
    }
  }
}

// Quit when all windows are closed
app.on('window-all-closed', () => {
  stopBackendServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Clean up on app quit
app.on('before-quit', () => {
  stopBackendServer();
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});

// IPC handlers for file operations
ipcMain.handle('select-files', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  
  return result.filePaths;
});

// IPC handler for selecting save file path
ipcMain.handle('select-save-path', async (event, options = {}) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: options.title || 'Save File',
    defaultPath: options.defaultName || 'memories_export.xlsx',
    filters: [
      { name: 'Excel Files', extensions: ['xlsx'] },
      { name: 'CSV Files', extensions: ['csv'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  
  return {
    canceled: result.canceled,
    filePath: result.filePath
  };
});

// IPC handler for taking screenshots
ipcMain.handle('take-screenshot', async (event, options = {}) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `screenshot-${timestamp}.png`;
    const filepath = path.join(imagesDir, filename);

    // Take screenshot
    const imgBuffer = await screenshot();
    
    // Save screenshot
    fs.writeFileSync(filepath, imgBuffer);
    
    return {
      success: true,
      filepath: filepath,
      filename: filename,
      size: imgBuffer.length
    };
  } catch (error) {
    safeLog.error('Failed to take screenshot:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC handler for taking screenshot of specific display
ipcMain.handle('take-screenshot-display', async (event, displayId = 0) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `screenshot-display-${displayId}-${timestamp}.png`;
    const filepath = path.join(imagesDir, filename);

    // Get list of displays and take screenshot of specific display
    const displays = await screenshot.listDisplays();
    if (displayId >= displays.length) {
      throw new Error(`Display ${displayId} not found. Available displays: ${displays.length}`);
    }

    const imgBuffer = await screenshot({ screen: displays[displayId].id });
    
    // Save screenshot
    fs.writeFileSync(filepath, imgBuffer);
    
    safeLog.log(`Screenshot of display ${displayId} saved: ${filepath}`);
    
    return {
      success: true,
      filepath: filepath,
      filename: filename,
      size: imgBuffer.length,
      displayId: displayId
    };
  } catch (error) {
    safeLog.error('Failed to take screenshot of display:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC handler for getting available displays
ipcMain.handle('list-displays', async () => {
  try {
    const displays = await screenshot.listDisplays();
    return {
      success: true,
      displays: displays.map((display, index) => ({
        id: display.id,
        index: index,
        name: display.name || `Display ${index + 1}`,
        bounds: display.bounds
      }))
    };
  } catch (error) {
    safeLog.error('Failed to list displays:', error);
    return {
      success: false,
      error: error.message,
      displays: []
    };
  }
});

// IPC handler for cleaning up old screenshots
ipcMain.handle('cleanup-screenshots', async (event, maxAge = 24 * 60 * 60 * 1000) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const files = fs.readdirSync(imagesDir);
    const now = Date.now();
    let deletedCount = 0;

    for (const file of files) {
      if (file.startsWith('screenshot-') && file.endsWith('.png')) {
        const filepath = path.join(imagesDir, file);
        const stats = fs.statSync(filepath);
        const age = now - stats.mtime.getTime();
        
        if (age > maxAge) {
          fs.unlinkSync(filepath);
          deletedCount++;
        }
      }
    }

    return {
      success: true,
      deletedCount: deletedCount
    };
  } catch (error) {
    safeLog.error('Failed to cleanup screenshots:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC handler for reading image as base64 (for similarity comparison)
ipcMain.handle('read-image-base64', async (event, filepath) => {
  try {
    if (!fs.existsSync(filepath)) {
      throw new Error(`File does not exist: ${filepath}`);
    }

    const imageBuffer = fs.readFileSync(filepath);
    const base64Data = imageBuffer.toString('base64');
    const mimeType = 'image/png'; // Assuming PNG format for screenshots
    const dataUrl = `data:${mimeType};base64,${base64Data}`;

    return {
      success: true,
      dataUrl: dataUrl,
      base64: base64Data,
      size: imageBuffer.length
    };
  } catch (error) {
    safeLog.error('Failed to read image as base64:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC handler for deleting screenshot files (used when screenshots are too similar)
ipcMain.handle('delete-screenshot', async (event, filepath) => {
  try {
    if (!fs.existsSync(filepath)) {
      safeLog.warn(`Tried to delete non-existent file: ${filepath}`);
      return {
        success: true, // Consider it successful if file doesn't exist
        message: 'File does not exist'
      };
    }

    // Only allow deletion of files in the screenshots directory for security
    const imagesDir = ensureScreenshotDirectory();
    const normalizedFilepath = path.resolve(filepath);
    const normalizedImagesDir = path.resolve(imagesDir);
    
    if (!normalizedFilepath.startsWith(normalizedImagesDir)) {
      throw new Error('Can only delete files in the screenshots directory');
    }

    fs.unlinkSync(filepath);
    // safeLog.log(`Screenshot deleted (too similar): ${filepath}`);

    return {
      success: true,
      message: 'File deleted successfully'
    };
  } catch (error) {
    safeLog.error('Failed to delete screenshot:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC handler for saving image files to tmp directory
ipcMain.handle('save-image-to-tmp', async (event, sourcePath, filename) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const targetPath = path.join(imagesDir, filename);

    // Check if source file exists
    if (!fs.existsSync(sourcePath)) {
      throw new Error(`Source file does not exist: ${sourcePath}`);
    }

    // Copy the file to the tmp directory
    fs.copyFileSync(sourcePath, targetPath);
    
    safeLog.log(`Image saved to tmp directory: ${targetPath}`);

    return targetPath;
  } catch (error) {
    safeLog.error('Failed to save image to tmp directory:', error);
    throw error;
  }
});

// IPC handler for saving image buffer to tmp directory
ipcMain.handle('save-image-buffer-to-tmp', async (event, arrayBuffer, filename) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const targetPath = path.join(imagesDir, filename);

    // Convert ArrayBuffer to Buffer
    const buffer = Buffer.from(arrayBuffer);
    
    // Write the buffer to file
    fs.writeFileSync(targetPath, buffer);
    
    safeLog.log(`Image buffer saved to tmp directory: ${targetPath}`);

    return targetPath;
  } catch (error) {
    safeLog.error('Failed to save image buffer to tmp directory:', error);
    throw error;
  }
});

// IPC handler for cleaning up old tmp images
ipcMain.handle('cleanup-tmp-images', async (event, maxAge = 7 * 24 * 60 * 60 * 1000) => {
  try {
    const imagesDir = ensureScreenshotDirectory();
    const files = fs.readdirSync(imagesDir);
    const now = Date.now();
    let deletedCount = 0;

    for (const file of files) {
      // Clean up any image files older than maxAge, but skip screenshot files
      if (!file.startsWith('screenshot-') && 
          (file.endsWith('.png') || file.endsWith('.jpg') || file.endsWith('.jpeg') || 
           file.endsWith('.gif') || file.endsWith('.bmp') || file.endsWith('.webp'))) {
        const filepath = path.join(imagesDir, file);
        const stats = fs.statSync(filepath);
        const age = now - stats.mtime.getTime();
        
        if (age > maxAge) {
          fs.unlinkSync(filepath);
          deletedCount++;
        }
      }
    }

    safeLog.log(`Cleaned up ${deletedCount} old tmp images`);

    return {
      success: true,
      deletedCount: deletedCount
    };
  } catch (error) {
    safeLog.error('Failed to cleanup tmp images:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// Handle app protocol for deep linking (optional)
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('mirix', process.execPath, [path.resolve(process.argv[1])]);
  }
} else {
  app.setAsDefaultProtocolClient('mirix');
}

// Create application menu
const createMenu = () => {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Chat',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.send('menu-new-chat');
          }
        },
        {
          label: 'Take Screenshot',
          accelerator: 'CmdOrCtrl+Shift+S',
          click: () => {
            mainWindow.webContents.send('menu-take-screenshot');
          }
        },
        {
          label: 'Open Terminal',
          accelerator: 'CmdOrCtrl+T',
          click: () => {
            mainWindow.webContents.send('menu-open-terminal');
          }
        },
        { type: 'separator' },
        {
          label: 'Quit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectall' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' }
      ]
    }
  ];

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    });
  }

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
};

app.whenReady().then(() => {
  createMenu();
}); 