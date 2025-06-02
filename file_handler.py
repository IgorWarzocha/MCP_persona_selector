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

def load_file_content_from_entry(
    persona_folder_path: Path, 
    file_entry: FileEntry
) -> Optional[str]:
    """
    Loads the content of a single file specified by a FileEntry object,
    relative to the persona_folder_path.

    It tries to find the file using the base_name and the list of extensions_to_try
    from the FileEntry.

    Args:
        persona_folder_path: The absolute path to the persona's folder.
        file_entry: The FileEntry object describing the file to load.

    Returns:
        The content of the file as a string if found.
        None if the file is not found and is_required_flag is False.

    Raises:
        FileHandlerError: If the file is not found and is_required_flag is True,
                          or if there's an error reading the file.
    """
    # path_relative_to_persona_folder in FileEntry could be just a filename or include subdirs
    # Example: file_entry.path_relative_to_persona_folder might be "definitions/core.txt"
    # So, base_path should be persona_folder_path / file_entry.path_relative_to_persona_folder.parent
    # and the actual filename to try is file_entry.base_name with extensions.
    # However, the current FileEntry schema implies path_relative_to_persona_folder IS the path including the base_name without ext.
    # Let's stick to the previous interpretation that base_path is the full path stem.

    base_file_path_stem = persona_folder_path / file_entry.path_relative_to_persona_folder
    
    file_found_path: Optional[Path] = None
    
    # Ensure the directory for the relative path exists, if path_relative_to_persona_folder includes directories
    target_dir = base_file_path_stem.parent
    if not target_dir.exists() or not target_dir.is_dir():
        if file_entry.is_required_flag:
            raise FileHandlerError(
                f"Base directory '{target_dir.resolve()}' for file stem '{file_entry.base_name}'"
                f" (from relative path '{file_entry.path_relative_to_persona_folder}')"
                f" in persona folder '{persona_folder_path.resolve()}' does not exist."
            )
        return None # Optional file, directory not found

    for ext_to_try in file_entry.extensions_to_try:
        # Construct file name with extension
        current_ext = ext_to_try if ext_to_try.startswith('.') else f".{ext_to_try}"
        # Use the base_name from FileEntry for the filename part
        potential_file_path = target_dir / f"{file_entry.base_name}{current_ext}"
        
        if potential_file_path.exists() and potential_file_path.is_file():
            file_found_path = potential_file_path
            break
            
    if not file_found_path:
        if file_entry.is_required_flag:
            raise FileHandlerError(
                f"Required file '{file_entry.base_name}' (tried extensions: {', '.join(file_entry.extensions_to_try)}) "
                f"not found in directory '{target_dir.resolve()}' "
                f"for persona folder '{persona_folder_path.resolve()}'."
            )
        return None # Optional file not found

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