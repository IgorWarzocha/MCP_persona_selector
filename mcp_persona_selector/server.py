# MCP_persona_selector/mcp_persona_selector/server.py
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Sequence

# --- MCP SDK Imports ---
from mcp.server.fastmcp import FastMCP # From your installed SDK
from mcp import types as mcp_types     # From your installed SDK
# We might not need ValidationError directly if FastMCP handles request parsing.
# from pydantic import ValidationError
# HTTPException might still be useful if FastMCP doesn't convert all errors.
# from fastapi import HTTPException 

# --- Project-Specific Imports ---
from .schemas import AppConfig, PersonaManifest
from .config_parser import load_app_config, discover_and_load_personas, ConfigError, APP_CONFIG_FILENAME
from .persona_manager import load_full_persona_data, FullPersonaData, PersonaManagerError
from .payload_constructor import construct_persona_payload

# --- Global Application State ---
app_state: Dict[str, Any] = {
    "app_config": None,
    "personas": {}, 
    "startup_error": None
}

# --- Startup Event Handler Function ---
async def startup_event():
    print("MCP Persona Selector Server: Initializing - loading configuration and personas...")
    try:
        current_file_path = Path(__file__).resolve()
        project_root_path = current_file_path.parent.parent
        config_file_path = project_root_path / APP_CONFIG_FILENAME
        
        app_config_instance = load_app_config(config_file_path)
        app_state["app_config"] = app_config_instance
        print(f"MCP Persona Selector Server: Application configuration loaded from: {config_file_path}")
        
        discovered_personas = discover_and_load_personas(app_config_instance)
        app_state["personas"] = discovered_personas
        print(f"MCP Persona Selector Server: Successfully loaded {len(discovered_personas)} persona manifest(s).")
        
        if app_config_instance and app_config_instance.personaActivationMap:
            for keyphrase, details in app_config_instance.personaActivationMap.items():
                if keyphrase in discovered_personas:
                    def create_tool_func(current_keyphrase, current_details_display_name):
                        # Tool functions registered with FastMCP are typically async
                        # and receive specific arguments based on the tool's inputSchema.
                        # For a simple tool called by name without other arguments,
                        # it might take no arguments or a context.
                        # The return type annotation here is str, which FastMCP should
                        # wrap into a TextContent automatically.
                        async def generic_persona_tool() -> str: 
                            print(f"Tool '{current_keyphrase}' called via FastMCP.")
                            app_cfg = app_state["app_config"]
                            persona_mnf = app_state["personas"][current_keyphrase]
                            
                            if not app_cfg or not persona_mnf:
                                # The FastMCP @tool decorator should handle this exception
                                # and convert it to an MCP error response.
                                raise PersonaManagerError(f"Server-side configuration error for tool {current_keyphrase}: AppConfig or PersonaManifest not loaded.")

                            # PersonaManagerError will be caught by FastMCP's tool handling
                            full_persona_data: FullPersonaData = load_full_persona_data(
                                keyphrase=current_keyphrase,
                                manifest=persona_mnf,
                                app_config=app_cfg
                            )
                            payload_string: str = construct_persona_payload(full_persona_data)
                            print(f"Successfully constructed payload for '{current_keyphrase}'. Payload length: {len(payload_string)}")
                            return payload_string 
                        
                        generic_persona_tool.__name__ = f"call_{current_keyphrase.lower()}_persona"
                        generic_persona_tool.__doc__ = f"Activates the {current_details_display_name} persona and returns its context."
                        return generic_persona_tool

                    tool_function = create_tool_func(keyphrase, details.displayName)
                    
                    # Register the tool using the .tool() decorator method of FastMCP
                    # The name and description are taken from the decorator arguments.
                    # The inputSchema for these tools is effectively empty (just called by name).
                    mcp_server.tool(
                        name=keyphrase, 
                        description=details.displayName
                        # inputSchema can be defined if needed, defaults to Pydantic model from type hints
                    )(tool_function)
                    print(f"MCP Persona Selector Server: Registered tool '{keyphrase}' - {details.displayName}")

        print("MCP Persona Selector Server: Startup complete. Server is ready to accept requests.")
        
    except ConfigError as e:
        error_msg = f"CRITICAL STARTUP ERROR (ConfigError): {e}. Server may not function correctly."
        print(error_msg, file=sys.stderr) # Print critical errors to stderr
        app_state["startup_error"] = error_msg
    except Exception as e:
        import traceback
        error_msg = f"UNEXPECTED CRITICAL STARTUP ERROR: {e}."
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        app_state["startup_error"] = error_msg

# --- Initialize FastMCP server ---
mcp_server = FastMCP(
    title="MCP Persona Selector Server", # Used for serverInfo.name
    version="0.3.0",                  # Used for serverInfo.version
    description="Provides persona contexts (PIP, SIU) as MCP tools.", # Used for serverInfo.instructions
    on_startup=[startup_event]        # Register our startup event
)

# --- Expose the FastMCP instance itself as the ASGI app ---
# This is what main.py will import and run.
app = mcp_server