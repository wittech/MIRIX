const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

class NativeCaptureHelper {
  constructor() {
    this.helperProcess = null;
    this.isRunning = false;
    this.requestQueue = [];
    this.helperPath = null;
  }

  async initialize() {
    console.log('Initializing Native Capture Helper...');
    
    // TEMPORARILY DISABLED: Skip Swift helper to avoid build issues and use enhanced Python approach
    throw new Error('Native capture helper disabled - using enhanced Python fallback');
    
    // Find the helper executable
    this.helperPath = await this.findHelperExecutable();
    if (!this.helperPath) {
      throw new Error('Native capture helper not found');
    }

    // Start the helper process
    await this.startHelper();
    console.log('✅ Native Capture Helper initialized successfully');
  }

  async findHelperExecutable() {
    const possiblePaths = [
      // Development paths
      path.join(__dirname, '../capture-helper/.build/debug/mirix-capture-helper'),
      path.join(__dirname, '../capture-helper/.build/release/mirix-capture-helper'),
      
      // Production paths (in app bundle)
      path.join(process.resourcesPath, 'capture-helper/mirix-capture-helper'),
      path.join(process.resourcesPath, 'app/capture-helper/mirix-capture-helper'),
      
      // Fallback paths
      './capture-helper/mirix-capture-helper',
      '../capture-helper/mirix-capture-helper'
    ];

    for (const helperPath of possiblePaths) {
      if (fs.existsSync(helperPath)) {
        console.log(`Found helper at: ${helperPath}`);
        return helperPath;
      }
    }

    console.log('Helper not found, attempting to build...');
    return await this.buildHelper();
  }

  async buildHelper() {
    const captureHelperDir = path.join(__dirname, '../capture-helper');
    
    if (!fs.existsSync(captureHelperDir)) {
      console.log('❌ Capture helper source directory not found');
      return null;
    }

    return new Promise((resolve, reject) => {
      console.log('Building Swift capture helper...');
      
      const buildProcess = spawn('swift', ['build', '--configuration', 'release'], {
        cwd: captureHelperDir,
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let buildOutput = '';
      let buildError = '';

      buildProcess.stdout.on('data', (data) => {
        buildOutput += data.toString();
      });

      buildProcess.stderr.on('data', (data) => {
        buildError += data.toString();
      });

      buildProcess.on('close', (code) => {
        if (code === 0) {
          console.log('✅ Swift helper built successfully');
          const builtPath = path.join(captureHelperDir, '.build/release/mirix-capture-helper');
          if (fs.existsSync(builtPath)) {
            resolve(builtPath);
          } else {
            reject(new Error('Built helper not found at expected location'));
          }
        } else {
          console.log('❌ Swift helper build failed:');
          console.log('STDOUT:', buildOutput);
          console.log('STDERR:', buildError);
          reject(new Error(`Build failed with code ${code}: ${buildError}`));
        }
      });
    });
  }

  async startHelper() {
    if (this.isRunning) {
      return;
    }

    return new Promise((resolve, reject) => {
      console.log(`Starting helper process: ${this.helperPath}`);
      
      this.helperProcess = spawn(this.helperPath, [], {
        stdio: ['pipe', 'pipe', 'pipe'],
        detached: false
      });

      this.helperProcess.stdout.on('data', (data) => {
        const output = data.toString().trim();
        console.log(`[Swift Helper] ${output}`);
      });

      this.helperProcess.stderr.on('data', (data) => {
        const error = data.toString().trim();
        console.log(`[Swift Helper Error] ${error}`);
      });

      this.helperProcess.on('close', (code) => {
        console.log(`Helper process exited with code ${code}`);
        this.isRunning = false;
        this.helperProcess = null;
      });

      this.helperProcess.on('error', (error) => {
        console.error('Failed to start helper process:', error);
        reject(error);
      });

      // Give the helper a moment to start
      setTimeout(() => {
        if (this.helperProcess && this.helperProcess.pid) {
          this.isRunning = true;
          resolve();
        } else {
          reject(new Error('Helper process failed to start'));
        }
      }, 1000);
    });
  }

  async sendRequest(command, parameters = null) {
    if (!this.isRunning) {
      throw new Error('Helper process not running');
    }

    const request = {
      command: command,
      parameters: parameters
    };

    return new Promise((resolve, reject) => {
      const requestId = Date.now();
      const pipePath = `/tmp/mirix-capture-helper`;
      const responsePath = `/tmp/mirix-capture-helper-response`;

      try {
        // Write request to pipe
        fs.writeFileSync(pipePath, JSON.stringify(request));

        // Wait for response with timeout
        const timeout = setTimeout(() => {
          reject(new Error('Request timeout'));
        }, 10000);

        const checkForResponse = () => {
          if (fs.existsSync(responsePath)) {
            clearTimeout(timeout);
            
            try {
              const responseData = fs.readFileSync(responsePath);
              fs.unlinkSync(responsePath); // Clean up
              
              const response = JSON.parse(responseData.toString());
              
              if (response.success) {
                resolve(response);
              } else {
                reject(new Error(response.error || 'Unknown error'));
              }
            } catch (error) {
              reject(new Error(`Failed to parse response: ${error.message}`));
            }
          } else {
            // Check again after a short delay
            setTimeout(checkForResponse, 100);
          }
        };

        checkForResponse();
      } catch (error) {
        reject(new Error(`Failed to send request: ${error.message}`));
      }
    });
  }

  // High-level methods

  async getAllWindows() {
    try {
      const response = await this.sendRequest('list-windows');
      if (response.dataBase64) {
        const jsonData = Buffer.from(response.dataBase64, 'base64').toString('utf8');
        return JSON.parse(jsonData);
      }
      return [];
    } catch (error) {
      console.error('Failed to get windows from native helper:', error);
      return [];
    }
  }

  async captureWindow(windowId) {
    try {
      const response = await this.sendRequest('capture-window', { windowId });
      if (response.dataBase64) {
        const imageData = Buffer.from(response.dataBase64, 'base64');
        return {
          success: true,
          data: imageData,
          size: imageData.length
        };
      }
      return {
        success: false,
        error: 'No image data received'
      };
    } catch (error) {
      console.error(`Failed to capture window ${windowId}:`, error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  async captureApp(appName) {
    try {
      const response = await this.sendRequest('capture-app', { appName });
      if (response.dataBase64) {
        const imageData = Buffer.from(response.dataBase64, 'base64');
        return {
          success: true,
          data: imageData,
          size: imageData.length
        };
      }
      return {
        success: false,
        error: 'No image data received'
      };
    } catch (error) {
      console.error(`Failed to capture app ${appName}:`, error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  async shutdown() {
    if (this.helperProcess) {
      console.log('Shutting down native capture helper');
      this.helperProcess.kill('SIGTERM');
      this.helperProcess = null;
      this.isRunning = false;
    }
  }
}

module.exports = NativeCaptureHelper;