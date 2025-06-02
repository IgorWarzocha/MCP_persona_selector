# mcp_persona_selector/schemas.py
from typing import List, Dict, Optional
from pathlib import Path
from pydantic import BaseModel, FilePath, DirectoryPath, field_validator, ValidationInfo

class FileEntry(BaseModel):
    description: str
    base_name: str
    extensions_to_try: List[str]
    path_relative_to_persona_folder: Path  # Path relative to its persona's folder
    is_required_flag: bool

class PersonaManifest(BaseModel):
    persona_id: str  # Based on 'ID' from your outline's manifest metadata
    version: str     # Based on 'version' from your outline's manifest metadata
    # Core operational rules - a list of strings as per outline
    core_operational_rules: List[str] 
    core_definition_files: List[FileEntry] #
    supporting_definition_files: Optional[List[FileEntry]] = None #

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