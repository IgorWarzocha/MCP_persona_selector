import { internalLoadAndPreparePersonaContext } from '../tools/persona_manager.js';
// Import the schema, even if it's z.object({}), for consistent argument parsing.
// This assumes the server will pass an empty args object for these dynamic tools.
import { ActivateDynamicPersonaArgsSchema } from '../tools/persona_schemas.js';
import { ServerResult } from '../types.js';
import { createErrorResponse } from '../error-handlers.js'; // Assuming you have this for standardized errors

/**
 * Handles the activation of a persona identified by its keyphrase.
 * This function is expected to be called by the main server when a tool name
 * matching a configured persona keyphrase is invoked.
 *
 * @param keyphrase The unique keyphrase identifying the persona to load (e.g., "SIU123").
 * @param args The arguments passed to the tool (expected to be empty for dynamic persona tools).
 * @returns A Promise resolving to a ServerResult containing the persona payload or an error.
 */
export async function handleActivatePersonaByKeyphrase(keyphrase: string, args: unknown): Promise<ServerResult> {
  try {
    // Validate args even if expected to be empty, for consistency and future-proofing
    // The ActivateDynamicPersonaArgsSchema is z.object({}), so it will pass for an empty object.
    ActivateDynamicPersonaArgsSchema.parse(args);

    if (!keyphrase || typeof keyphrase !== 'string' || keyphrase.trim() === '') {
      return createErrorResponse("Invalid or missing persona keyphrase for activation.");
    }

    // Call the core logic function from persona_manager.ts
    return await internalLoadAndPreparePersonaContext(keyphrase);

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`Error in handleActivatePersonaByKeyphrase for keyphrase '${keyphrase}':`, errorMessage);
    // Capture telemetry for this error if you have a capture utility
    // import { capture } from '../utils/capture.js';
    // capture('persona_activation_error', { keyphrase, error: errorMessage });
    return createErrorResponse(`Failed to activate persona '${keyphrase}': ${errorMessage}`);
  }
}

// Example for a future 'list_available_personas' tool handler:
/*
import { configManager } from '../config-manager.js';

export async function handleListAvailablePersonas(): Promise<ServerResult> {
  try {
    const config = await configManager.getConfig();
    const personaActivationMap = config.personaActivationMap || {};
    const availablePersonas = Object.entries(personaActivationMap).map(([keyphrase, details]) => ({
      keyphrase: keyphrase,
      displayName: details.displayName,
      folderName: details.folderName // Be cautious about exposing full paths if not intended
    }));

    if (availablePersonas.length === 0) {
      return { content: [{ type: "text", text: "No personas configured." }] };
    }

    const personaListText = "Available personas (Keyphrase: Display Name):\n" +
      availablePersonas.map(p => `- ${p.keyphrase}: ${p.displayName}`).join("\n");

    return {
      content: [{ type: "text", text: personaListText }],
      _meta: { availablePersonas } // Optionally include structured data for programmatic use by Claude
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Error in handleListAvailablePersonas:', errorMessage);
    return createErrorResponse(`Failed to list available personas: ${errorMessage}`);
  }
}
*/