# mcp_persona_selector/persona_manager.py
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .schemas import AppConfig, PersonaManifest, FileEntry
from .file_handler import (
    load_file_content_from_entry,
    load_extra_files_content,
    load_latest_chat_log,
    FileHandlerError  # To catch errors from file_handler
)

class LoadedPersonaFileContent(BaseModel):
    """Represents the content of a loaded file along with its source description and path."""
    source_description: str
    # relative_path is relative to the specific persona's folder for manifest files,
    # or relative to the Extra_Files folder for extra files.
    relative_path_in_source_dir: Path 
    content: str
    is_required: bool # From the FileEntry, if applicable

class FullPersonaData(BaseModel):
    """
    Aggregates all data loaded for a specific persona, ready for payload construction.
    """
    keyphrase: str
    persona_id: str
    version: str
    operational_rules: List[str] = Field(default_factory=list)
    # Content from files defined in the manifest
    manifest_files_content: List[LoadedPersonaFileContent] = Field(default_factory=list)
    # Content from the Extra_Files directory
    # Keys are relative paths from within the Extra_Files directory
    extra_files_content: Dict[Path, str] = Field(default_factory=dict) 
    # Content of the latest chat log
    chat_log_content: Optional[str] = None
    # Optionally store the raw manifest for reference during payload construction or other steps
    # raw_manifest: PersonaManifest 

class PersonaManagerError(Exception):
    """Custom exception for errors during persona data aggregation."""
    pass

def load_full_persona_data(
    keyphrase: str,
    manifest: PersonaManifest,
    app_config: AppConfig
) -> FullPersonaData:
    """
    Loads all data for a specified persona, including manifest-defined files,
    extra files, and the latest chat log.

    Args:
        keyphrase: The activation keyphrase for the persona.
        manifest: The loaded PersonaManifest for this persona.
        app_config: The loaded application configuration.

    Returns:
        A FullPersonaData object containing all loaded information for the persona.

    Raises:
        PersonaManagerError: If critical data cannot be loaded or persona folder is not found.
    """
    persona_activation_detail = app_config.personaActivationMap.get(keyphrase)
    if not persona_activation_detail:
        # This case should ideally be caught by discover_and_load_personas if manifest is pre-loaded
        # Or by an earlier check if calling this function directly with a keyphrase
        raise PersonaManagerError(f"Keyphrase '{keyphrase}' not found in personaActivationMap.")

    persona_folder_name = persona_activation_detail.folderName
    persona_folder_path = (app_config.personasBasePath / persona_folder_name).resolve()

    if not persona_folder_path.exists() or not persona_folder_path.is_dir():
        raise PersonaManagerError(
            f"Persona folder '{persona_folder_name}' for keyphrase '{keyphrase}' not found at "
            f"{persona_folder_path} or is not a directory."
        )

    loaded_manifest_files: List[LoadedPersonaFileContent] = []

    # Helper to process a list of FileEntry objects
    def _process_file_entries(
        file_entries: List[FileEntry], 
        category_description_prefix: str
    ):
        for file_entry in file_entries:
            try:
                content = load_file_content_from_entry(persona_folder_path, file_entry)
                if content is not None:
                    # Try to determine a representative file extension from those tried
                    # This is for the relative_path_in_source_dir display
                    # Note: load_file_content_from_entry doesn't return which extension succeeded.
                    # We'll just show the first one for now or the base_name.
                    # A more robust way would be for load_file_content_from_entry to return the Path it successfully loaded.
                    # For now, constructing a representative path.
                    
                    # Construct a plausible relative path for LoadedPersonaFileContent
                    # based on file_entry.path_relative_to_persona_folder and file_entry.base_name
                    # The FileEntry's path_relative_to_persona_folder is a stem.
                    # We need to add the base_name and an extension.
                    # For simplicity, using the first extension listed.
                    ext_to_use = file_entry.extensions_to_try[0] if file_entry.extensions_to_try else ""
                    if ext_to_use and not ext_to_use.startswith('.'):
                        ext_to_use = f".{ext_to_use}"
                    
                    # The path_relative_to_persona_folder in FileEntry should be the directory part
                    # and base_name is the filename without extension.
                    # If path_relative_to_persona_folder already includes the base name (as a stem),
                    # then this logic needs slight adjustment.
                    # Based on current file_handler, path_relative_to_persona_folder is the stem.
                    # So, for display, we just need to add an extension to it.
                    # This is mainly for logging/payload construction path info.
                    display_path = file_entry.path_relative_to_persona_folder.with_name(
                        f"{file_entry.base_name}{ext_to_use}"
                    )


                    loaded_manifest_files.append(
                        LoadedPersonaFileContent(
                            source_description=f"{category_description_prefix}: {file_entry.description}",
                            relative_path_in_source_dir=display_path,
                            content=content,
                            is_required=file_entry.is_required_flag
                        )
                    )
                elif file_entry.is_required_flag:
                    raise PersonaManagerError( # This error might be redundant if load_file_content_from_entry raises
                        f"Critical {category_description_prefix.lower()} file '{file_entry.base_name}' for persona '{manifest.persona_id}' could not be loaded."
                    )
            except FileHandlerError as e:
                if file_entry.is_required_flag:
                    raise PersonaManagerError(
                        f"Failed to load required {category_description_prefix.lower()} file '{file_entry.base_name}' for persona '{manifest.persona_id}': {e}"
                    )
                else:
                    print(f"Warning: Optional {category_description_prefix.lower()} file '{file_entry.base_name}' for persona '{manifest.persona_id}' not loaded: {e}")

    # Process core definition files
    _process_file_entries(manifest.core_definition_files, "Core Definition")

    # Process supporting definition files (if any)
    if manifest.supporting_definition_files:
        _process_file_entries(manifest.supporting_definition_files, "Supporting Definition")

    # Load Extra_Files content
    extra_files_dict: Dict[Path, str] = {}
    try:
        # file_handler.load_extra_files_content returns Dict[str, str]
        # converting keys to Path for FullPersonaData schema
        raw_extra_files = load_extra_files_content(persona_folder_path)
        for rel_path_str, content in raw_extra_files.items():
            extra_files_dict[Path(rel_path_str)] = content
    except FileHandlerError as e:
        # This error implies an issue reading a file within Extra_Files, not that the dir is missing
        print(f"Warning: Error loading some content from '{EXTRA_FILES_SUBDIR_NAME}' for persona '{manifest.persona_id}': {e}")

    # Load latest chat log
    chat_log: Optional[str] = None
    try:
        # file_handler.load_latest_chat_log already handles FileHandlerError internally by returning None for IOErrors
        chat_log = load_latest_chat_log(persona_folder_path)
    except Exception as e: # Catch any unexpected errors from load_latest_chat_log, though it should be handled
        print(f"Warning: Unexpected error during chat log loading for persona '{manifest.persona_id}': {e}")


    return FullPersonaData(
        keyphrase=keyphrase,
        persona_id=manifest.persona_id,
        version=manifest.version,
        operational_rules=manifest.core_operational_rules, #
        manifest_files_content=loaded_manifest_files,
        extra_files_content=extra_files_dict,
        chat_log_content=chat_log
        # raw_manifest=manifest # Can be added if needed
    )