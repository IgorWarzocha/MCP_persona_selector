# main.py
import uvicorn
from pathlib import Path

# Attempt to import the FastAPI app instance from your package
# This assumes that the mcp_persona_selector package is in the PYTHONPATH
# or that you are running this script from the project root directory
# where mcp_persona_selector is a subdirectory.
try:
    from mcp_persona_selector.server import app
    from mcp_persona_selector.config_parser import APP_CONFIG_FILENAME
except ImportError as e:
    print(f"Error importing the FastAPI app or config filename: {e}")
    print("Please ensure that the mcp_persona_selector package is correctly structured and in your PYTHONPATH,")
    print("or that you are running main.py from the project's root directory.")
    app = None # Set app to None so Uvicorn doesn't run if import fails
    APP_CONFIG_FILENAME = "config.json" # Default to prevent further error if import fails

if __name__ == "__main__":
    if app:
        print("Starting MCP Persona Selector server with Uvicorn...")
        
        # Check for config.json in the current working directory (project root)
        # The server.py startup event will try to load it from this location.
        config_path_check = Path(APP_CONFIG_FILENAME)
        if config_path_check.exists() and config_path_check.is_file():
            print(f"Found '{APP_CONFIG_FILENAME}' at: {config_path_check.resolve()}")
        else:
            print(f"WARNING: '{APP_CONFIG_FILENAME}' not found at: {config_path_check.resolve()}.")
            print("The server's startup event will attempt to load it, but might fail if the path isn't correct there either.")
            print(f"Ensure '{APP_CONFIG_FILENAME}' is placed in the directory from which you run this script,")
            print(f"or update the path in mcp_persona_selector/server.py's startup event.")

        print(f"MCP Persona Selector server will be accessible at http://0.0.0.0:8000 (or your configured host/port)")
        print("MCP Endpoints expected at /tools/list and /tools/call")
        print("Press CTRL+C to stop the server.")
        
        # Configuration for Uvicorn
        # host="0.0.0.0" makes the server accessible on your network
        # host="127.0.0.1" makes it only accessible locally
        # port can be changed as needed
        # log_level="info" provides a good amount of logging from Uvicorn itself
        # reload=True can be useful during development for automatic restarts on code changes
        # but should generally be False for "production" or stable testing.
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    else:
        print("Could not start server because the FastAPI app instance failed to import.")