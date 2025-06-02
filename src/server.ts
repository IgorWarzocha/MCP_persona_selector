import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
    ListResourcesRequestSchema,
    ListPromptsRequestSchema,
    type CallToolRequest,
} from "@modelcontextprotocol/sdk/types.js";
import { zodToJsonSchema } from "zod-to-json-schema";

// Shared constants for tool descriptions (from original file)
const PATH_GUIDANCE = `IMPORTANT: Always use absolute paths (starting with '/' or drive letter like 'C:\\') for reliability. Relative paths may fail as they depend on the current working directory. Tilde paths (~/...) might not work in all contexts. Unless the user explicitly asks for relative paths, use absolute paths.`;
const CMD_PREFIX_DESCRIPTION = `This command can be referenced as "DC: ..." or "use Desktop Commander to ..." in your instructions.`;

import {
    // Existing schemas
    ExecuteCommandArgsSchema,
    ReadOutputArgsSchema,
    ForceTerminateArgsSchema,
    ListSessionsArgsSchema,
    KillProcessArgsSchema,
    ReadFileArgsSchema,
    ReadMultipleFilesArgsSchema,
    WriteFileArgsSchema,
    CreateDirectoryArgsSchema,
    ListDirectoryArgsSchema,
    MoveFileArgsSchema,
    SearchFilesArgsSchema,
    GetFileInfoArgsSchema,
    SearchCodeArgsSchema,
    GetConfigArgsSchema,
    SetConfigValueArgsSchema,
    ListProcessesArgsSchema,
    EditBlockArgsSchema,
    // --- NEW ---
    // Schema for our dynamically generated persona activation tools
    // Assuming ActivateDynamicPersonaArgsSchema is exported from persona_schemas.ts or main schemas.ts
} from './tools/schemas.js'; // Ensure persona_schemas are re-exported via tools/schemas.ts or import directly

// --- NEW ---
// If ActivateDynamicPersonaArgsSchema is in its own file and not re-exported by './tools/schemas.js':
import { ActivateDynamicPersonaArgsSchema } from './tools/persona_schemas.js';
import { configManager } from './config-manager.js'; // To access personaActivationMap
// --- END NEW ---

import { getConfig, setConfigValue } from './tools/config.js'; // Keep existing config tools
import { trackToolCall } from './utils/trackTools.js';
import { VERSION } from './version.js';
import { capture } from "./utils/capture.js";
import * as handlers from './handlers/index.js'; // This will now include persona_handlers
import { ServerResult } from './types.js';

console.error("Loading server.ts for MCP_persona_selector");

export const server = new Server(
    {
        name: "desktop-commander", // Or consider "mcp-persona-selector" if this is its primary new role
        version: VERSION,
    },
    {
        capabilities: {
            tools: {},
            resources: {},
            prompts: {},
        },
    },
);

server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return { resources: [] };
});

server.setRequestHandler(ListPromptsRequestSchema, async () => {
    return { prompts: [] };
});

console.error("Setting up request handlers for MCP_persona_selector...");

server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
        console.error("Generating tools list for MCP_persona_selector...");
        const staticTools = [
            // Configuration tools (keep as is)
            {
                name: "get_config",
                description: `Get the complete server configuration. Includes personasBasePath and personaActivationMap. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(GetConfigArgsSchema),
            },
            {
                name: "set_config_value",
                description: `Set a config value (e.g., personasBasePath, personaActivationMap items). ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(SetConfigValueArgsSchema),
            },
            // Filesystem tools (keep as is)
             {
                name: "read_file",
                description: `Read file contents or URL. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ReadFileArgsSchema),
            },
            {
                name: "read_multiple_files",
                description: `Read multiple files. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ReadMultipleFilesArgsSchema),
            },
            {
                name: "write_file",
                description: `Write or append to file. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(WriteFileArgsSchema),
            },
            {
                name: "create_directory",
                description: `Create a directory. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(CreateDirectoryArgsSchema),
            },
            {
                name: "list_directory",
                description: `List directory contents. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ListDirectoryArgsSchema),
            },
            {
                name: "move_file",
                description: `Move/rename files. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(MoveFileArgsSchema),
            },
            {
                name: "search_files",
                description: `Find files by name. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(SearchFilesArgsSchema),
            },
            {
                name: "search_code",
                description: `Search text in files using ripgrep. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(SearchCodeArgsSchema),
            },
            {
                name: "get_file_info",
                description: `Get file/directory metadata. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(GetFileInfoArgsSchema),
            },
            {
                name: "edit_block",
                description: `Apply surgical text replacements. ${PATH_GUIDANCE} ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(EditBlockArgsSchema),
            },
            // Terminal tools (keep as is)
            {
                name: "execute_command",
                description: `Execute a terminal command. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ExecuteCommandArgsSchema),
            },
            {
                name: "read_output",
                description: `Read output from a running command. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ReadOutputArgsSchema),
            },
            {
                name: "force_terminate",
                description: `Force terminate a command. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ForceTerminateArgsSchema),
            },
            {
                name: "list_sessions",
                description: `List active command sessions. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ListSessionsArgsSchema),
            },
            {
                name: "list_processes",
                description: `List all running processes. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(ListProcessesArgsSchema),
            },
            {
                name: "kill_process",
                description: `Terminate a process by PID. ${CMD_PREFIX_DESCRIPTION}`,
                inputSchema: zodToJsonSchema(KillProcessArgsSchema),
            },
        ];

        // --- NEW: Dynamically add persona activation tools ---
        const dynamicPersonaTools = [];
        const currentConfig = await configManager.getConfig();
        const personaActivationMap = currentConfig.personaActivationMap || {};

        for (const keyphrase in personaActivationMap) {
            if (Object.prototype.hasOwnProperty.call(personaActivationMap, keyphrase)) {
                const personaDetails = personaActivationMap[keyphrase];
                dynamicPersonaTools.push({
                    name: keyphrase, // e.g., "SIU123"
                    description: `Activates the '${personaDetails.displayName}' persona. Subsequent interactions will be guided by this persona. ${CMD_PREFIX_DESCRIPTION}`,
                    // All dynamically generated persona activation tools will use the same empty schema
                    inputSchema: zodToJsonSchema(ActivateDynamicPersonaArgsSchema),
                });
            }
        }
        // --- END NEW ---

        return {
            tools: [...staticTools, ...dynamicPersonaTools],
        };
    } catch (error) {
        console.error("Error in list_tools request handler:", error);
        // Consider capturing this error for telemetry
        capture('server_list_tools_error', { error: error instanceof Error ? error.message : String(error) });
        throw error; // Re-throw to let the MCP SDK handle it or return a default error
    }
});

server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest): Promise<ServerResult> => {
    try {
        const { name, arguments: args } = request.params;

        // --- NEW: Check if the called tool name is a persona activation keyphrase ---
        const currentConfig = await configManager.getConfig(); // Must fetch fresh config
        const personaActivationMap = currentConfig.personaActivationMap || {};

        if (personaActivationMap[name]) { // If 'name' (e.g., "SIU123") is a key in our map
            trackToolCall(name, args); // Track this dynamic tool call
            capture('server_call_tool_persona_activation', { persona_keyphrase: name });
            // Route to the generic persona activation handler, passing the keyphrase
            return await handlers.handleActivatePersonaByKeyphrase(name, args);
        }
        // --- END NEW ---

        // If not a dynamic persona tool, proceed with existing static tool handling
        capture('server_call_tool_static', { tool_name: name });
        trackToolCall(name, args);

        switch (name) {
            // Config tools
            case "get_config":
                return await getConfig(); // No args needed for getConfig from original file
            case "set_config_value":
                return await setConfigValue(args);

            // Terminal tools
            case "execute_command": return await handlers.handleExecuteCommand(args);
            case "read_output": return await handlers.handleReadOutput(args);
            case "force_terminate": return await handlers.handleForceTerminate(args);
            case "list_sessions": return await handlers.handleListSessions(); // No args

            // Process tools
            case "list_processes": return await handlers.handleListProcesses(); // No args
            case "kill_process": return await handlers.handleKillProcess(args);

            // Filesystem tools
            case "read_file": return await handlers.handleReadFile(args);
            case "read_multiple_files": return await handlers.handleReadMultipleFiles(args);
            case "write_file": return await handlers.handleWriteFile(args);
            case "create_directory": return await handlers.handleCreateDirectory(args);
            case "list_directory": return await handlers.handleListDirectory(args);
            case "move_file": return await handlers.handleMoveFile(args);
            case "search_files": return await handlers.handleSearchFiles(args);
            case "search_code": return await handlers.handleSearchCode(args);
            case "get_file_info": return await handlers.handleGetFileInfo(args);
            case "edit_block": return await handlers.handleEditBlock(args);

            default:
                capture('server_unknown_tool', { name });
                return {
                    content: [{ type: "text", text: `Error: Unknown tool: ${name}` }],
                    isError: true,
                };
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        const toolName = request.params.name || "unknown_tool_in_error";
        capture('server_call_tool_error', { tool_name: toolName, error: errorMessage });
        return {
            content: [{ type: "text", text: `Error processing tool '${toolName}': ${errorMessage}` }],
            isError: true,
        };
    }
});