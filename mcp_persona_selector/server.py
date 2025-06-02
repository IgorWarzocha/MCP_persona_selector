# mcp_persona_selector/server.py
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from typing import Dict, List, Any, Optional

# --- MCP SDK Imports & Placeholders ---
# This section attempts to import necessary types from the MCP SDK.
# If these imports fail, it falls back to Pydantic-compatible placeholder types
# and prints a critical warning. For the server to be truly MCP compliant and
# robust, the actual SDK types must be successfully imported.
# This usually means `pip install "mcp[cli]"` must have installed the correct
# 'mcp' package and it's accessible in your Python environment.

try:
    from mcp import types as mcp_types  # For various MCP data structures
    from mcp.shared.message import JSONRPCRequest as JsonRpcRequest  # For the JSON-RPC request envelope
    from pydantic import ValidationError  # For validating params extracted from JSONRPCRequest
    SDK_AVAILABLE = True
    print("MCP Persona Selector Server: Successfully imported actual MCP SDK types.")
except ImportError as e:
    print(
        "CRITICAL WARNING: MCP SDK types could not be imported directly. "
        f"Specific error: {e}. Using placeholder types. "
        "Server will NOT be fully MCP compliant and may lack functionality. "
        "Ensure the 'mcp' package (installed via 'pip install \"mcp[cli]\"') is correct, "
        "installed in the active virtual environment, and accessible."
    )
    SDK_AVAILABLE = False
    
    # Import Pydantic BaseModel for placeholders
    from pydantic import BaseModel as PydanticBaseModel, Field as PydanticField

    class Placeholder(PydanticBaseModel):
        """Base for our Pydantic-compatible placeholders."""
        model_config = {"extra": "allow"} # Allow extra fields for some flexibility

    class JsonRpcRequest(Placeholder): # Placeholder for the JSON-RPC request envelope
        method: Optional[str] = None
        params: Optional[Dict[str, Any]] = None
        id: Optional[Any] = None
        jsonrpc: str = "2.0"

    class CallToolRequestParams(Placeholder): # Placeholder for the 'params' of a tools/call request
        name: Optional[str] = None
        arguments: Optional[Dict[str, Any]] = None
        toolState: Optional[Dict[str, Any]] = None
        progressToken: Optional[str] = None # Ensure all fields from real type are covered if possible

    class TextContent(Placeholder):
        type: str = "text"
        text: Optional[str] = None # Make optional to avoid validation issues if it's missing

    class CallToolResult(Placeholder):
        content: List[TextContent] = PydanticField(default_factory=list)
        isError: bool = False
        toolState: Optional[Dict[str, Any]] = None

    class Tool(Placeholder):
        name: str
        description: Optional[str] = None
        inputSchema: Dict[str, Any] = PydanticField(default_factory=lambda: {"type": "object", "properties": {}})
        outputSchema: Optional[Dict[str, Any]] = None
        annotations: Optional[Dict[str, Any]] = None

    class ListToolsResult(Placeholder):
        tools: List[Tool] = PydanticField(default_factory=list)
        nextCursor: Optional[str] = None
        _meta: Optional[Any] = None # Common in MCP types

    # Mock the mcp_types object with placeholder classes
    mcp_types = type('MockMCPTypes', (), {
        'ListToolsResult': ListToolsResult,
        'Tool': Tool,
        'CallToolRequest': CallToolRequestParams, # This is for validating rpc_request.params
        'CallToolResult': CallToolResult,
        'TextContent': TextContent,
        # Add any other mcp.types.* used by the server endpoints if the primary import fails
    })
    
    # Pydantic's ValidationError should ideally always be importable if FastAPI is working
    # If not, define a basic placeholder.
    if 'ValidationError' not in globals():
        class ValidationError(Exception): pass

# --- Project-Specific Imports ---
from .schemas import AppConfig, PersonaManifest
from .config_parser import load_app_config, discover_and_load_personas, ConfigError, APP_CONFIG_FILENAME
from .persona_manager import load_full_persona_data, FullPersonaData, PersonaManagerError
from .payload_constructor import construct_persona_payload

# --- FastAPI App Initialization ---
app = FastAPI(
    title="MCP Persona Selector Server",
    version="0.1.0",
    description="A local server to dynamically provide persona contexts to MCP clients like Claude Desktop."
)

# --- Global Application State ---
app_state: Dict[str, Any] = {
    "app_config": None,
    "personas": {},  # Dict[keyphrase, PersonaManifest]
    "startup_error": None
}

# --- Startup Event Handler ---
@app.on_event("startup")
async def startup_event():
    """
    Loads application configuration and discovers personas upon server startup.
    Handles potential errors during this critical phase.
    """
    print("MCP Persona Selector Server: Initializing - loading configuration and personas...")
    try:
        # config_file_path should be relative to where main.py is run (project root)
        config_file_path = Path(APP_CONFIG_FILENAME).resolve()
        
        app_config_instance = load_app_config(config_file_path)
        app_state["app_config"] = app_config_instance
        print(f"MCP Persona Selector Server: Application configuration loaded from: {config_file_path}")
        
        discovered_personas = discover_and_load_personas(app_config_instance)
        app_state["personas"] = discovered_personas
        print(f"MCP Persona Selector Server: Successfully loaded {len(discovered_personas)} persona manifest(s).")
        
        if not SDK_AVAILABLE: # Print warning again if placeholders are active
             print("MCP Persona Selector Server: WARNING - Running with placeholder MCP types due to import failure.")
        print("MCP Persona Selector Server: Startup complete. Server is ready to accept requests.")
        
    except ConfigError as e:
        error_msg = f"CRITICAL STARTUP ERROR (ConfigError): {e}. Server may not function correctly."
        print(error_msg)
        app_state["startup_error"] = error_msg
    except FileNotFoundError as e:
        error_msg = f"CRITICAL STARTUP ERROR (FileNotFoundError): {e}. Check config path. Server may not function."
        print(error_msg)
        app_state["startup_error"] = error_msg
    except Exception as e:
        error_msg = f"UNEXPECTED CRITICAL STARTUP ERROR: {e}. Server may not function correctly."
        print(error_msg)
        app_state["startup_error"] = error_msg # Store generic errors too

# --- MCP Endpoints ---

@app.post(
    "/tools/list",
    response_model=mcp_types.ListToolsResult,
    summary="List available personas as MCP tools",
    description="Provides a list of configured personas that can be activated as tools by an MCP client."
)
async def list_tools_endpoint() -> mcp_types.ListToolsResult:
    """
    MCP Endpoint: tools/list
    Returns a list of available personas (defined in config.json and successfully loaded)
    formatted as MCP Tool objects.
   
    
    """
    if app_state.get("startup_error"):
        print(f"Error in /tools/list: Server startup failed: {app_state['startup_error']}")
        # According to MCP, if a method itself fails (not a tool execution), a JSON-RPC error should be returned.
        # FastAPI handles this by raising HTTPException for HTTP errors, but for MCP logical errors within
        # a successful HTTP call, the response structure might need to reflect an MCP-level error.
        # For now, returning an empty tool list for simplicity if startup failed.
        return mcp_types.ListToolsResult(tools=[])

    app_config: Optional[AppConfig] = app_state.get("app_config")
    if not app_config or not app_config.personaActivationMap:
        print("Warning: /tools/list called, but app_config or personaActivationMap is not loaded/empty.")
        return mcp_types.ListToolsResult(tools=[])

    tools_list: List[mcp_types.Tool] = []
    for keyphrase, details in app_config.personaActivationMap.items():
        if keyphrase in app_state.get("personas", {}):  # Ensure manifest for this keyphrase was loaded
            tool = mcp_types.Tool(
                name=keyphrase,
                description=details.displayName,
                inputSchema={"type": "object", "properties": {}} # Standard minimal input schema
            )
            tools_list.append(tool)
        else:
            print(f"Info: Keyphrase '{keyphrase}' from config.json was not found in loaded personas during startup. Not listing as tool.")
            
    return mcp_types.ListToolsResult(tools=tools_list)


@app.post(
    "/tools/call",
    response_model=mcp_types.CallToolResult,
    summary="Activate a persona (tool) and retrieve its consolidated context payload",
    description="Handles an MCP tool call by loading all data for the specified persona (tool name/keyphrase), constructing its context payload, and returning it."
)
async def call_tool_endpoint(
    # Expects the full JSON-RPC request envelope as the body.
    # JsonRpcRequest should be from mcp.shared.message or our Pydantic-compatible placeholder.
    rpc_request: JsonRpcRequest = Body(...)
) -> mcp_types.CallToolResult:
    """
    MCP Endpoint: tools/call
    Processes a tool call by name (persona keyphrase), loads all associated data,
    constructs the context payload, and returns it.
   
   
    """
    if app_state.get("startup_error"):
        error_text = f"Server startup error prevents tool call for '{rpc_request.method if hasattr(rpc_request, 'method') else 'unknown method'}': {app_state['startup_error']}"
        print(f"Error in /tools/call: {error_text}")
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    app_config: Optional[AppConfig] = app_state.get("app_config")
    loaded_personas: Dict[str, PersonaManifest] = app_state.get("personas", {})

    if not app_config:
        print("Error in /tools/call: Server configuration not available.")
        error_text = "Server configuration error. Cannot process tool call."
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    # Validate the structure of the incoming JSON-RPC request params
    if not hasattr(rpc_request, 'params') or not isinstance(rpc_request.params, dict):
        method_name = rpc_request.method if hasattr(rpc_request, 'method') else "tools/call"
        error_msg = f"'params' field must be a valid object for '{method_name}' method."
        print(f"Error in /tools/call: {error_msg} Received params: {getattr(rpc_request, 'params', 'Not_Available')}")
        error_content = mcp_types.TextContent(type="text", text=error_msg)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    try:
        # mcp_types.CallToolRequest here should refer to the model for PARAMS,
        # not the full envelope. This will be CallToolRequestParamsPlaceholder if SDK failed to import.
        call_params = mcp_types.CallToolRequest(**rpc_request.params)
    except ValidationError as ve:
        method_name = rpc_request.method if hasattr(rpc_request, 'method') else "tools/call"
        error_msg = f"Invalid parameters for '{method_name}': {ve}"
        print(f"Error in /tools/call: {error_msg}")
        error_content = mcp_types.TextContent(type="text", text=error_msg)
        return mcp_types.CallToolResult(content=[error_content], isError=True)
    except Exception as e: # Catch other errors like TypeError if params is not a dict
        method_name = rpc_request.method if hasattr(rpc_request, 'method') else "tools/call"
        error_msg = f"Error validating parameters for '{method_name}': {e}"
        print(f"Error in /tools/call: {error_msg}")
        error_content = mcp_types.TextContent(type="text", text=error_msg)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    keyphrase = call_params.name
    if not keyphrase: # Check if name was actually present in params
        error_msg = f"Parameter 'name' (keyphrase) missing in 'params' for '{rpc_request.method if hasattr(rpc_request, 'method') else 'tools/call'}'."
        print(f"Error in /tools/call: {error_msg}")
        error_content = mcp_types.TextContent(type="text", text=error_msg)
        return mcp_types.CallToolResult(content=[error_content], isError=True)


    persona_manifest = loaded_personas.get(keyphrase)
    if not persona_manifest:
        print(f"Error in /tools/call: Manifest for keyphrase '{keyphrase}' not found in loaded personas.")
        error_text = f"Persona with keyphrase '{keyphrase}' not found or its manifest failed to load during startup."
        error_content = mcp_types.TextContent(type="text", text=error_text)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    try:
        print(f"Processing /tools/call for keyphrase: '{keyphrase}'...")
        full_persona_data: FullPersonaData = load_full_persona_data(
            keyphrase=keyphrase,
            manifest=persona_manifest,
            app_config=app_config
        )
        
        payload_string: str = construct_persona_payload(full_persona_data)
        
        print(f"Successfully constructed payload for '{keyphrase}'. Payload length: {len(payload_string)}")
        text_content = mcp_types.TextContent(type="text", text=payload_string)
        return mcp_types.CallToolResult(content=[text_content], isError=False)
        
    except PersonaManagerError as e:
        print(f"PersonaManagerError during /tools/call for '{keyphrase}': {e}")
        error_content = mcp_types.TextContent(type="text", text=f"Error loading data for persona '{keyphrase}': {e}")
        return mcp_types.CallToolResult(content=[error_content], isError=True)
    except Exception as e:
        print(f"Unexpected critical error during /tools/call processing for '{keyphrase}': {e}")
        # Add traceback logging here in a real scenario: import traceback; traceback.print_exc();
        error_content = mcp_types.TextContent(type="text", text=f"Unexpected server error while processing persona '{keyphrase}'.")
        return mcp_types.CallToolResult(content=[error_content], isError=True)

# To run this server (typically in a separate main.py or using uvicorn directly):
# Ensure `APP_CONFIG_FILENAME` (imported from .config_parser) is correctly defined and 
# the config file is in the expected location when main.py is run.
# Example main.py at project root:
#
# import uvicorn
# from mcp_persona_selector.server import app
# from mcp_persona_selector.config_parser import APP_CONFIG_FILENAME
# from pathlib import Path
#
# if __name__ == "__main__":
#     print("Starting MCP Persona Selector server with Uvicorn on http://127.0.0.1:8000")
#     print(f"Attempting to load configuration from: {Path(APP_CONFIG_FILENAME).resolve()}")
#     uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
#