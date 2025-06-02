import fs from "fs/promises";
import path from "path";
import { configManager, ServerConfig } from '../config-manager.js'; // Adjusted path
import { ServerResult } from '../types.js'; // Adjusted path

// Interface for a file entry within the manifest
interface PersonaFileEntry {
  description: string;
  base_name: string;
  extensions: string[];
  path: string; // Relative path from the persona's specific root directory
  version_policy?: string;
  date_policy?: string;
  required: boolean;
  content?: string;
}

// Interface for the persona manifest structure
interface PersonaManifest {
  prompt_metadata: {
    prompt_id: string;
    version: string;
    description?: string;
  };
  core_definition_files: PersonaFileEntry[];
  supporting_definition_files?: PersonaFileEntry[];
  core_operational_rules: any[];
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
  let manifestPath = path.join(personaRootDir, `${personaConfig.folderName}_manifest.json`);
  let manifest: PersonaManifest;

  try {
    const manifestContent = await fs.readFile(manifestPath, 'utf-8');
    manifest = JSON.parse(manifestContent);
  } catch (e) { // First catch block for primary manifest
    manifestPath = path.join(personaRootDir, `manifest.json`); // Fallback manifest name
    try {
        const manifestContent = await fs.readFile(manifestPath, 'utf-8');
        manifest = JSON.parse(manifestContent);
    } catch (e2) { // This is where e2 was 'unknown'
      let detailMessage = "Unknown error during manifest loading.";
      if (e2 instanceof Error) {
        detailMessage = e2.message;
      } else if (typeof e2 === 'string') {
        detailMessage = e2;
      }
      // Original line causing error: src/tools/persona_manager.ts:84:280
      return { content: [{ type: "text", text: `Error: Could not load or parse manifest for persona '${personaConfig.displayName}' (Keyphrase: ${personaKeyphrase}). Tried ${path.join(personaRootDir, `${personaConfig.folderName}_manifest.json`)} and ${manifestPath}. Details: ${detailMessage}` }], isError: true };
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
    } catch (e) { // This is where e was 'unknown'
      let fileLoadErrorMessage = "Unknown error loading file.";
      if (e instanceof Error) {
        fileLoadErrorMessage = e.message;
      } else if (typeof e === 'string') {
        fileLoadErrorMessage = e;
      }
      loadedFilesReport.push({ ...fileEntry, status: fileEntry.required ? 'missing_required' : 'missing_optional', actualPathAttempted: filePath });
      // Original line causing error: src/tools/persona_manager.ts:106:107
      console.warn(`Could not load file for persona '${personaConfig.displayName}': ${filePath}. Error: ${fileLoadErrorMessage}`);
    }
  }

  const extraFilesDir = path.join(personaRootDir, "Extra_Files");
  const additionalKnowledge: AdditionalKnowledgeFile[] = [];
  try {
    const extraDirContents = await fs.readdir(extraFilesDir);
    for (const fileName of extraDirContents) {
      const filePath = path.join(extraFilesDir, fileName);
      const content = await fs.readFile(filePath, 'utf-8');
      additionalKnowledge.push({ fileName, content, path: filePath });
    }
  } catch (e) { // This is where e was 'unknown'
    let extraFilesErrorMessage = "Unknown error reading Extra_Files.";
    if (e instanceof Error) {
      extraFilesErrorMessage = e.message;
    } else if (typeof e === 'string') {
      extraFilesErrorMessage = e;
    }
    // Original line causing error: src/tools/persona_manager.ts:121:90
    console.warn(`Could not read Extra_Files for persona ${personaConfig.displayName}: ${extraFilesErrorMessage}`);
  }

  let chatLogData: ChatLogFile | null = null;
  try {
    const personaRootContents = await fs.readdir(personaRootDir);
    const chatLogRegex = /^ChatLog_(\d{4}-\d{2}-\d{2}).*(\.json|\.txt)$/i;
    let latestLogFile: string | null = null;
    let latestDate: Date | null = null;

    for (const fileName of personaRootContents) {
      const match = fileName.match(chatLogRegex);
      if (match) {
        const dateStr = match[1];
        try {
            const fileDate = new Date(dateStr);
            if (!isNaN(fileDate.getTime())) {
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
  } catch (e) { // This is where e was 'unknown'
    let chatLogErrorMessage = "Unknown error loading chat log.";
    if (e instanceof Error) {
      chatLogErrorMessage = e.message;
    } else if (typeof e === 'string') {
      chatLogErrorMessage = e;
    }
    // Original line causing error: src/tools/persona_manager.ts:155:87
    console.warn(`Could not load chat log for persona ${personaConfig.displayName}: ${chatLogErrorMessage}`);
  }
  
  const criticalFilesMissing = loadedFilesReport.some(f => f.status === 'missing_required');
  const optionalFilesMissing = loadedFilesReport.some(f => f.status === 'missing_optional');
  let overallStatus = "success";
  if (criticalFilesMissing) {
    overallStatus = "failure_critical_missing";
  } else if (optionalFilesMissing) {
    overallStatus = "partial_optional_missing";
  }

  let definitionPromptSummary = `Persona Activated: ${personaConfig.displayName}\n\n`;
  loadedFilesReport.forEach(file => {
      if (file.status === 'loaded' && file.content) {
          definitionPromptSummary += `--- ${file.description} (${file.base_name}) ---\n${file.content}\n\n`;
      }
  });
  if (chatLogData) {
    definitionPromptSummary += `--- Chat Log (${chatLogData.fileName}) ---\n${chatLogData.content}\n\n`;
  }
  additionalKnowledge.forEach(kb => {
    definitionPromptSummary += `--- Additional Knowledge (${kb.fileName}) ---\n${kb.content}\n\n`;
  });
  definitionPromptSummary += "--- Core Operational Rules ---\n" + JSON.stringify(manifest.core_operational_rules, null, 2);

  // This payload is primarily for structured return if needed, or debugging.
  // The main context for Claude is definitionPromptSummary.
  // const personaPayloadForStructuredReturn = { 
  //   activated_persona_keyphrase: personaKeyphrase,
  //   // ... (other fields as previously defined)
  // };

  return {
    content: [{ 
        type: "text", 
        text: definitionPromptSummary 
    }]
  };
}
