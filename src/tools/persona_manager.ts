import fs from "fs/promises";
import path from "path";
import { configManager, ServerConfig } from '../config-manager.js'; // Adjusted path
import { ServerResult } from '../types.js'; // Adjusted path

// Interface for a file entry within the manifest
interface PersonaFileEntry {
  description: string;
  base_name: string;
  extensions: string[]; // Kept for compatibility with original prompt, though path is primary
  path: string; // Relative path from the persona's specific root directory (e.g., "Team_Files/Jen_Persona.json")
  version_policy?: string; // Optional, for compatibility
  date_policy?: string; // Optional, for compatibility
  required: boolean;
  content?: string; // To store loaded content after reading
}

// Interface for the persona manifest structure (reworked from SIU_Initialization_Prompt_JSON_V1.5.json)
interface PersonaManifest {
  prompt_metadata: {
    prompt_id: string;
    version: string;
    description?: string; // A brief description of the persona/team
  };
  core_definition_files: PersonaFileEntry[]; // Combined core and supporting files here
  supporting_definition_files?: PersonaFileEntry[]; // Or keep separate if preferred
  core_operational_rules: any[]; // Keep as is from original prompt
  // Add other relevant fields from your SIU_Initialization_Prompt if needed
}

interface LoadedFileReport extends Partial<PersonaFileEntry> {
    status: 'loaded' | 'missing_required' | 'missing_optional';
    actualPathAttempted?: string;
}

interface AdditionalKnowledgeFile {
    fileName: string;
    content: string;
    path: string;
}

interface ChatLogFile {
    fileName: string;
    content: string;
    path: string;
}

/**
 * Loads persona context based on a keyphrase.
 * This is the core function called by persona activation handlers.
 * @param personaKeyphrase The unique keyphrase for the persona (e.g., "SIU123").
 * @returns A Promise resolving to a ServerResult containing the persona payload.
 */
export async function internalLoadAndPreparePersonaContext(personaKeyphrase: string): Promise<ServerResult> {
  const config = await configManager.getConfig();
  const personasBasePath = config.personasBasePath;
  const personaActivationMap = config.personaActivationMap;

  if (!personasBasePath) {
    return { content: [{ type: "text", text: "Error: personasBasePath is not configured in DesktopCommanderMCP." }], isError: true };
  }
  if (!personaActivationMap || !personaActivationMap[personaKeyphrase]) {
    return { content: [{ type: "text", text: `Error: Persona keyphrase '${personaKeyphrase}' not found in personaActivationMap configuration.` }], isError: true };
  }

  const personaConfig = personaActivationMap[personaKeyphrase];
  const personaRootDir = path.join(personasBasePath, personaConfig.folderName);
  // Assuming manifest is named after the folderName or a standard name like 'manifest.json'
  // For this example, let's assume '[folderName]_manifest.json' or 'manifest.json'
  // We will try '[folderName]_manifest.json' first, then 'manifest.json'
  let manifestPath = path.join(personaRootDir, `${personaConfig.folderName}_manifest.json`);
  let manifest: PersonaManifest;

  try {
    const manifestContent = await fs.readFile(manifestPath, 'utf-8');
    manifest = JSON.parse(manifestContent);
  } catch (e) {
    // Try 'manifest.json' as a fallback
    manifestPath = path.join(personaRootDir, `manifest.json`);
    try {
        const manifestContent = await fs.readFile(manifestPath, 'utf-8');
        manifest = JSON.parse(manifestContent);
    } catch (e2) {
        return { content: [{ type: "text", text: `Error: Could not load or parse manifest for persona '${personaConfig.displayName}' (Keyphrase: ${personaKeyphrase}). Tried ${path.join(personaRootDir, `${personaConfig.folderName}_manifest.json`)} and ${manifestPath}. Details: ${e2.message}` }], isError: true };
    }
  }

  const loadedFilesReport: LoadedFileReport[] = [];
  const allFilesToLoad: PersonaFileEntry[] = [
    ...(manifest.core_definition_files || []),
    ...(manifest.supporting_definition_files || [])
  ];

  for (const fileEntry of allFilesToLoad) {
    if (!fileEntry.path) {
        console.warn(`Manifest entry for '${fileEntry.description}' is missing 'path'. Skipping.`);
        loadedFilesReport.push({ ...fileEntry, status: fileEntry.required ? 'missing_required' : 'missing_optional', actualPathAttempted: 'Unknown (path missing in manifest)' });
        continue;
    }
    const filePath = path.join(personaRootDir, fileEntry.path);
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      loadedFilesReport.push({ ...fileEntry, content, status: "loaded", actualPathAttempted: filePath });
    } catch (e) {
      loadedFilesReport.push({ ...fileEntry, status: fileEntry.required ? 'missing_required' : 'missing_optional', actualPathAttempted: filePath });
      console.warn(`Could not load file for persona '${personaConfig.displayName}': ${filePath}. Error: ${e.message}`);
    }
  }

  // Load additional knowledge files
  const extraFilesDir = path.join(personaRootDir, "Extra_Files");
  const additionalKnowledge: AdditionalKnowledgeFile[] = [];
  try {
    const extraDirContents = await fs.readdir(extraFilesDir);
    for (const fileName of extraDirContents) {
      const filePath = path.join(extraFilesDir, fileName);
      const content = await fs.readFile(filePath, 'utf-8');
      additionalKnowledge.push({ fileName, content, path: filePath });
    }
  } catch (e) {
    console.warn(`Could not read Extra_Files for persona ${personaConfig.displayName}: ${e.message}`);
  }

  // Load latest chat log
  let chatLogData: ChatLogFile | null = null;
  try {
    const personaRootContents = await fs.readdir(personaRootDir);
    const chatLogRegex = /^ChatLog_(\d{4}-\d{2}-\d{2}).*(\.json|\.txt)$/i; // Flexible extensions
    let latestLogFile: string | null = null;
    let latestDate: Date | null = null;

    for (const fileName of personaRootContents) {
      const match = fileName.match(chatLogRegex);
      if (match) {
        const dateStr = match[1];
        try {
            const fileDate = new Date(dateStr);
            if (!isNaN(fileDate.getTime())) { // Check if date is valid
                if (!latestDate || fileDate.getTime() > latestDate.getTime()) {
                    latestDate = fileDate;
                    latestLogFile = fileName;
                }
            }
        } catch (dateErr) {
            console.warn(`Invalid date format in chat log filename: ${fileName}`);
        }
      }
    }
    if (latestLogFile) {
      const logPath = path.join(personaRootDir, latestLogFile);
      const content = await fs.readFile(logPath, 'utf-8');
      chatLogData = { fileName: latestLogFile, content, path: logPath };
    }
  } catch (e) {
    console.warn(`Could not load chat log for persona ${personaConfig.displayName}: ${e.message}`);
  }

  const criticalFilesMissing = loadedFilesReport.some(f => f.status === 'missing_required');
  const optionalFilesMissing = loadedFilesReport.some(f => f.status === 'missing_optional');
  let overallStatus = "success";
  if (criticalFilesMissing) {
    overallStatus = "failure_critical_missing";
  } else if (optionalFilesMissing) {
    overallStatus = "partial_optional_missing";
  }

  // Consolidate definition file content for the system prompt
  // This is a simplified example; you might want more sophisticated concatenation
  let definitionPromptSummary = `Persona Activated: ${personaConfig.displayName}\n\n`;
  loadedFilesReport.forEach(file => {
      if (file.status === 'loaded' && file.content) {
          definitionPromptSummary += `--- <span class="math-inline">\{file\.description\} \(</span>{file.base_name}) ---\n${file.content}\n\n`;
      }
  });
  if (chatLogData) {
    definitionPromptSummary += `--- Chat Log (<span class="math-inline">\{chatLogData\.fileName\}\) \-\-\-\\n</span>{chatLogData.content}\n\n`;
  }
  additionalKnowledge.forEach(kb => {
    definitionPromptSummary += `--- Additional Knowledge (<span class="math-inline">\{kb\.fileName\}\) \-\-\-\\n</span>{kb.content}\n\n`;
  });
  definitionPromptSummary += "--- Core Operational Rules ---\n" + JSON.stringify(manifest.core_operational_rules, null, 2);


  const personaPayload = {
    activated_persona_keyphrase: personaKeyphrase,
    persona_display_name: personaConfig.displayName,
    status: overallStatus,
    loaded_files_report: loadedFilesReport.map(f => ({description: f.description, base_name: f.base_name, path: f.path, status: f.status, required: f.required, actualPathAttempted: f.actualPathAttempted})),
    additional_knowledge_loaded: additionalKnowledge.map(f => ({fileName: f.fileName, path: f.path})),
    chat_log_loaded: chatLogData ? {fileName: chatLogData.fileName, path: chatLogData.path} : null,
    // Full content for Claude to process:
    full_context_for_claude: {
        persona_definitions: loadedFilesReport.filter(f => f.status === 'loaded').map(f => ({description: f.description, base_name: f.base_name, content: f.content})),
        additional_knowledge: additionalKnowledge,
        chat_log: chatLogData,
        core_operational_rules: manifest.core_operational_rules
    },
    // A more concise summary prompt string that Claude can use directly
    system_prompt_string_for_claude: definitionPromptSummary 
  };

  return {
    content: [{ 
        type: "text", 
        // Return the full context string for Claude to adopt the persona.
        // Claude will receive this entire string as the tool's output.
        text: definitionPromptSummary 
    }
    // Optionally, also include the structured JSON payload for more complex processing by Claude if it supports it,
    // or for your own debugging when Claude shows the tool output.
    // , { type: "json_object", text: JSON.stringify(personaPayload, null, 2) } // Or just 'data: personaPayload' if your MCP SDK supports it
    ]
  };
}