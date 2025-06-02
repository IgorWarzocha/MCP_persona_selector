# MCP_persona_selector/main.py
import sys
from pathlib import Path
import asyncio 

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import mcp_server (the FastMCP instance) from our server module
from mcp_persona_selector.server import mcp_server 
from mcp_persona_selector.config_parser import APP_CONFIG_FILENAME # For initial warning only

def main_runner() -> None:
    """
    Main synchronous wrapper to run the async server startup.
    """
    print("MCP Persona Selector Server (main.py): Initializing...")

    config_path_for_warning = Path(APP_CONFIG_FILENAME)
    if not config_path_for_warning.exists():
        print(
            f"INFO (main.py): Initial check for '{APP_CONFIG_FILENAME}' in CWD ({config_path_for_warning.resolve()}) shows it's not there.\n"
            f"The server's startup event will load it from the project root: "
            f"{project_root / APP_CONFIG_FILENAME}."
        )
    
    # The mcp_server instance has _server_info populated by its constructor
    # using title, version, description arguments.
    # We can access these via mcp_server.name and mcp_server.settings.version (or mcp_server.instructions)
    # if needed for logging here, or just use the strings directly.
    # The FastMCP class you provided has .name and .instructions properties.
    print(f"Attempting to start MCP server: {mcp_server.name} (Version defined in server.py)") 
    
    try:
        # Call the run_stdio_async method of the FastMCP instance
        asyncio.run(mcp_server.run_stdio_async())
    except Exception as e:
        import traceback
        # Print to stderr so Claude Desktop can capture it in mcp-server-PersonaSelector.log
        print(f"CRITICAL ERROR in main.py during server execution: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1) # Exit with an error code to signal failure to Claude Desktop

if __name__ == "__main__":
    main_runner()