# mcp_persona_selector/schemas.py
from typing import List, Dict, Optional
from pathlib import Path
# Add Field to pydantic imports if it's not already there
from pydantic import BaseModel, FilePath, DirectoryPath, field_validator, ValidationInfo, Field # Added Field

class FileEntry(BaseModel):
    description: str
    base_name: str = Field(..., min_length=1) # Ensures base_name is not empty
    extensions_to_try: List[str]
    path_relative_to_persona_folder: Path
    is_required_flag: bool

# ... rest of schemas.py remains the same (PersonaManifest, PersonaActivationDetail, AppConfig) ...
# Ensure PersonaManifest uses this updated FileEntry
class PersonaManifest(BaseModel): # Make sure this uses the updated FileEntry
    persona_id: str 
    version: str    
    core_operational_rules: List[str]
    core_definition_files: List[FileEntry] # Will use the validated FileEntry
    supporting_definition_files: Optional[List[FileEntry]] = None # Will use the validated FileEntry
# ...

class PersonaActivationDetail(BaseModel):
    displayName: str  # As per personaActivationMap in your outline
    folderName: str   # As per personaActivationMap in your outline

class AppConfig(BaseModel):
    personasBasePath: DirectoryPath # Ensures the path is a directory
    personaActivationMap: Dict[str, PersonaActivationDetail] #

    @field_validator('personasBasePath')
    @classmethod
    def resolve_personas_base_path(cls, v: Path, info: ValidationInfo) -> Path:
        if not v.exists():
            raise ValueError(f"personasBasePath does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"personasBasePath is not a directory: {v}")
        return v.resolve()