# mcp_persona_selector/persona_manager.py
from pathlib import Path
from typing import Dict, List, Optional, Any # Added Any for Pydantic model_config
from pydantic import BaseModel, Field # Ensure Field is imported for FullPersonaData

# Assuming AppConfig, PersonaManifest, FileEntry are correctly defined in .schemas
from .schemas import AppConfig, PersonaManifest, FileEntry
from .file_handler import (
    load_file_content_from_entry,
    load_extra_files_content,
    load_latest_chat_log,
    FileHandlerError,
    EXTRA_FILES_SUBDIR_NAME # Import if used directly for context in descriptions
)

class LoadedPersonaFileContent(BaseModel):
    """Represents the content of a loaded file along with its source description and path."""
    source_description: str
    # relative_path_in_source_dir is relative to the specific persona's folder for manifest files,
    # or relative to the Extra_Files folder for extra files.
    relative_path_in_source_dir: Path 
    content: str
    is_required: bool

    model_config = {"extra": "allow"} # Pydantic v2 config

class FullPersonaData(BaseModel):
    """
    Aggregates all data loaded for a specific persona, ready for payload construction.
    """
    keyphrase: str
    persona_id: str
    version: str
    operational_rules: List[str] = Field(default_factory=list)
    manifest_files_content: List[LoadedPersonaFileContent] = Field(default_factory=list)
    extra_files_content: Dict[Path, str] = Field(default_factory=dict) # Keys are Path relative to Extra_Files
    chat_log_content: Optional[str] = None
    # raw_manifest: Optional[PersonaManifest] = None # Optional: if needed later

    model_config = {"extra": "allow"} # Pydantic v2 config

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
        file_entries_list: List[FileEntry], 
        category_description_prefix: str
    ):
        for file_entry in file_entries_list:
            # The FileEntry schema should ensure base_name is non-empty (min_length=1)
            # This check is an additional safeguard if schema validation wasn't strict enough or not applied.
            if not file_entry.base_name:
                error_msg = (f"FileEntry has an empty 'base_name' for {category_description_prefix.lower()} "
                             f"file described as '{file_entry.description}'. This is invalid.")
                if file_entry.is_required_flag:
                    raise PersonaManagerError(error_msg)
                else:
                    print(f"Warning: {error_msg} Skipping this optional file entry.")
                    continue
            
            try:
                content = load_file_content_from_entry(persona_folder_path, file_entry)
                
                # Construct the filename part for display_path carefully
                filename_part_for_display = file_entry.base_name
                if file_entry.extensions_to_try:
                    # Use the first extension for display purposes.
                    # load_file_content_from_entry handles trying all extensions.
                    first_ext = file_entry.extensions_to_try[0]
                    if first_ext: # Ensure the extension string itself is not empty
                        filename_part_for_display += first_ext if first_ext.startswith('.') else f".{first_ext}"
                
                if not filename_part_for_display: # Should be caught by base_name validation mostly
                    path_error_msg = (f"Cannot form a valid display filename for file described as "
                                      f"'{file_entry.description}' (base_name: '{file_entry.base_name}', "
                                      f"first_ext: '{first_ext if file_entry.extensions_to_try and file_entry.extensions_to_try[0] else 'N/A'}').")
                    if file_entry.is_required_flag:
                        raise PersonaManagerError(path_error_msg)
                    else:
                        print(f"Warning: {path_error_msg} Using a placeholder display path for this optional file.")
                        # Create a placeholder path if the real one is problematic, to avoid errors with .with_name('')
                        display_path = file_entry.path_relative_to_persona_folder / f"{file_entry.base_name}_[bad_ext_or_name]"
                else:
                    try:
                        display_path = file_entry.path_relative_to_persona_folder.with_name(filename_part_for_display)
                    except ValueError as ve_path: # Catch error from path_relative_to_persona_folder.with_name(), e.g. if filename_part_for_display is invalid
                        path_error_msg = (f"Path construction error for display path of file '{filename_part_for_display}' "
                                          f"(related to '{file_entry.description}'): {ve_path}")
                        if file_entry.is_required_flag:
                            raise PersonaManagerError(path_error_msg)
                        else:
                            print(f"Warning: {path_error_msg} Using placeholder display path for this optional file.")
                            display_path = file_entry.path_relative_to_persona_folder / f"{file_entry.base_name}_[path_error]"


                if content is not None:
                    loaded_manifest_files.append(
                        LoadedPersonaFileContent(
                            source_description=f"{category_description_prefix}: {file_entry.description}",
                            relative_path_in_source_dir=display_path,
                            content=content,
                            is_required=file_entry.is_required_flag
                        )
                    )
                elif file_entry.is_required_flag:
                    # This means load_file_content_from_entry returned None for a file marked as required.
                    # load_file_content_from_entry should have raised FileHandlerError if it couldn't find a required file.
                    # This is a safeguard or indicates an unexpected None for a required file.
                    raise PersonaManagerError(
                        f"Required {category_description_prefix.lower()} file '{file_entry.base_name}' for persona "
                        f"'{manifest.persona_id}' was indicated as not found by file_handler, despite being required."
                    )
            except FileHandlerError as e:
                if file_entry.is_required_flag:
                    raise PersonaManagerError(
                        f"Failed to load required {category_description_prefix.lower()} file '{file_entry.base_name}' "
                        f"for persona '{manifest.persona_id}': {e}"
                    )
                else:
                    # Log optional file loading failures, but don't stop the process
                    print(f"Warning: Optional {category_description_prefix.lower()} file '{file_entry.base_name}' "
                          f"for persona '{manifest.persona_id}' not loaded: {e}")
            except PersonaManagerError: # Re-raise if it's one of our specific errors from above
                raise
            except Exception as e: # Catch any other unexpected errors for this FileEntry
                error_detail = (f"Unexpected error processing file entry (description: '{file_entry.description}', "
                                f"base_name: '{file_entry.base_name}') for persona '{manifest.persona_id}': {e}")
                if file_entry.is_required_flag:
                    raise PersonaManagerError(error_detail)
                else:
                    print(f"Warning: {error_detail}")


    # Process core definition files
    _process_file_entries(manifest.core_definition_files, "Core Definition")

    # Process supporting definition files (if any)
    if manifest.supporting_definition_files:
        _process_file_entries(manifest.supporting_definition_files, "Supporting Definition")

    # Load Extra_Files content
    extra_files_dict: Dict[Path, str] = {}
    try:
        raw_extra_files = load_extra_files_content(persona_folder_path)
        for rel_path_str, content_str in raw_extra_files.items():
            extra_files_dict[Path(rel_path_str)] = content_str # Keys are relative to Extra_Files dir
    except FileHandlerError as e:
        print(f"Warning: Error loading some content from '{EXTRA_FILES_SUBDIR_NAME}' for persona '{manifest.persona_id}': {e}")
    except Exception as e: # Catch any other unexpected errors
        print(f"Warning: Unexpected error loading from '{EXTRA_FILES_SUBDIR_NAME}' for persona '{manifest.persona_id}': {e}")


    # Load latest chat log
    chat_log: Optional[str] = None
    try:
        chat_log = load_latest_chat_log(persona_folder_path)
    except Exception as e: 
        # load_latest_chat_log should ideally handle its own IOErrors gracefully and return None.
        # This catch is for truly unexpected issues from that function.
        print(f"Warning: Unexpected error during chat log loading for persona '{manifest.persona_id}': {e}")

    return FullPersonaData(
        keyphrase=keyphrase,
        persona_id=manifest.persona_id,
        version=manifest.version,
        operational_rules=manifest.core_operational_rules, #
        manifest_files_content=loaded_manifest_files,
        extra_files_content=extra_files_dict,
        chat_log_content=chat_log
    )