# mcp_persona_selector/server.py
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from typing import Dict, List, Any, Optional

# --- MCP SDK Imports & Placeholders ---
try:
    from mcp import types as mcp_types
    from mcp.types import JSONRPCRequest as JsonRpcRequest
    from pydantic import ValidationError
    SDK_AVAILABLE = True
    print("MCP Persona Selector Server: Successfully imported actual MCP SDK types.")
except ImportError as e:
    print(
        f"CRITICAL WARNING: MCP SDK types could not be imported directly. "
        f"Specific error: {e}. Using placeholder types. "
        "Server will NOT be fully MCP compliant and may lack functionality. "
        "Ensure the 'mcp' package (installed via 'pip install \"mcp[cli]\"') is correct, "
        "installed in the active virtual environment, and accessible."
    )
    SDK_AVAILABLE = False
    
    from pydantic import BaseModel as PydanticBaseModel, Field as PydanticField

    class Placeholder(PydanticBaseModel):
        model_config = {"extra": "allow"}

    class JsonRpcRequest(Placeholder): 
        method: Optional[str] = None
        params: Optional[Dict[str, Any]] = None
        id: Optional[Any] = None
        jsonrpc: str = "2.0"

    class CallToolRequestParamsPlaceholder(Placeholder): 
        name: Optional[str] = None
        arguments: Optional[Dict[str, Any]] = None
        toolState: Optional[Dict[str, Any]] = None
        progressToken: Optional[str] = None

    class TextContent(Placeholder):
        type: str = "text"
        text: Optional[str] = None

    class CallToolResult(Placeholder):
        content: List[TextContent] = PydanticField(default_factory=list)
        isError: bool = False
        toolState: Optional[Dict[str, Any]] = None
        _meta: Optional[Any] = None

    class Tool(Placeholder):
        name: str
        description: Optional[str] = None
        inputSchema: Dict[str, Any] = PydanticField(default_factory=lambda: {"type": "object", "properties": {}})
        outputSchema: Optional[Dict[str, Any]] = None
        annotations: Optional[Dict[str, Any]] = None

    class ListToolsResult(Placeholder):
        tools: List[Tool] = PydanticField(default_factory=list)
        nextCursor: Optional[str] = None
        _meta: Optional[Any] = None

    mcp_types = type('MockMCPTypes', (), {
        'ListToolsResult': ListToolsResult,
        'Tool': Tool,
        'CallToolRequest': CallToolRequestParamsPlaceholder,
        'CallToolResult': CallToolResult,
        'TextContent': TextContent,
        'JSONRPCRequest': JsonRpcRequest
    })
    
    if 'ValidationError' not in globals():
        class ValidationError(Exception): pass

# --- Project-Specific Imports ---
from .schemas import AppConfig, PersonaManifest
# APP_CONFIG_FILENAME is used in server.py's startup_event
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
    "personas": {},
    "startup_error": None
}

# --- Startup Event Handler ---
@app.on_event("startup")
async def startup_event():
    print("MCP Persona Selector Server: Initializing - loading configuration and personas...")
    try:
        # --- MODIFICATION START for config_file_path ---
        # Calculate path to config.json relative to this server.py file
        # Assumes server.py is in MCP_persona_selector/mcp_persona_selector/
        # And config.json is in MCP_persona_selector/
        current_file_path = Path(__file__).resolve()
        project_root_path = current_file_path.parent.parent 
        config_file_path = project_root_path / APP_CONFIG_FILENAME
        # --- MODIFICATION END for config_file_path ---
        
        app_config_instance = load_app_config(config_file_path) # load_app_config now receives an absolute path
        app_state["app_config"] = app_config_instance
        print(f"MCP Persona Selector Server: Application configuration loaded from: {config_file_path}")
        
        # discover_and_load_personas uses app_config.personasBasePath, which is resolved
        # by AppConfig's validator relative to where config.json was found.
        discovered_personas = discover_and_load_personas(app_config_instance)
        app_state["personas"] = discovered_personas
        print(f"MCP Persona Selector Server: Successfully loaded {len(discovered_personas)} persona manifest(s).")
        
        if not SDK_AVAILABLE:
             print("MCP Persona Selector Server: WARNING - Running with placeholder MCP types due to import failure.")
        print("MCP Persona Selector Server: Startup complete. Server is ready to accept requests.")
        
    except ConfigError as e:
        error_msg = f"CRITICAL STARTUP ERROR (ConfigError): {e}. Server may not function correctly."
        print(error_msg)
        app_state["startup_error"] = error_msg
    except FileNotFoundError as e: # Should be less likely now for config.json
        error_msg = f"CRITICAL STARTUP ERROR (FileNotFoundError): {e}. Check paths. Server may not function."
        print(error_msg)
        app_state["startup_error"] = error_msg
    except Exception as e:
        error_msg = f"UNEXPECTED CRITICAL STARTUP ERROR: {e}. Server may not function correctly."
        print(error_msg) # Consider traceback.print_exc() for full detail in dev
        app_state["startup_error"] = error_msg

# --- MCP Endpoints ---

@app.post(
    "/tools/list",
    response_model=mcp_types.ListToolsResult,
    summary="List available personas as MCP tools",
    description="Provides a list of configured personas that can be activated as tools by an MCP client."
)
async def list_tools_endpoint() -> mcp_types.ListToolsResult:
    if app_state.get("startup_error"):
        print(f"Error in /tools/list: Server startup failed: {app_state['startup_error']}")
        return mcp_types.ListToolsResult(tools=[])

    app_config: Optional[AppConfig] = app_state.get("app_config")
    if not app_config or not app_config.personaActivationMap:
        print("Warning: /tools/list called, but app_config or personaActivationMap is not loaded/empty.")
        return mcp_types.ListToolsResult(tools=[])

    tools_list: List[mcp_types.Tool] = []
    for keyphrase, details in app_config.personaActivationMap.items():
        if keyphrase in app_state.get("personas", {}):
            tool = mcp_types.Tool(
                name=keyphrase,
                description=details.displayName,
                inputSchema={"type": "object", "properties": {}}
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
    rpc_request: JsonRpcRequest = Body(...)
) -> mcp_types.CallToolResult:

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

    if not hasattr(rpc_request, 'params') or not isinstance(rpc_request.params, dict):
        method_name_str = rpc_request.method if hasattr(rpc_request, 'method') and rpc_request.method else "tools/call"
        error_msg = (f"Internal Server Error: rpc_request.params is not a dictionary or missing "
                       f"for method '{method_name_str}'.")
        params_type_str = type(rpc_request.params).__name__ if hasattr(rpc_request, 'params') else 'N/A'
        print(f"Error in /tools/call: {error_msg}. Params type: {params_type_str}")
        error_content = mcp_types.TextContent(type="text", text=error_msg)
        return mcp_types.CallToolResult(content=[error_content], isError=True)

    keyphrase = rpc_request.params.get("name")

    if not keyphrase:
        method_name_str = rpc_request.method if hasattr(rpc_request, 'method') and rpc_request.method else "tools/call"
        error_msg = f"Parameter 'name' (keyphrase) missing in params for method '{method_name_str}'."
        print(f"Error in /tools/call: {error_msg}. Params content: {rpc_request.params}")
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
        error_content = mcp_types.TextContent(type="text", text=f"Unexpected server error while processing persona '{keyphrase}'.")
        return mcp_types.CallToolResult(content=[error_content], isError=True)