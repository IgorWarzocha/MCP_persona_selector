# TODO for MCP_persona_selector Project

This document outlines the remaining tasks to get the persona management feature functional and suggests next steps for testing and further development.

## 1. Completing Core Project Setup (`MCP_persona_selector`)

These are the foundational files and setup needed for your project, mostly adapted from the original `wonderwhy-er/desktopcommandermcp`.

-   [ ] **Copy Essential Supporting Files:**
    Ensure the following files and directories are copied from the original `wonderwhy-er/desktopcommandermcp` project into the corresponding locations in your `MCP_persona_selector` project. These are generally 1:1 copies or require minimal adaptation:
    -   `MCP_persona_selector/src/config.ts` (defines constants like `CONFIG_FILE_PATH`)

    -   `MCP_persona_selector/src/version.ts` (you will manage the version string)

    -   `MCP_persona_selector/src/types.ts` (shared TypeScript type definitions)

    -   `MCP_persona_selector/src/error-handlers.ts`

    -   `MCP_persona_selector/src/custom-stdio.ts`

    -   `MCP_persona_selector/src/command-manager.ts`

    -   `MCP_persona_selector/src/terminal-manager.ts`

    -   **Existing Tools:** Copy all files from `wonderwhy-er/desktopcommandermcp/src/tools/` (except `persona_manager.ts` and `persona_schemas.ts` which we created) into `MCP_persona_selector/src/tools/`.
    -   **Existing Handlers:** Copy all files from `wonderwhy-er/desktopcommandermcp/src/handlers/` (except `persona_handlers.ts` and `index.ts` which we modified/created) into `MCP_persona_selector/src/handlers/`.
    -   **Utilities:** Copy the entire `wonderwhy-er/desktopcommandermcp/src/utils/` directory into `MCP_persona_selector/src/utils/`.
-   [ ] **Root Project Files:**
    -   Copy `wonderwhy-er/desktopcommandermcp/setup-claude-server.js` to `MCP_persona_selector/setup-claude-server.js`.

        -   Review this script to ensure it aligns with any changes made in your `package.json` (e.g., `bin` commands, project name if referenced).
    -   Create a `.gitignore` file suitable for a Node.js/TypeScript project (e.g., ignoring `node_modules/`, `dist/`, `.env`, log files).
    -   Create/update `README.md` for your `MCP_persona_selector` project, detailing its unique features.
-   [ ] **Version Update:**
    -   Open `MCP_persona_selector/src/version.ts` and set an initial version for your project, for example:
        ```typescript
        export const VERSION = '0.1.0-persona-alpha';
        ```

## 2. User Configuration for Persona Management

This involves setting up your local runtime configuration for `MCP_persona_selector`. These changes are made to the `config.json` file that `MCP_persona_selector` uses (typically located at `~/.claude-server-commander/config.json` on macOS/Linux or `%APPDATA%\\Claude-Server-Commander\\config.json` on Windows - the exact path is defined in your `MCP_persona_selector/src/config.ts`).

-   [ ] **Set `personasBasePath`:**
    Use the `set_config_value` tool (once the server is running) or manually edit your runtime `config.json` to set `personasBasePath`.
    -   **Key:** `personasBasePath`
    -   **Value:** `"G:\\My Drive\\__Persona_Architect_System\\3_Generated_Teams"` (Use double backslashes `\\` for Windows paths in JSON)
-   [ ] **Populate `personaActivationMap`:**
    Again, use `set_config_value` or manually edit the runtime `config.json` to define your persona keyphrases and their corresponding details.
    -   **Key:** `personaActivationMap`
    -   **Value (example):**
        ```json
        {
          "SIU123": {
            "displayName": "Strategic Intelligence Unit (SIU)",
            "folderName": "Strategic Intelligence Unit"
          },
          "JenAI": {
            "displayName": "Jennifer (Lead AI)",
            "folderName": "Individual_Personas/Jen"
          }
          // Add other personas/teams here
        }
        ```
    -   **Note:** `folderName` is relative to your `personasBasePath`. For example, for "SIU123", the tool will look for files in `G:\My Drive\__Persona_Architect_System\3_Generated_Teams\Strategic Intelligence Unit\`.

## 3. Persona Manifest File Creation

For each persona/team you defined in `personaActivationMap`, you need to create a manifest file in its root directory. This manifest guides the `MCP_persona_selector` tool on what files to load for that persona.

-   [ ] **SIU Manifest Example:**
    -   **Location:** `G:\My Drive\__Persona_Architect_System\3_Generated_Teams\Strategic Intelligence Unit\SIU_manifest.json` (or just `manifest.json` if preferred, ensure `persona_manager.ts` logic matches this naming).
    -   **Content Structure (rework your `SIU_Initialization_Prompt_JSON_V1.5.json`):**
        ```json
        {
          "prompt_metadata": {
            "prompt_id": "SIU_Team_Manifest_V1.0", // Or similar
            "version": "1.0",
            "description": "Manifest for the Strategic Intelligence Unit (SIU) team."
          },
          "core_definition_files": [
            {
              "description": "Lead Persona Definition for Jen",
              "base_name": "Jen_Persona",
              "extensions": ["json", "txt"],
              "path": "Team_Files/Jen_Persona.json", // Relative to this persona's root folder
              "required": true
            },
            // ... other core_definition_files entries with 'path'
          ],
          "supporting_definition_files": [ // Optional, or merge into core_definition_files
            {
              "description": "SIU Consolidated SOP",
              "base_name": "SIU_Consolidated_SOP",
              "extensions": ["json", "txt"],
              "path": "Team_Files/SIU_Consolidated_SOP.json",
              "required": true
            }
            // ... other supporting_definition_files entries with 'path'
          ],
          "core_operational_rules": [
            // ... copy from your SIU_Initialization_Prompt_JSON_V1.5.json
          ]
        }
        ```
    -   Ensure all `path` fields in the manifest are correct and relative to the persona's specific root folder (e.g., relative to `G:\My Drive\__Persona_Architect_System\3_Generated_Teams\Strategic Intelligence Unit\`).
-   [ ] Create similar manifest files for any other personas/teams you configure in `personaActivationMap`.

## 4. Building and Testing `MCP_persona_selector`

-   [ ] **Install Dependencies:**
    Navigate to your `MCP_persona_selector` project root in the terminal. If you haven't already after creating `package.json`, run:
    ```bash
    npm install
    ```
-   [ ] **Build Project:**
    Run the build script:
    ```bash
    npm run build
    ```
    This should compile TypeScript to JavaScript in the `dist/` folder.
-   [ ] **Configure Claude Desktop:**
    Ensure Claude Desktop is set up to use your local `MCP_persona_selector` server. If you copied and adapted `setup-claude-server.js`, running `node setup-claude-server.js` (or `npm run setup` if it calls this script) should configure Claude Desktop. Otherwise, you might need to manually edit Claude's `claude_desktop_config.json`.
-   [ ] **Testing:**
    1.  Restart Claude Desktop completely.
    2.  Open the "Search and tools" menu in Claude. Verify that your persona keyphrases (e.g., "SIU123", "JenAI") appear as toggleable tools.
    3.  Enable one of the persona tools (e.g., toggle "SIU123" on).
    4.  In a new chat, give a prompt like: `"SIU123, what are your primary objectives for this session?"` or `"Using SIU123, analyze this project brief: [brief]"`. (The exact invocation might need experimentation based on how Claude interprets the tool name vs. natural language triggers).
    5.  Observe Claude's response. It should have received the persona context from `MCP_persona_selector` and ideally respond according to the SIU persona definitions and rules.
    6.  Check the terminal where your `MCP_persona_selector` server is running (if you started it manually for debugging, e.g., `npm run start:debug`) for any log messages or errors related to persona loading.

## 5. Future Enhancements / Considerations (Post-MVP)

-   [ ] **Tool to List Available Personas:** Implement a `list_available_personas` tool that reads the `personaActivationMap` and informs Claude of the configured personas and their keyphrases.
-   [ ] **Refine Payload:** Experiment with the structure and content of the payload returned to Claude by `internalLoadAndPreparePersonaContext` to optimize Claude's adoption of the persona.
-   [ ] **Error Handling:** Enhance error reporting to Claude if critical persona files are missing or manifests are malformed.
-   [ ] **Security:** Further review security implications, especially around file paths and potential for misconfiguration.
-   [ ] **Dynamic Team Building:** If you decide to revisit this, plan the merging logic and the `build_composite_team` tool.

---
This `TODO.md` should help guide you through the next steps.