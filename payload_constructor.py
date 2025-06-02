# mcp_persona_selector/payload_constructor.py
from typing import List, Dict, Optional

# Assuming FullPersonaData & LoadedPersonaFileContent are in persona_manager.py
# If your project structure or import paths differ, adjust these imports accordingly.
from .persona_manager import FullPersonaData, LoadedPersonaFileContent

def construct_persona_payload(persona_data: FullPersonaData) -> str:
    """
    Constructs a single, consolidated text payload from the FullPersonaData.
    Each piece of content is clearly demarcated with headers as specified
    in the project outline.

    Args:
        persona_data: A FullPersonaData object containing all loaded information
                      for the activated persona (or team persona).

    Returns:
        A single string representing the consolidated persona context payload.
    """
    payload_parts: List[str] = []

    # General header for the persona context
    # Using persona_id from the manifest as the primary identifier for the persona itself.
    # The keyphrase is how it's activated.
    payload_parts.append(
        f"--- Activated Persona Context: {persona_data.persona_id} (Version: {persona_data.version}) ---"
    )
    payload_parts.append(f"Activation Keyphrase: {persona_data.keyphrase}")

    # 1. Core Operational Rules
    # (requirement to include operational rules)
    if persona_data.operational_rules:
        rules_header = "--- Core Operational Rules ---"
        # Formatting rules as a list for clarity
        rules_content = "\n".join(f"- {rule.strip()}" for rule in persona_data.operational_rules if rule.strip())
        if rules_content: # Only add section if there are non-empty rules
            payload_parts.append(f"{rules_header}\n{rules_content}")

    # 2. Manifest-defined Files Content
    # (requirement to include manifest-defined files)
    if persona_data.manifest_files_content:
        # Could add a general header, but individual file headers might be clearer
        # payload_parts.append("--- Manifest-Defined Files ---")
        for loaded_file in persona_data.manifest_files_content:
            # Using relative_path_in_source_dir which should be relative to persona folder for manifest files
            file_header = (
                f"--- File ({loaded_file.source_description.replace(':', '')}): "
                f"{loaded_file.relative_path_in_source_dir} ---"
            )
            payload_parts.append(f"{file_header}\n{loaded_file.content.strip()}") # strip() to remove leading/trailing whitespace from content

    # 3. Extra Files Content
    # (requirement to include extra knowledge files)
    if persona_data.extra_files_content:
        extra_files_header = "--- Additional Context (Extra Files) ---"
        payload_parts.append(extra_files_header)
        for rel_path, content in persona_data.extra_files_content.items():
            # rel_path here is relative to the Extra_Files directory
            file_specific_header = f"--- Extra File: {rel_path} ---"
            payload_parts.append(f"{file_specific_header}\n{content.strip()}")

    # 4. Chat Log Content
    # (requirement to include latest chat log)
    if persona_data.chat_log_content and persona_data.chat_log_content.strip():
        chat_log_header = "--- Recent Chat Log ---"
        payload_parts.append(f"{chat_log_header}\n{persona_data.chat_log_content.strip()}")
        
    # Join all parts with a double newline for clear separation between sections
    return "\n\n".join(payload_parts).strip() # Final strip for overall cleanliness