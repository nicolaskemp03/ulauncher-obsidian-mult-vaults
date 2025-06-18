import os
import glob
import json
import datetime
from urllib.parse import quote, urlencode
from pathlib import Path
from typing import List, Literal
import logging
from ulauncher.utils.fuzzy_search import get_score

from .moment import convert_moment_to_strptime_format

logger = logging.getLogger(__name__)


def fuzzyfinder(search: str, items: List[str]) -> List[str]:
    """
    >>> fuzzyfinder("hallo", ["hi", "hu", "hallo", "false"])
    ['hallo', 'false', 'hi', 'hu']
    """
    scores = []
    for i in items:
        score = get_score(search, get_name_from_path(i))
        scores.append((score, i))

    scores = sorted(scores, key=lambda score: score[0], reverse=True)

    return list(map(lambda score: score[1], scores))


class Note:
    def __init__(self, name: str, path: str, description: str):
        self.name = name
        self.path = path
        self.description = description

    def __repr__(self):
        return f"Note<{self.path}>"


def generate_url(vault_name: str, file_full_path: str, full_vault_path: str, mode: Literal["open", "new"] = "open") -> str:
    """
    Generates an Obsidian URL for a given file within a vault.
    vault_name: The display name of the vault (e.g., "MyVault")
    file_full_path: The absolute path to the markdown file.
    full_vault_path: The absolute path to the vault's root directory.
    mode: "open" or "new"
    """
    # Ensure the file path ends with .md for Obsidian
    if not file_full_path.endswith(".md"):
        file_full_path += ".md"

    # Calculate the path relative to the vault's root
    try:
        # Path(file_full_path) could be something like /home/user/vault/notes/MyNote.md
        # Path(full_vault_path) could be /home/user/vault
        # relative_to will give 'notes/MyNote.md'
        relative_file = Path(file_full_path).relative_to(full_vault_path)

        # Obsidian's 'file' parameter expects forward slashes, even on Windows
        relative_file_str = str(relative_file).replace(os.sep, '/')

        return (
            "obsidian://"
            + mode
            + "?"
            + urlencode({"vault": vault_name, "file": relative_file_str}, quote_via=quote)
        )
    except ValueError:
        # Fallback for cases where file_full_path is not within full_vault_path
        # (e.g., if we're trying to open a file that doesn't "belong" to this vault)
        # This should ideally not happen if paths are correctly passed.
        logger.warning(f"File {file_full_path} is not relative to vault {full_vault_path}. Falling back to file name.")
        file_name_for_url = os.path.basename(file_full_path)
        if not file_name_for_url.endswith(".md"):
            file_name_for_url += ".md"
        return (
            "obsidian://"
            + mode
            + "?"
            + urlencode({"vault": vault_name, "file": file_name_for_url}, quote_via=quote)
        )

class DailyPath:
    path: str
    date: str
    folder: str
    exists: bool

    def __init__(self, path, date, folder, exists) -> None:
        self.path = path
        self.date = date
        self.folder = folder
        self.exists = exists


class DailySettings:
    format: str
    folder: str

    def __init__(self, format, folder) -> None:
        self.folder = folder
        self.format = format


def get_daily_settings(vault_path: str) -> DailySettings: # Changed 'vault' to 'vault_path'
    daily_notes_path = os.path.join(vault_path, ".obsidian", "daily-notes.json") # Use vault_path
    # ... rest of function remains the same ...
    try:
        f = open(daily_notes_path, "r")
        daily_notes_config = json.load(f)
        f.close()
    except:
        daily_notes_config = {}
    format = daily_notes_config.get("format", "YYYY-MM-DD")
    folder = daily_notes_config.get("folder", "")

    if format == "":
        format = "YYYY-MM-DD"

    return DailySettings(format, folder)


def get_periodic_settings(vault_path: str) -> DailySettings: # Changed 'vault' to 'vault_path'
    periodic_path = os.path.join(
        vault_path, ".obsidian", "plugins", "periodic-notes", "data.json" # Use vault_path
    )
    # ... rest of function remains the same ...
    try:
        f = open(periodic_path)
        config = json.load(f)
        f.close()
    except:
        config = {}

    daily_config = config.get("daily", {})
    format = daily_config.get("format", "YYYY-MM-DD")
    folder = daily_config.get("folder", "")

    if format == "":
        format = "YYYY-MM-DD"

    return DailySettings(format, folder)


def is_obsidian_plugin_enabled(vault_path: str, name: str) -> bool: # Changed 'vault' to 'vault_path'
    core = os.path.join(vault_path, ".obsidian", "core-plugins.json") # Use vault_path
    community = os.path.join(vault_path, ".obsidian", "community-plugins.json") # Use vault_path
    # ... rest of function remains the same ...
    plugins = []
    try:
        with open(core) as f:
            core = json.load(f)
            plugins += core
    except:
        pass

    try:
        with open(community) as f:
            community = json.load(f)
            plugins += community
    except:
        pass

    return name in plugins


def get_daily_path(vault_path: str) -> DailyPath: # Changed 'vault' to 'vault_path'
    if is_obsidian_plugin_enabled(vault_path, "periodic-notes"): # Use vault_path
        settings = get_periodic_settings(vault_path) # Use vault_path
    else:
        settings = get_daily_settings(vault_path) # Use vault_path

    date = datetime.datetime.now().strftime(
        convert_moment_to_strptime_format(settings.format)
    )
    path = os.path.join(vault_path, settings.folder, date + ".md") # Use vault_path
    exists = os.path.exists(path)

    return DailyPath(path, date, settings.folder, exists)


def generate_daily_url(vault_name: str, full_vault_path: str) -> str: # New parameters
    """
    Generates an Obsidian URL to open/create today's daily note in a specific vault.
    vault_name: The display name of the vault (e.g., "MyVault")
    full_vault_path: The absolute path to the vault's root directory.
    """
    # Pass full_vault_path to get_daily_path
    daily_path_info = get_daily_path(full_vault_path)
    mode = "new"
    if daily_path_info.exists:
        mode = "open"

    # Construct the file path relative to the vault root for generate_url
    # daily_path_info.path is already the full path.
    # We need to pass vault_name, full_path to the file, and full_vault_path to generate_url
    return generate_url(
        vault_name, daily_path_info.path, full_vault_path, mode=mode
    )


def get_name_from_path(path: str, exclude_ext=True) -> str:
    """
    >>> get_name_from_path("~/home/test/bla/hallo.md")
    'hallo'

    >>> get_name_from_path("~/home/Google Drive/Brain 1.0", False)
    'Brain 1.0'
    """
    base = os.path.basename(path)
    if exclude_ext:
        split = os.path.splitext(base)
        return split[0]
    return base


def find_note_in_vault(vault_path: str, search: str) -> List[Note]: # Changed 'vault' to 'vault_path'
    """
    Searches for notes in a specific vault whose filenames match the search term.
    Returns a list of Note objects, each enriched with vault_name and full_vault_path.
    """
    search_pattern = os.path.join(vault_path, "**", "*.md") # Use vault_path
    logger.info(f"Searching in {vault_path} with pattern: {search_pattern}") # Added f-string for better logging
    files = glob.glob(search_pattern, recursive=True)
    suggestions = fuzzyfinder(search, files)

    notes_with_vault_info = []
    vault_name = get_name_from_path(vault_path, exclude_ext=False) # Get the simple vault name

    for s in suggestions:
        note = Note(name=get_name_from_path(s), path=s, description=s)
        note.vault_name = vault_name # Attach vault_name
        note.full_vault_path = vault_path # Attach full_vault_path
        notes_with_vault_info.append(note)
    return notes_with_vault_info


def find_string_in_vault(vault_path: str, search: str) -> List[Note]: # Changed 'vault' to 'vault_path'
    """
    Searches for notes in a specific vault containing the search term in their content.
    Returns a list of Note objects, each enriched with vault_name and full_vault_path.
    """
    files = glob.glob(os.path.join(vault_path, "**", "*.md"), recursive=True) # Use vault_path

    suggestions = []
    CONTEXT_SIZE = 50 # Increased context size for better preview

    search_lower = search.lower() # Do lowercasing once
    vault_name = get_name_from_path(vault_path, exclude_ext=False) # Get the simple vault name

    for file in files:
        if os.path.isfile(file):
            try:
                with open(file, "r", encoding="utf-8") as f: # Specify encoding
                    content = f.read()
                    if search_lower in content.lower():
                        # Find the first occurrence and get context
                        match_index = content.lower().find(search_lower)
                        start = max(0, match_index - CONTEXT_SIZE)
                        end = min(len(content), match_index + len(search_lower) + CONTEXT_SIZE)

                        # Add ellipses if content is truncated
                        preview_text = content[start:end].strip()
                        if start > 0:
                            preview_text = "..." + preview_text
                        if end < len(content):
                            preview_text += "..."

                        note = Note(
                            name=get_name_from_path(file),
                            path=file,
                            description=preview_text,
                        )
                        note.vault_name = vault_name # Attach vault_name
                        note.full_vault_path = vault_path # Attach full_vault_path
                        suggestions.append(note)
                        # Only add once per file, even if multiple matches
                        break 
            except Exception as e:
                logger.warning(f"Could not read file {file} for content search: {e}")
                pass # Continue to next file

    return suggestions

def create_note_in_vault(vault_path: str, name: str) -> str: # Changed 'vault' to 'vault_path'
    path = os.path.join(vault_path, name + ".md") # Use vault_path
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as f: # Added encoding
            f.write(f"# {name}")
    return path



def append_to_note_in_vault(vault_path: str, file_name_or_path: str, content: str): # New parameters names
    """
    Appends content to a specific note file within a vault.
    vault_path: The absolute path to the vault.
    file_name_or_path: Can be a filename (e.g., "Daily Note.md") or a full absolute path.
                       If it's just a filename, it's assumed to be in the vault's root.
    content: The text to append.
    """
    final_file_path = file_name_or_path

    # If file_name_or_path is not an absolute path, assume it's relative to the vault
    if not os.path.isabs(file_name_or_path):
        # If it's a filename or relative path, join it with the vault_path
        final_file_path = os.path.join(vault_path, file_name_or_path)

    # Ensure it ends with .md if it's just a name
    if not final_file_path.endswith(".md"):
        final_file_path += ".md"

    # If no specific file is given, default to the daily note path for the given vault
    if not file_name_or_path.strip(): # Handles empty string
        daily_path_info = get_daily_path(vault_path)
        final_file_path = daily_path_info.path


    logger.info(f"Appending to note: {final_file_path} in vault: {vault_path}")

    with open(final_file_path, "a", encoding="utf-8") as f: # Added encoding
        f.write(os.linesep) # Add a newline before appending
        f.write(content)



if __name__ == "__main__":
    import doctest
    import time_machine

    traveller = time_machine.travel(datetime.datetime(2021, 7, 16))
    traveller.start()

    doctest.testmod()

    traveller.stop()
