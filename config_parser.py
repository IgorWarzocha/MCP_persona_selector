# mcp_persona_selector/config_parser.py
import json
from pathlib import Path
from typing import Dict, Optional, Union # Added Union for type hinting

from .schemas import AppConfig, PersonaManifest

# Configuration file names (as constants)
APP_CONFIG_FILENAME = "config.json"
# Manifest naming conventions from user outline
PERSONA_MANIFEST_GENERIC_FILENAME = "manifest.json"
PERSONA_MANIFEST_SPECIFIC_SUFFIX = "_manifest.json"


class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

def load_app_config(config_file_path: Path = Path(APP_CONFIG_FILENAME)) -> AppConfig:
    """
    Loads the main application configuration from the specified JSON file.
    Validates against the AppConfig schema.
   
    """
    if not config_file_path.exists():
        raise ConfigError(f"Application configuration file not found: {config_file_path.resolve()}")
    if not config_file_path.is_file():
        raise ConfigError(f"Application configuration path is not a file: {config_file_path.resolve()}")
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return AppConfig(**data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Error decoding JSON from {config_file_path.resolve()}: {e}")
    except Exception as e: # Pydantic validation errors will also be caught here via BaseModel instantiation
        raise ConfigError(f"Error loading or validating app config {config_file_path.resolve()}: {e}")

def load_persona_manifest(persona_folder_path: Path, persona_folder_name: str) -> PersonaManifest:
    """
    Loads a persona's manifest file (e.g., manifest.json or [persona_folder_name]_manifest.json)
    from its directory. Validates against the PersonaManifest schema.
    Raises ConfigError if manifest is not found or invalid.
   
    """
    manifest_filename_generic = persona_folder_path / PERSONA_MANIFEST_GENERIC_FILENAME
    manifest_filename_specific = persona_folder_path / f"{persona_folder_name}{PERSONA_MANIFEST_SPECIFIC_SUFFIX}"

    manifest_path_to_load: Optional[Path] = None

    if manifest_filename_specific.exists() and manifest_filename_specific.is_file():
        manifest_path_to_load = manifest_filename_specific
    elif manifest_filename_generic.exists() and manifest_filename_generic.is_file():
        manifest_path_to_load = manifest_filename_generic
            
    if not manifest_path_to_load:
        raise ConfigError(f"Manifest file not found in {persona_folder_path.resolve()} (tried {manifest_filename_specific.name} and {manifest_filename_generic.name})")

    try:
        with open(manifest_path_to_load, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return PersonaManifest(**data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Error decoding JSON from {manifest_path_to_load.resolve()}: {e}")
    except Exception as e: # Pydantic validation errors
        raise ConfigError(f"Error loading or validating manifest {manifest_path_to_load.resolve()}: {e}")

def discover_and_load_personas(app_config: AppConfig) -> Dict[str, PersonaManifest]:
    """
    Discovers personas based on the personaActivationMap and loads their manifests.
   
    Returns a dictionary mapping keyphrases to loaded PersonaManifest objects.
    Logs warnings for missing persona folders or manifests but continues.
    """
    loaded_personas: Dict[str, PersonaManifest] = {}
    base_path = app_config.personasBasePath.resolve() # Ensure path is absolute

    # The AppConfig model already validates that personasBasePath exists and is a directory.

    for keyphrase, details in app_config.personaActivationMap.items():
        persona_folder_path = base_path / details.folderName
        if not persona_folder_path.exists() or not persona_folder_path.is_dir():
            print(f"Warning: Persona folder '{details.folderName}' for keyphrase '{keyphrase}' not found at {persona_folder_path} or is not a directory.")
            continue
        
        try:
            manifest = load_persona_manifest(persona_folder_path, details.folderName)
            loaded_personas[keyphrase] = manifest
        except ConfigError as e:
            # Log the warning but continue processing other personas
            print(f"Warning: Could not load manifest for persona '{details.folderName}' (keyphrase: {keyphrase}): {e}")
            # Depending on strictness, one might choose to re-raise or collect errors

    return loaded_personas