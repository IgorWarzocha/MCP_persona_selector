# mcp_persona_selector/__init__.py
"""
MCP Persona Selector Package

This package provides functionalities to load, manage, and select
AI personas for integration with applications like Claude Desktop via MCP.
"""
from .schemas import (
    AppConfig,
    PersonaManifest,
    FileEntry,
    PersonaActivationDetail
)
from .config_parser import (
    load_app_config,
    load_persona_manifest,
    discover_and_load_personas,
    ConfigError,
    APP_CONFIG_FILENAME, # Exposing for easier reference if needed
    PERSONA_MANIFEST_GENERIC_FILENAME,
    PERSONA_MANIFEST_SPECIFIC_SUFFIX
)

__all__ = [
    "AppConfig",
    "PersonaManifest",
    "FileEntry",
    "PersonaActivationDetail",
    "load_app_config",
    "load_persona_manifest",
    "discover_and_load_personas",
    "ConfigError",
    "APP_CONFIG_FILENAME",
    "PERSONA_MANIFEST_GENERIC_FILENAME",
    "PERSONA_MANIFEST_SPECIFIC_SUFFIX"
]

__version__ = "0.1.0" # Initial version