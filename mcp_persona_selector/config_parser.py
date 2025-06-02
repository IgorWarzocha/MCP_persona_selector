# mcp_persona_selector/config_parser.py
import json
from pathlib import Path
from typing import Dict, Optional, Union

from .schemas import AppConfig, PersonaManifest

# Configuration file names (as constants)
APP_CONFIG_FILENAME = "config.json"
PERSONA_MANIFEST_GENERIC_FILENAME = "manifest.json"
PERSONA_MANIFEST_SPECIFIC_SUFFIX = "_manifest.json"

# This path is now primarily for the default in load_app_config.
# The actual config_file_path used by server.py will be absolute.
PROJECT_ROOT_PATH_FOR_DEFAULT = Path(__file__).resolve().parent.parent 
DEFAULT_CONFIG_PATH = PROJECT_ROOT_PATH_FOR_DEFAULT / APP_CONFIG_FILENAME

class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

def load_app_config(config_file_path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """
    Loads the main application configuration from the specified JSON file.
    Validates against the AppConfig schema.
    """
    resolved_config_path = config_file_path.resolve() # Ensures config_file_path is absolute

    if not resolved_config_path.exists():
        raise ConfigError(f"Application configuration file not found: {resolved_config_path}")
    if not resolved_config_path.is_file():
        raise ConfigError(f"Application configuration path is not a file: {resolved_config_path}")
    try:
        with open(resolved_config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # --- MODIFICATION START for personasBasePath ---
        # If personasBasePath is present and relative, make it absolute
        # relative to the directory containing config.json.
        if "personasBasePath" in data and isinstance(data["personasBasePath"], str):
            path_val = Path(data["personasBasePath"])
            if not path_val.is_absolute():
                # config_dir is the directory where config.json was found
                config_dir = resolved_config_path.parent
                data["personasBasePath"] = (config_dir / path_val).resolve()
        # --- MODIFICATION END for personasBasePath ---

        # Now, when AppConfig(**data) is called, Pydantic's DirectoryPath
        # will receive an absolute path for personasBasePath, so its
        # .exists() and .is_dir() checks will work correctly.
        return AppConfig(**data)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Error decoding JSON from {resolved_config_path}: {e}")
    except Exception as e: 
        raise ConfigError(f"Error loading or validating app config {resolved_config_path}: {e}")

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
    except Exception as e: 
        raise ConfigError(f"Error loading or validating manifest {manifest_path_to_load.resolve()}: {e}")

def discover_and_load_personas(app_config: AppConfig) -> Dict[str, PersonaManifest]:
    """
    Discovers personas based on the personaActivationMap and loads their manifests.
    Returns a dictionary mapping keyphrases to loaded PersonaManifest objects.
    Logs warnings for missing persona folders or manifests but continues.
    """
    loaded_personas: Dict[str, PersonaManifest] = {}
    
    # app_config.personasBasePath is now guaranteed to be absolute by load_app_config
    base_path = app_config.personasBasePath

    for keyphrase, details in app_config.personaActivationMap.items():
        persona_folder_path = base_path / details.folderName 
        if not persona_folder_path.exists() or not persona_folder_path.is_dir():
            print(f"Warning: Persona folder '{details.folderName}' for keyphrase '{keyphrase}' not found at {persona_folder_path} or is not a directory.")
            continue
        
        try:
            manifest = load_persona_manifest(persona_folder_path, details.folderName)
            loaded_personas[keyphrase] = manifest
        except ConfigError as e:
            print(f"Warning: Could not load manifest for persona '{details.folderName}' (keyphrase: {keyphrase}): {e}")
            
    return loaded_personas