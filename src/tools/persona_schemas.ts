import { z } from "zod";

/**
 * Arguments for a dynamically named persona activation tool (e.g., a tool named "SIU123").
 * Since the tool's name itself identifies the persona, it may not require additional arguments.
 * This schema can be used when dynamically generating tool definitions in server.ts.
 */
export const ActivateDynamicPersonaArgsSchema = z.object({}).describe(
  "Input for a dynamically named persona activation tool. The specific persona is identified by the tool's name."
);

// Example for a potential future static tool, if dynamic tool names become an issue:
// export const ActivatePersonaArgsSchema = z.object({
//   keyphrase: z.string().describe("The unique keyphrase for the persona to activate (e.g., 'SIU123').")
// });

// You can add other persona-related tool argument schemas here in the future, for example:
// export const ListPersonasArgsSchema = z.object({});
// export const GetPersonaDetailsArgsSchema = z.object({
//   keyphrase: z.string().describe("The keyphrase of the persona to get details for.")
// });