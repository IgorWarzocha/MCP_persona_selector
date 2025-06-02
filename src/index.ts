#!/usr/bin/env node

import { FilteredStdioServerTransport } from './custom-stdio.js'; // Assuming this is still used
import { server } from './server.js';
// import { commandManager } from './command-manager.js'; // Original has this, may or may not be needed directly here
import { configManager } from './config-manager.js';
import { join, dirname } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import { platform } from 'os';
import { capture } from './utils/capture.js'; // Assuming utils/capture.js exists

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const isWindows = platform() === 'win32';

// Helper function to properly convert file paths to URLs (from original)
function createFileURL(filePath: string): URL {
  if (isWindows) {
    const normalizedPath = filePath.replace(/\\/g, '/');
    if (normalizedPath.startsWith('/')) {
      return new URL(`file://${normalizedPath}`);
    } else {
      return new URL(`file:///${normalizedPath}`);
    }
  } else {
    return pathToFileURL(filePath);
  }
}

async function runSetup() {
  try {
    const setupScriptPath = join(__dirname, '..', 'setup-claude-server.js'); // Adjusted path to be relative to dist/
    const setupScriptUrl = createFileURL(setupScriptPath);

    const { default: setupModule } = await import(setupScriptUrl.href);
    if (typeof setupModule === 'function') {
      await setupModule();
    }
  } catch (error) {
    console.error('Error running setup from index.ts:', error);
    // Decide if this should be a fatal error
  }
}

async function runServer() {
  try {
    // Handle "setup" command if passed (from original)
    if (process.argv[2] === 'setup') {
      await runSetup();
      return;
    }

    const transport = new FilteredStdioServerTransport();

    process.on('uncaughtException', async (error) => {
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (errorMessage.includes('JSON') && errorMessage.includes('Unexpected token')) {
        process.stderr.write(`[mcp-persona-selector] JSON parsing error: ${errorMessage}\n`);
        return;
      }
      await capture('run_server_uncaught_exception', { error: errorMessage });
      process.stderr.write(`[mcp-persona-selector] Uncaught exception: ${errorMessage}\n`);
      process.exit(1);
    });

    process.on('unhandledRejection', async (reason) => {
      const errorMessage = reason instanceof Error ? reason.message : String(reason);
      if (errorMessage.includes('JSON') && errorMessage.includes('Unexpected token')) {
        process.stderr.write(`[mcp-persona-selector] JSON parsing rejection: ${errorMessage}\n`);
        return;
      }
      await capture('run_server_unhandled_rejection', { error: errorMessage });
      process.stderr.write(`[mcp-persona-selector] Unhandled rejection: ${errorMessage}\n`);
      process.exit(1);
    });

    await capture('run_server_start', { project: 'mcp_persona_selector'});

    try {
      console.error("Loading configuration for MCP Persona Selector...");
      await configManager.loadConfig(); // This will initialize config, including persona defaults
      console.error("Configuration loaded successfully.");
    } catch (configError) {
      const errorMessage = configError instanceof Error ? configError.message : String(configError);
      console.error(`Failed to load configuration: ${errorMessage}`);
      console.error(configError instanceof Error && configError.stack ? configError.stack : 'No stack trace available');
      console.error("Continuing with in-memory configuration only.");
      await capture('config_load_error', { error: errorMessage, project: 'mcp_persona_selector'});
    }

    console.error("Connecting MCP Persona Selector server...");
    await server.connect(transport);
    console.error("MCP Persona Selector server connected successfully.");

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`FATAL ERROR starting MCP Persona Selector: ${errorMessage}`);
    console.error(error instanceof Error && error.stack ? error.stack : 'No stack trace available');
    process.stderr.write(JSON.stringify({
      type: 'error',
      timestamp: new Date().toISOString(),
      message: `Failed to start MCP Persona Selector server: ${errorMessage}`
    }) + '\n');
    await capture('run_server_failed_start_error', { error: errorMessage, project: 'mcp_persona_selector'});
    process.exit(1);
  }
}

runServer().catch(async (error) => {
  const errorMessage = error instanceof Error ? error.message : String(error);
  console.error(`RUNTIME ERROR in MCP Persona Selector: ${errorMessage}`);
  console.error(error instanceof Error && error.stack ? error.stack : 'No stack trace available');
  process.stderr.write(JSON.stringify({
    type: 'error',
    timestamp: new Date().toISOString(),
    message: `Fatal error running MCP Persona Selector server: ${errorMessage}`
  }) + '\n');
  await capture('run_server_fatal_error', { error: errorMessage, project: 'mcp_persona_selector'});
  process.exit(1);
});