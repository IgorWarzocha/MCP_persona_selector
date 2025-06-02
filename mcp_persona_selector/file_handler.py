# mcp_persona_selector/file_handler.py
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from .schemas import FileEntry # Assuming FileEntry is defined in schemas.py

class FileHandlerError(Exception):
    """Custom exception for file handling errors."""
    pass

# Constants
EXTRA_FILES_SUBDIR_NAME = "Extra_Files"
CHAT_LOG_PREFIX = "ChatLog_"
CHAT_LOG_SUPPORTED_EXTENSIONS = [".json", ".txt"]
# Regex to capture YYYY-MM-DD from filename, e.g., ChatLog_2023-10-26.json
CHAT_LOG_DATE_PATTERN = re.compile(
    rf"^{CHAT_LOG_PREFIX}(\d{{4}}-\d{{2}}-\d{{2}})\.(json|txt)$", 
    re.IGNORECASE
)
# In mcp_persona_selector/file_handler.py

# ... (keep existing imports: Path, Optional, List, FileEntry, FileHandlerError) ...
# ... (keep other functions like load_extra_files_content, load_latest_chat_log as they are) ...

def load_file_content_from_entry(
    persona_folder_path: Path,
    file_entry: FileEntry
) -> Optional[str]:
    """
    Loads the content of a single file specified by a FileEntry object.
    The path to the file is constructed by joining persona_folder_path,
    file_entry.path_relative_to_persona_folder, and then appending
    file_entry.base_name with one of the extensions_to_try.

    Args:
        persona_folder_path: The absolute path to the persona's main folder.
        file_entry: The FileEntry object describing the file to load.

    Returns:
        The content of the file as a string if found.
        None if the file is not found and is_required_flag is False.

    Raises:
        FileHandlerError: If the file is not found and is_required_flag is True,
                          or if there's an error reading the file.
    """
    # Determine the actual directory where the file should be found
    # file_entry.path_relative_to_persona_folder is the subdirectory string (e.g., ".", "definitions")
    actual_file_directory = (persona_folder_path / file_entry.path_relative_to_persona_folder).resolve()

    file_found_path: Optional[Path] = None

    if not actual_file_directory.exists() or not actual_file_directory.is_dir():
        if file_entry.is_required_flag:
            raise FileHandlerError(
                f"Target directory '{actual_file_directory}' for file '{file_entry.base_name}' "
                f"(relative path: '{file_entry.path_relative_to_persona_folder}') "
                f"in persona folder '{persona_folder_path.resolve()}' does not exist or is not a directory."
            )
        # If optional and directory doesn't exist, the file cannot be found.
        print(f"Warning: Target directory '{actual_file_directory}' for optional file '{file_entry.base_name}' not found. Skipping.")
        return None

    for ext_to_try in file_entry.extensions_to_try:
        # Ensure extension starts with a dot if it's not empty
        current_ext = ext_to_try
        if current_ext and not current_ext.startswith('.'):
            current_ext = f".{current_ext}"
        
        potential_file_path = actual_file_directory / f"{file_entry.base_name}{current_ext}"

        if potential_file_path.exists() and potential_file_path.is_file():
            file_found_path = potential_file_path
            break # File found with an extension

    if not file_found_path:
        # If still not found after trying all extensions
        if file_entry.is_required_flag:
            tried_extensions_str = ', '.join(file_entry.extensions_to_try)
            raise FileHandlerError(
                f"Required file '{file_entry.base_name}' (tried extensions: [{tried_extensions_str}]) "
                f"not found in directory '{actual_file_directory}'."
            )
        return None # Optional file not found

    # If file_found_path is set, proceed to read
    try:
        with open(file_found_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except IOError as e:
        raise FileHandlerError(
            f"IOError reading file '{file_found_path.resolve()}': {e}"
        )
    except Exception as e:
        raise FileHandlerError(
            f"Unexpected error reading file '{file_found_path.resolve()}': {e}"
        )

def load_extra_files_content(persona_folder_path: Path) -> Dict[str, str]:
    """
    Loads the content of all files within the 'Extra_Files/' subdirectory
    of a given persona folder.

    Args:
        persona_folder_path: The absolute path to the persona's folder.

    Returns:
        A dictionary where keys are the relative file paths (from within 
        'Extra_Files/') and values are their string content.
        Returns an empty dictionary if the 'Extra_Files' subdirectory 
        does not exist or is empty.
    
    Raises:
        FileHandlerError: If there's an error reading any file within
                          the 'Extra_Files' subdirectory.
    """
    extra_files_path = persona_folder_path / EXTRA_FILES_SUBDIR_NAME
    loaded_content: Dict[str, str] = {}

    if not extra_files_path.exists() or not extra_files_path.is_dir():
        return loaded_content # No Extra_Files directory, or it's not a directory

    for file_path in extra_files_path.rglob('*'): # rglob to include files in subdirs of Extra_Files
        if file_path.is_file():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Store with path relative to the Extra_Files directory
                relative_path_str = str(file_path.relative_to(extra_files_path))
                loaded_content[relative_path_str] = content
            except IOError as e:
                raise FileHandlerError(
                    f"IOError reading extra file '{file_path.resolve()}': {e}"
                )
            except Exception as e:
                raise FileHandlerError(
                    f"Unexpected error reading extra file '{file_path.resolve()}': {e}"
                )
                
    return loaded_content

def load_latest_chat_log(persona_folder_path: Path) -> Optional[str]:
    """
    Finds and loads the most recent chat log file from the persona's root directory.
    The expected pattern is 'ChatLog_YYYY-MM-DD.[json|txt]'.
   

    Args:
        persona_folder_path: The absolute path to the persona's folder.

    Returns:
        The content of the latest chat log file as a string if found.
        None if no matching chat log files are found or an error occurs.
    
    Raises:
        FileHandlerError: If there's an unrecoverable error reading a found chat log file
                          (currently, prints warning and returns None for IOErrors).
    """
    latest_log_file: Optional[Path] = None
    latest_log_date: Optional[datetime] = None

    if not persona_folder_path.exists() or not persona_folder_path.is_dir():
        print(f"Warning: Persona folder {persona_folder_path.resolve()} not found for chat log loading.")
        return None

    # Ensure CHAT_LOG_SUPPORTED_EXTENSIONS includes the dot
    processed_extensions = [ext if ext.startswith('.') else f".{ext}" for ext in CHAT_LOG_SUPPORTED_EXTENSIONS]

    for ext_pattern in processed_extensions:
        # Glob for files starting with prefix and ending with current extension
        for file_path in persona_folder_path.glob(f"{CHAT_LOG_PREFIX}*{ext_pattern}"):
            if file_path.is_file():
                match = CHAT_LOG_DATE_PATTERN.match(file_path.name)
                if match:
                    date_str = match.group(1)
                    try:
                        current_file_date = datetime.strptime(date_str, "%Y-%m-%d")
                        if latest_log_date is None or current_file_date > latest_log_date:
                            latest_log_date = current_file_date
                            latest_log_file = file_path
                    except ValueError:
                        print(f"Warning: Chat log file with invalid date format in name skipped: {file_path.name}")
                        continue
    
    if latest_log_file:
        try:
            with open(latest_log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except IOError as e:
            print(f"Warning: IOError reading chat log file '{latest_log_file.resolve()}': {e}")
            # To make it stricter, uncomment:
            # raise FileHandlerError(f"IOError reading chat log file '{latest_log_file.resolve()}': {e}")
            return None
        except Exception as e:
            print(f"Warning: Unexpected error reading chat log file '{latest_log_file.resolve()}': {e}")
            # To make it stricter, uncomment:
            # raise FileHandlerError(f"Unexpected error reading chat log file '{latest_log_file.resolve()}': {e}")
            return None
            
    return None # No suitable chat log file found