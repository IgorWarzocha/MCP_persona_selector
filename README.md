# MCP Persona Selector

## Overview

`MCP_persona_selector` is an enhanced version of the DesktopCommanderMCP server, designed to run locally and integrate with the Claude Desktop application. Its primary purpose is to allow users to define and load different AI personas or "teams" (e.g., "Strategic Intelligence Unit") dynamically.

Claude can then be instructed to adopt these personas, leveraging context and operational rules defined in local files. This is achieved by:
1.  User configuration of persona locations and activation keyphrases.
2.  A manifest file within each persona's directory detailing its constituent files (definitions, knowledge bases, SOPs, etc.).
3.  The `MCP_persona_selector` server dynamically generating "tools" in Claude's UI, where each tool corresponds to a persona's activation keyphrase.
4.  When such a tool is invoked via Claude, the server reads all relevant persona files and provides a consolidated context payload back to Claude.

This system allows for flexible and powerful persona management without direct code changes for each new persona, relying instead on user-defined local file structures and manifests.

## Basic Setup and Usage Guidelines

### 1. Prerequisites
-   Node.js (version 18.0.0 or higher recommended, as per `package.json`).
-   Claude Desktop application.
-   A subscription for Claude that allows tool use.

### 2. Project Installation & Build
-   Clone the `MCP_persona_selector` repository from `https://github.com/IgorWarzocha/MCP_persona_selector`.
-   Navigate to the project root directory.
-   Install dependencies: Run `npm install` (refer to `package.json`).
-   Build the project: Run `npm run build` (this uses `tsc` as configured in `tsconfig.json` to compile files from `src/` to `dist/`).

### 3. Core Configuration (Runtime)
The following configurations need to be set in the runtime `config.json` file used by `MCP_persona_selector` (typically located at `~/.claude-server-commander/config.json` or platform equivalent, path defined in `src/config.ts`). These are managed by `src/config-manager.ts`.

-   **`personasBasePath`**:
    -   Set this to the absolute path of your main directory containing all individual persona/team folders.
    -   Example: `"G:\\My Drive\\__Persona_Architect_System\\3_Generated_Teams"`
-   **`personaActivationMap`**:
    -   Define a JSON object mapping your desired short, unique `keyphrases` to persona details.
    -   Each keyphrase will become a dynamically generated tool name in Claude's UI.
    -   Each entry needs a `displayName` (for human readability) and a `folderName` (the actual name of the persona's subfolder within `personasBasePath`).
    -   Example:
        ```json
        "personaActivationMap": {
          "SIU123": { "displayName": "Strategic Intelligence Unit (SIU)", "folderName": "Strategic Intelligence Unit" },
          "JenAI": { "displayName": "Jennifer (Lead AI)", "folderName": "Individual_Personas/Jen" }
        }
        ```

### 4. Persona Definition Files (User's Responsibility on Local Disk)
For each entry in `personaActivationMap`:
-   Create a corresponding subfolder within your `personasBasePath`.
    -   Example for "SIU123": `G:\My Drive\__Persona_Architect_System\3_Generated_Teams\Strategic Intelligence Unit\`
-   Inside each persona's subfolder, create a **manifest file** (e.g., `SIU_manifest.json` or `manifest.json` - ensure consistency with logic in `src/tools/persona_manager.ts`).
    -   This manifest is a JSON file based on your original `SIU_Initialization_Prompt_JSON_V1.5.json` but reworked to primarily list files and core rules. Refer to the `PersonaManifest` interface defined in `src/tools/persona_manager.ts`.
    -   Key sections: `prompt_metadata`, `core_definition_files`, `supporting_definition_files` (optional), `core_operational_rules`.
    -   Each file entry within `core_definition_files` and `supporting_definition_files` *must* have a `path` attribute specifying its location relative to that persona's root folder (e.g., `"path": "Team_Files/Jen_Persona.json"`).
-   Organize the actual persona definition files (personas, SOPs, KBs) according to the `path` entries in the manifest (e.g., within a `Team_Files/` subdirectory).
-   Place additional, non-manifest knowledge base files into an `Extra_Files/` subdirectory within the persona's folder if this feature is used by `src/tools/persona_manager.ts`.
-   Place relevant chat logs (e.g., `ChatLog_YYYY-MM-DD.json`) in the persona's root folder; the system will attempt to load the latest one.

### 5. Integration with Claude Desktop
-   Run the `setup-claude-server.js` script (located in the `MCP_persona_selector` project root, copied to `dist/` during build) using `node dist/setup-claude-server.js`. This script (adapted from the original DesktopCommanderMCP) should configure your Claude Desktop application to recognize and use your locally running `MCP_persona_selector` server.

### 6. Activating a Persona in Claude
1.  Restart the Claude Desktop application after setup.
2.  The keyphrases you defined in `personaActivationMap` (e.g., "SIU123") should appear as toggleable "tools" in Claude's "Search and tools" interface.
3.  Enable the switch for the desired persona tool.
4.  In your chat with Claude, instruct it to use the persona, for example: "Using SIU123, please outline a plan for project X."
5.  Claude will call the corresponding tool (e.g., "SIU123"). Your `MCP_persona_selector` server (specifically `src/server.ts` routing to `src/handlers/persona_handlers.ts` which uses `src/tools/persona_manager.ts`) will load all files defined in that persona's manifest and return the consolidated context to Claude.
6.  Claude should then respond according to the activated persona's definitions and rules.

### 7. Troubleshooting
-   Check the console output where your `MCP_persona_selector` server is running (e.g., if started with `npm run start` or `npm run start:debug`) for logs and error messages, especially from `src/tools/persona_manager.ts` during the file loading process.
-   Verify paths in `personasBasePath`, `personaActivationMap`, and your manifest files.
-   Ensure JSON files (manifests, persona definitions if JSON) are well-formed.

## Key Internal File References (for Development)

-   **Main Persona Loading Logic:** `MCP_persona_selector/src/tools/persona_manager.ts` (contains `internalLoadAndPreparePersonaContext`).
-   **Server-Side Tool Registration & Routing:** `MCP_persona_selector/src/server.ts` (handles dynamic tool listing and calls to persona activation tools).
-   **Configuration Management for Persona Settings:** `MCP_persona_selector/src/config-manager.ts` (defines how `personasBasePath` and `personaActivationMap` are stored and accessed).
-   **Persona Manifest Structure Guidance:** User's `SIU_Initialization_Prompt_JSON_V1.5.json` serves as the base design. The expected structure for the tool is defined by the `PersonaManifest` interface in `src/tools/persona_manager.ts`.
-   **Persona Activation Handler:** `MCP_persona_selector/src/handlers/persona_handlers.ts`.
-   **Input Schemas (if any for persona tools):** `MCP_persona_selector/src/tools/persona_schemas.ts`.
-   **Project Definition & Scripts:** `MCP_persona_selector/package.json`.
-   **TypeScript Compilation Config:** `MCP_persona_selector/tsconfig.json`.
-   **Server Entry Point:** `MCP_persona_selector/src/index.ts`.