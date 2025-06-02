#!/usr/bin/env node

import { homedir, platform } from 'os';
import { join, dirname } from 'path';
import { readFileSync, writeFileSync, existsSync, appendFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { exec } from "node:child_process";
import { version as nodeVersion } from 'process';
import * as https from 'https';
import { randomUUID } from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const isWindows = platform() === 'win32';

const MCP_PERSONA_SELECTOR_PACKAGE_NAME = "@igorwarzocha/mcp_persona_selector";
const MCP_PERSONA_SELECTOR_DISPLAY_NAME = "MCP Persona Selector";
const MCP_SERVER_CONFIG_KEY = "mcp_persona_selector"; // Matches src/server.ts name

// Google Analytics configuration (Consider replacing with your own IDs if desired)


let uniqueUserId = 'unknown';
try {
    uniqueUserId = randomUUID();
} catch (error) {
    uniqueUserId = `random-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
}

let setupSteps = [];
let setupStartTime = Date.now();

// --- Logging ---
const LOG_FILE_NAME = 'mcp-persona-selector-setup.log';
const LOG_FILE_PATH = join(__dirname, LOG_FILE_NAME); // Log file in the same dir as script (e.g., dist/)

function logToFile(message, isError = false) {
    const timestamp = new Date().toISOString();
    const consolePrefix = isError ? '[MCP_PS_SETUP_ERROR]' : '[MCP_PS_SETUP_INFO]';
    const logMessage = `${timestamp} - ${isError ? 'ERROR: ' : ''}${message}\n`;
    try {
        appendFileSync(LOG_FILE_PATH, logMessage);
        process.stdout.write(`${consolePrefix} ${message}\n`);
    } catch (err) {
        process.stderr.write(`[MCP_PS_SETUP_FATAL] Failed to write to log file: ${err.message}. Log attempted: ${logMessage}\n`);
    }
}

// --- Analytics & Versioning ---
let npmVersionCache = null;
async function getNpmVersion() {
  if (npmVersionCache !== null) return npmVersionCache;
  try {
    return new Promise((resolve) => {
      exec('npm --version', (error, stdout) => {
        if (error) {
          npmVersionCache = 'unknown';
          resolve('unknown');
          return;
        }
        npmVersionCache = stdout.trim();
        resolve(npmVersionCache);
      });
    });
  } catch (error) {
    npmVersionCache = 'unknown';
    return 'unknown';
  }
}

const getAppVersion = async () => {
    try {
        if (process.env.npm_package_version) {
            return process.env.npm_package_version;
        }
        // Assumes setup-claude-server.js and version.js are both in dist/ after build
        const versionFilePath = join(__dirname, 'version.js');
        if (existsSync(versionFilePath)) {
            const { VERSION } = await import(versionFilePath);
            return VERSION || 'unknown';
        }
        const packageJsonPath = join(__dirname, '..', 'package.json'); // package.json is one level up from dist/
        if (existsSync(packageJsonPath)) {
            const packageJsonContent = readFileSync(packageJsonPath, 'utf8');
            const packageJson = JSON.parse(packageJsonContent);
            return packageJson.version || 'unknown';
        }
        return 'unknown';
    } catch (error) {
        logToFile(`Error getting app version: ${error.message}`, true);
        return 'unknown';
    }
};

function detectShell() {
  if (process.platform === 'win32') {
    if (process.env.TERM_PROGRAM === 'vscode') return 'vscode-terminal';
    if (process.env.WT_SESSION) return 'windows-terminal';
    if (process.env.SHELL?.includes('bash')) return 'git-bash'; // Common on Windows for Git
    if (process.env.ComSpec?.toLowerCase().includes('powershell')) return 'powershell';
    if (process.env.PROMPT) return 'cmd';
    if (process.env.WSL_DISTRO_NAME || process.env.WSLENV) return `wsl-${process.env.WSL_DISTRO_NAME || 'unknown'}`;
    return 'windows-unknown';
  }
  if (process.env.SHELL) {
    const shellPath = process.env.SHELL.toLowerCase();
    if (shellPath.includes('bash')) return 'bash';
    if (shellPath.includes('zsh')) return 'zsh';
    if (shellPath.includes('fish')) return 'fish';
    return `unix-${shellPath.split('/').pop() || 'unknown'}`;
  }
  if (process.env.TERM_PROGRAM) return process.env.TERM_PROGRAM.toLowerCase();
  return 'unknown-shell';
}

function getExecutionContext() {
  const isNpx = import.meta.url.includes('_npx') || // Check for npx cache path
                (process.env.npm_config_global !== 'true' && process.env.npm_execpath && process.env.npm_execpath.includes('npx')); // Heuristic for npx
  const isGlobal = process.env.npm_config_global === 'true' || import.meta.url.includes('node_modules/.bin');
  const isNpmScript = !!process.env.npm_lifecycle_script;

  let runMethod = 'direct';
  if (isNpx) runMethod = 'npx';
  else if (isGlobal) runMethod = 'global';
  else if (isNpmScript) runMethod = 'npm_script';

  return {
    runMethod: runMethod,
    isCI: !!process.env.CI || !!process.env.GITHUB_ACTIONS,
    shell: detectShell()
  };
}

async function getTrackingProperties(additionalProps = {}) {
  const propertiesStep = addSetupStep('get_tracking_properties_mcp_ps');
  try {
    const appVersion = await getAppVersion();
    const npmVersion = await getNpmVersion();
    const context = getExecutionContext();

    updateSetupStep(propertiesStep, 'completed');
    return {
      platform: platform(),
      node_version: nodeVersion,
      npm_version: npmVersion,
      execution_context: context.runMethod,
      is_ci: context.isCI,
      shell: context.shell,
      app_name: MCP_PERSONA_SELECTOR_DISPLAY_NAME,
      app_version: appVersion,
      event_source: 'mcp_persona_selector_setup',
      engagement_time_msec: "100",
      ...additionalProps
    };
  } catch (error) {
    updateSetupStep(propertiesStep, 'failed', error);
    return {
      platform: platform(), node_version: nodeVersion,
      error: error.message, engagement_time_msec: "100",
      app_name: MCP_PERSONA_SELECTOR_DISPLAY_NAME,
      event_source: 'mcp_persona_selector_setup',
      ...additionalProps
    };
  }
}

async function trackEvent(eventName, additionalProps = {}) {
    const trackingStep = addSetupStep(`track_event_mcp_ps_${eventName}`);
    if (!GA_MEASUREMENT_ID || !GA_API_SECRET) {
        updateSetupStep(trackingStep, 'skipped', new Error('GA not configured for MCP_PS'));
        return;
    }

    const maxRetries = 2;
    let attempt = 0;
    let lastError = null;

    while (attempt <= maxRetries) {
        try {
            attempt++;
            const eventProperties = await getTrackingProperties(additionalProps);
            const payload = {
                client_id: uniqueUserId,
                non_personalized_ads: false,
                timestamp_micros: Date.now() * 1000,
                events: [{ name: eventName, params: eventProperties }]
            };
            const postData = JSON.stringify(payload);
            const options = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(postData) }
            };

            await new Promise((resolve, reject) => {
                const req = https.request(GA_BASE_URL, options, (res) => {
                    let data = '';
                    res.on('data', (chunk) => data += chunk);
                    res.on('end', () => (res.statusCode >= 200 && res.statusCode < 300) ? resolve({ success: true, data }) : reject(new Error(`HTTP error ${res.statusCode}: ${data}`)));
                });
                req.on('error', reject);
                req.setTimeout(5000, () => { req.destroy(); reject(new Error('Request timeout')); });
                req.write(postData);
                req.end();
            });
            updateSetupStep(trackingStep, 'completed');
            return;
        } catch (error) {
            lastError = error;
            if (attempt <= maxRetries) await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
        }
    }
    updateSetupStep(trackingStep, 'failed', lastError);
}

async function ensureTrackingCompleted(eventName, additionalProps = {}, timeoutMs = 6000) {
    return Promise.race([
        trackEvent(eventName, additionalProps),
        new Promise(resolve => setTimeout(() => resolve(false), timeoutMs))
    ]);
}

process.on('uncaughtException', async (error) => {
    logToFile(`Uncaught Exception: ${error.message}\nStack: ${error.stack}`, true);
    await ensureTrackingCompleted('mcp_ps_setup_uncaught_exception', { error: error.message });
    process.exit(1);
});

process.on('unhandledRejection', async (reason) => {
    const errMessage = reason instanceof Error ? reason.message : String(reason);
    logToFile(`Unhandled Rejection: ${errMessage}`, true);
    await ensureTrackingCompleted('mcp_ps_setup_unhandled_rejection', { error: errMessage });
    process.exit(1);
});


// --- Path Configuration ---
let claudeConfigPath;
const currentOS = platform();
switch (currentOS) {
    case 'win32':
        claudeConfigPath = join(process.env.APPDATA || '', 'Claude', 'claude_desktop_config.json');
        break;
    case 'darwin':
        claudeConfigPath = join(homedir(), 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
        break;
    case 'linux':
        claudeConfigPath = join(homedir(), '.config', 'Claude', 'claude_desktop_config.json');
        break;
    default:
        claudeConfigPath = join(homedir(), '.claude_mcp_ps_desktop_config.json'); // Fallback
        logToFile(`Unsupported OS: ${currentOS}. Using fallback config path: ${claudeConfigPath}`, true);
}

// --- Setup Steps Tracking ---
function addSetupStep(step, status = 'started', error = null) {
    const timestamp = Date.now();
    const newStep = {
        step, status, timestamp,
        timeFromStart: timestamp - setupStartTime,
        error: error ? (error.message || String(error)) : null
    };
    setupSteps.push(newStep);
    return setupSteps.length - 1;
}

function updateSetupStep(index, status, error = null) {
    if (setupSteps[index]) {
        const timestamp = Date.now();
        setupSteps[index].status = status;
        setupSteps[index].completionTime = timestamp;
        setupSteps[index].timeFromStart = timestamp - setupStartTime; // Update duration
        if (error) setupSteps[index].error = error.message || String(error);
    }
}

// --- Helper Functions ---
async function execAsync(command) {
    const execStep = addSetupStep(`exec_mcp_ps_${command.substring(0, 20)}...`);
    return new Promise((resolve, reject) => {
        const actualCommand = isWindows ? `cmd.exe /c ${command}` : command;
        exec(actualCommand, { timeout: 10000 }, (error, stdout, stderr) => {
            if (error) {
                updateSetupStep(execStep, 'failed', error);
                reject(error);
                return;
            }
            updateSetupStep(execStep, 'completed');
            resolve({ stdout, stderr });
        });
    });
}

// --- Claude Restart Logic ---
async function restartClaude() {
    const restartStep = addSetupStep('restart_claude_for_mcp_ps');
    logToFile("Attempting to restart Claude Desktop application...");
    try {
        const currentPlatform = platform();
        await trackEvent('mcp_ps_setup_restart_claude_attempt', { platform: currentPlatform });

        const killStep = addSetupStep('kill_claude_process_for_mcp_ps');
        try {
            if (currentPlatform === "win32") await execAsync(`taskkill /F /IM "Claude.exe"`);
            else if (currentPlatform === "darwin") await execAsync(`killall "Claude"`);
            else if (currentPlatform === "linux") await execAsync(`pkill -f "claude"`); // Common process name
            updateSetupStep(killStep, 'completed');
        } catch (killError) {
            updateSetupStep(killStep, 'no_process_found', killError);
            logToFile("Claude process not found or could not be terminated. This is often okay if Claude wasn't running.", false);
        }

        await new Promise((resolve) => setTimeout(resolve, 3000)); // Wait for process to terminate

        const startStep = addSetupStep('start_claude_process_for_mcp_ps');
        if (currentPlatform === "darwin") {
            await execAsync(`open -a "Claude"`);
            logToFile("Claude restarted (macOS).");
            updateSetupStep(startStep, 'completed');
        } else if (currentPlatform === "linux") {
            await execAsync(`claude &`); // Start in background
            logToFile("Attempted to restart Claude (Linux). Check if it launched successfully.");
            updateSetupStep(startStep, 'completed');
        } else { // Windows or other
            logToFile("Automatic Claude restart is not supported on this platform. Please restart Claude manually.");
            updateSetupStep(startStep, 'skipped_manual_restart_needed');
        }
        updateSetupStep(restartStep, 'completed_with_notes');
         await trackEvent('mcp_ps_setup_restart_claude_success', { platform: currentPlatform });

    } catch (error) {
        updateSetupStep(restartStep, 'failed', error);
        await trackEvent('mcp_ps_setup_restart_claude_error', { error: error.message });
        logToFile(`Failed to fully restart Claude: ${error.message}. Please restart it manually.`, true);
        logToFile("If Claude Desktop is not installed, download from https://claude.ai/download", false);
    }
}

// --- Main Setup Function ---
export default async function setup() {
    await ensureTrackingCompleted('mcp_ps_setup_function_started', {
        argv: process.argv.join(' '),
        start_time: new Date().toISOString()
    });
    setupStartTime = Date.now(); // Reset start time for more accurate step timings

    const setupOverallStep = addSetupStep('main_mcp_ps_setup');
    const debugMode = process.argv.includes('--debug-mcp-ps'); // Specific debug flag

    console.log('\n');
    console.log(`Setting up ${MCP_PERSONA_SELECTOR_DISPLAY_NAME} for Claude Desktop...`);
    console.log('\n');

    if (debugMode) {
        logToFile('Debug mode enabled for MCP Persona Selector setup.');
        await trackEvent('mcp_ps_setup_debug_mode', { enabled: true });
    }

    try {
        const configDirStep = addSetupStep('check_claude_config_directory_mcp_ps');
        const claudeConfigDir = dirname(claudeConfigPath);
        try {
            if (!existsSync(claudeConfigDir)) {
                logToFile(`Claude config directory not found. Creating: ${claudeConfigDir}`);
                mkdirSync(claudeConfigDir, { recursive: true });
            }
            updateSetupStep(configDirStep, 'completed');
        } catch (dirError) {
            updateSetupStep(configDirStep, 'failed', dirError);
            throw dirError; // Critical failure
        }

        const configFileStep = addSetupStep('read_claude_config_file_mcp_ps');
        let claudeDesktopConfig;
        if (existsSync(claudeConfigPath)) {
            try {
                claudeDesktopConfig = JSON.parse(readFileSync(claudeConfigPath, 'utf8'));
                updateSetupStep(configFileStep, 'read_existing');
            } catch (parseError) {
                logToFile(`Error parsing existing Claude config: ${parseError.message}. Creating new default config.`, true);
                claudeDesktopConfig = {}; // Start fresh
                updateSetupStep(configFileStep, 'parse_error_creating_new');
            }
        } else {
            logToFile(`Claude config file not found at: ${claudeConfigPath}. Creating new config.`);
            claudeDesktopConfig = {};
            updateSetupStep(configFileStep, 'creating_new');
        }

        const appVersion = await getAppVersion();
        logToFile(`${MCP_PERSONA_SELECTOR_DISPLAY_NAME} version: ${appVersion}`);

        const isRunningFromNpx = import.meta.url.includes('_npx') || (process.env.npm_execpath && process.env.npm_execpath.includes('npx'));
        // If this script (setup-claude-server.js) is in dist/, then the main server script (index.js) is also in dist/
        const mainServerScriptPath = join(__dirname, 'index.js');

        let serverConfigEntry;
        const serverArgs = [];

        if (debugMode) {
            serverArgs.push("--inspect-brk=9230"); // Using a different port in case default 9229 is in use
        }
        
        if (isRunningFromNpx) {
             serverArgs.push(`${MCP_PERSONA_SELECTOR_PACKAGE_NAME}@${appVersion || 'latest'}`);
             serverConfigEntry = {
                "command": isWindows ? "npx.cmd" : "npx",
                "args": serverArgs
            };
        } else { // Local/global package install or dev environment
            serverArgs.push(mainServerScriptPath.replace(/\\/g, '\\\\'));
            serverConfigEntry = {
                "command": "node",
                "args": serverArgs
            };
        }
        
        if (debugMode) {
            serverConfigEntry.command = isWindows ? "node.exe" : "node"; // Ensure node is used for --inspect-brk
            // Prepend --inspect-brk to args if not already there (for local case where node is explicit)
            if (serverConfigEntry.args[0] !== "--inspect-brk=9230") {
                 serverConfigEntry.args.unshift("--inspect-brk=9230");
            }
            serverConfigEntry.env = { "NODE_OPTIONS": "--trace-warnings", "DEBUG": "*" };
            logToFile(`Debug mode: Server command will be: ${serverConfigEntry.command} ${serverConfigEntry.args.join(' ')}`);
        }


        if (!claudeDesktopConfig.mcpServers) {
            claudeDesktopConfig.mcpServers = {};
        }
        claudeDesktopConfig.mcpServers[MCP_SERVER_CONFIG_KEY] = serverConfigEntry;

        const writeConfigStep = addSetupStep('write_claude_config_file_mcp_ps');
        try {
            writeFileSync(claudeConfigPath, JSON.stringify(claudeDesktopConfig, null, 2), 'utf8');
            updateSetupStep(writeConfigStep, 'completed');
            logToFile(`✅ ${MCP_PERSONA_SELECTOR_DISPLAY_NAME} (v${appVersion}) successfully configured in Claude Desktop.`);
            logToFile(`Claude config location: ${claudeConfigPath}`);
        } catch (writeError) {
            updateSetupStep(writeConfigStep, 'failed', writeError);
            throw writeError; // Critical failure
        }

        await restartClaude();

        logToFile(`\n✅ ${MCP_PERSONA_SELECTOR_DISPLAY_NAME} setup complete!`);
        logToFile(`The server is available as "${MCP_SERVER_CONFIG_KEY}" in Claude's MCP server list.`);
        logToFile("Future updates will install automatically if you used npx with @latest or a version range.");
        logToFile("If installed globally, update with: npm install -g @igorwarzocha/mcp_persona_selector@latest");
        logToFile("\n💬 Need help or found an issue? Visit: https://github.com/IgorWarzocha/MCP_persona_selector/issues\n");

        updateSetupStep(setupOverallStep, 'completed');
        await ensureTrackingCompleted('mcp_ps_setup_final_success', {
            total_steps: setupSteps.length,
            total_time_ms: Date.now() - setupStartTime,
            app_version: appVersion
        });

    } catch (error) {
        logToFile(`❌ Error during ${MCP_PERSONA_SELECTOR_DISPLAY_NAME} setup: ${error.message}`, true);
        if (error.stack) logToFile(`Stack: ${error.stack}`, true);
        updateSetupStep(setupOverallStep, 'failed', error);
        await ensureTrackingCompleted('mcp_ps_setup_fatal_error', {
            error: error.message,
            error_stack: error.stack,
            total_steps: setupSteps.length,
            failed_step_info: JSON.stringify(setupSteps.find(s => s.status === 'failed') || {})
        });
        process.exitCode = 1; // Indicate failure
    }
}

// Execute setup if run directly
if (import.meta.url === `file://${__filename}` || import.meta.url === `file:///${__filename.replace(/\\/g, '/')}`) {
    setup().catch(async (error) => {
        // Final catch-all, error should have been logged by setup()
        // This ensures process exits with error code if setup promise rejects unexpectedly
        if (!process.exitCode) process.exitCode = 1;
    });
}