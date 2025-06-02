# mcp_persona_selector/server.py
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from typing import Dict, List, Any, Optional

# Attempt to import MCP types from the provided SDK.
# The exact import path may depend on how the SDK is integrated/installed.
try:
    # This assumes the 'mcp' package from the SDK is in PYTHONPATH
    # or installed in the environment.
    from mcp import types as mcp_types
    # from mcp.shared.exceptions import McpError # Available for more specific error handling
except ImportError:
    # Fallback placeholder types if MCP SDK is not directly importable.
    # This allows the server structure to be defined, but real MCP interaction would fail.
    # In a production setup, ensure the MCP SDK is correctly installed or accessible.
    print(
        "CRITICAL WARNING: MCP SDK types could not be imported directly. "
        "Using placeholder types. Server will not be MCP compliant without the actual SDK types. "
        "Ensure the 'python-sdk/src' directory is in your PYTHONPATH or the SDK is installed."
    )
    class PlaceholderBaseModel: # Minimal Pydantic-like placeholder
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self, **kwargs): # For FastAPI response_model compatibility
            return self.__dict__

    class ListToolsResult(PlaceholderBaseModel): pass
    class Tool(PlaceholderBaseModel): pass
    class CallToolRequest(PlaceholderBaseModel): pass
    class CallToolResult(PlaceholderBaseModel): pass
    class TextContent(PlaceholderBaseModel): pass
    
    # Create a mock mcp_types object
    mcp_types = type('MockMCPTypes', (), {
        'ListToolsResult': ListToolsResult, 'Tool': Tool,
        'CallToolRequest': CallToolRequest, 'CallToolResult': CallToolResult,
        'TextContent': TextContent,
        # Define other necessary MCP types as placeholders if server.py uses them
        'Error': type('Error', (PlaceholderBaseModel,), {}),
        'ErrorCode': type('ErrorCode', (), {'InvalidRequest': -32600, 'InternalError': -32603, 'MethodNotFound': -32601}),
        'JsonRpcError': type('JsonRpcError', (PlaceholderBaseModel,), {})
    })


# Our project's modules
from .schemas import AppConfig, PersonaManifest
from .config_parser import load_app_config, discover_and_load_personas, ConfigError, APP_CONFIG_FILENAME
from .persona_manager import load_full_persona_data, FullPersonaData, PersonaManagerError
from .payload_constructor import construct_persona_payload

# --- FastAPI App Initialization ---
app = FastAPI(
    title="MCP Persona Selector Server",
    version="0.1.0", # Consider moving version to __init__.py and importing
    description="A local server to dynamically provide persona contexts to MCP clients like Claude Desktop."
)

# --- Global Application State ---
# This dictionary will hold loaded configurations and discovered personas.
# It's populated during the server's startup event.
app_state: Dict[str, Any] = {
    "app_config": None,      # Will hold AppConfig instance
    "personas": {},          # Will hold Dict[keyphrase (str), PersonaManifest]
    "startup_error": None    # To store any critical startup error message
}

# --- Startup Event Handler ---
@app.on_event("startup")
async def startup_event():
    """
    Load configurations and discover personas when the server starts.
    """
    print("MCP Persona Selector Server: Attempting startup configuration...")
    try:
        # Assuming APP_CONFIG_FILENAME is relative to where the server is run from.
        # For robustness, consider using an environment variable for config path or an absolute path.
        config_file_path = Path(APP_CONFIG_FILENAME).resolve()
        
        app_config_instance = load_app_config(config_file_path)
        app_state["app_config"] = app_config_instance
        print(f"MCP Persona Selector Server: Loaded application configuration from: {config_file_path}")
        
        discovered_personas = discover_and_load_personas(app_config_instance)
        app_state["personas"] = discovered_personas
        print(f"MCP Persona Selector Server: Successfully loaded {len(discovered_personas)} persona manifest(s).")
        print("MCP Persona Selector Server: Startup complete. Ready to accept requests.")
        
    except ConfigError as e:
        error_msg = f"CRITICAL STARTUP ERROR: Failed to load configuration or initial personas: {e}"
        print(error_msg)
        app_state["startup_error"] = error_msg
        app_state["app_config"] = None 
        app_state["personas"] = {}
    except Exception as e:
        error_msg = f"UNEXPECTED CRITICAL STARTUP ERROR: {e}"
        print(error_msg)
        app_state["startup_error"] = error_msg # Store unexpected errors too
        app_state["app_config"] = None
        app_state["personas"] = {}

# --- MCP Endpoints ---

# Reference for MCP tools/list:
@app.post(
    "/tools/list", # MCP typically uses JSON-RPC style method names as paths
    response_model=mcp_types.ListToolsResult, 
    summary="List available personas as MCP tools"
)
async def list_tools_endpoint() -> mcp_types.ListToolsResult:
    """
    MCP Endpoint to list available personas as tools.
    Each persona keyphrase from the personaActivationMap in config.json becomes an MCP tool.
   
    """
    if app_state.get("startup_error"):
        # If startup failed critically, this endpoint might not function.
        # Consider how MCP expects such server-level errors to be reported for /tools/list.
        # For now, returning empty, but a proper MCP error response might be better if spec allows.
        print(f"Error: /tools/list called but server startup encountered an error: {app_state['startup_error']}")
        return mcp_types.ListToolsResult(tools=[])

    app_config: Optional[AppConfig] = app_state.get("app_config")
    
    if not app_config or not app_config.personaActivationMap:
        print("Warning: /tools/list called but no app_config or personaActivationMap loaded.")
        return mcp_types.ListToolsResult(tools=[])

    tools_list: List[mcp_types.Tool] = []
    for keyphrase, details in app_config.personaActivationMap.items():
        if keyphrase in app_state.get("personas", {}): # Check if manifest was loaded
            tool = mcp_types.Tool(
                name=keyphrase,
                description=details.displayName,
                inputSchema={"type": "object", "properties": {}}, # Minimal schema
            )
            tools_list.append(tool)
        else:
            print(f"Info: Keyphrase '{keyphrase}' in activation map but manifest not loaded/found during startup. Not listing as tool.")
    
    return mcp_types.ListToolsResult(tools=tools_list)

# Reference for MCP tools/call:
@app.post(
    "/tools/call", 
    response_model=mcp_types.CallToolResult, 
    summary="Activate a persona (tool) and get its context payload"
)
async def call_tool_endpoint(
    request: mcp_types.CallToolRequest = Body(...) # Ensure request is from body
) -> mcp_types.CallToolResult:
    """
    MCP Endpoint to handle a tool call, which corresponds to activating a persona.
    It loads all data for the specified persona, constructs the context payload,
    and returns it as part of the MCP CallToolResult.
   
    """
    if app_state.get("startup_error"):
        error_text = f"Server startup error prevents tool call: {app_state['startup_error']}"
        print(f"Error: /tools/call for '{request.name}' but server has startup error.")
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    app_config: Optional[AppConfig] = app_state.get("app_config")
    loaded_personas: Dict[str, PersonaManifest] = app_state.get("personas", {})
    
    keyphrase = request.name 

    if not app_config:
        print(f"Error: /tools/call for '{keyphrase}' but server configuration is not loaded.")
        error_text = "Server configuration error. Cannot process tool call."
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    persona_manifest = loaded_personas.get(keyphrase)
    if not persona_manifest:
        print(f"Error: /tools/call for '{keyphrase}' but no manifest found for this persona.")
        error_text = f"Persona with keyphrase '{keyphrase}' not found or its manifest failed to load."
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    try:
        print(f"Processing /tools/call for keyphrase: {keyphrase}")
        full_persona_data: FullPersonaData = load_full_persona_data(
            keyphrase=keyphrase,
            manifest=persona_manifest,
            app_config=app_config
        )
        
        payload_string: str = construct_persona_payload(full_persona_data)
        
        text_content = mcp_types.TextContent(type="text", text=payload_string)
        return mcp_types.CallToolResult(content=[text_content], isError=False)
        
    except PersonaManagerError as e:
        print(f"PersonaManagerError processing persona '{keyphrase}' for /tools/call: {e}")
        error_content = mcp_types.TextContent(type="text", text=f"Error loading data for persona '{keyphrase}': {e}")
        return mcp_types.CallToolResult(content=[error_content], isError=True)
    except Exception as e:
        print(f"Unexpected critical error during /tools/call for '{keyphrase}': {e}")
        # Consider logging traceback for debugging
        error_content = mcp_types.TextContent(type="text", text=f"Unexpected server error while processing persona '{keyphrase}'.")
        return mcp_types.CallToolResult(content=[error_content], isError=True)

# Note on running:
# This server definition can be run using Uvicorn. For example, if you create a
# main.py in your project root:
#
# # main.py
# import uvicorn
# from mcp_persona_selector.server import app # Make sure mcp_persona_selector is in PYTHONPATH
#
# if __name__ == "__main__":
#     print("Starting MCP Persona Selector server with Uvicorn on http://0.0.0.0:8000")
#     print(f"Ensure '{APP_CONFIG_FILENAME}' is in the current working directory: {Path.cwd()}")
#     uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
#
# Then run `python main.py`.
# The APP_CONFIG_FILENAME constant is imported from .config_parser.