import os
from typing import List
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.OpenAction import OpenAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction

from .functions import generate_url, Note


ICON_FILE = "images/icon.png"
ICON_ADD_FILE = "images/icon-add.png"


def create_note(name: str, vault_paths: list) -> list: # Added vault_paths as a parameter
    """
    Generates Ulauncher items for creating a new note.
    If multiple vaults are configured, it offers to create the note in each.
    """
    items = []

    # If no specific name is provided (e.g., just 'o cn'), offer a generic prompt
    # for the first vault, or show no vaults config message
    if not name.strip():
        if vault_paths:
            first_vault_path = vault_paths[0]
            first_vault_name = os.path.basename(first_vault_path)
            items.append(
                ExtensionResultItem(
                    icon=ICON_ADD_FILE,
                    name=f"Create a new note in '{first_vault_name}' vault",
                    description=f"Type a name to create a note in this vault.",
                    highlightable=False, # Make it not selectable, but informative
                )
            )
        else:
             items.append(
                ExtensionResultItem(
                    icon=ICON_ADD_FILE,
                    name="No Vaults Configured",
                    description="Cannot create note. Please set 'obsidian_vaults' in preferences.",
                    highlightable=False,
                )
            )
        return items

    # If a name is provided, offer to create the note in each configured vault
    for vault_path in vault_paths:
        vault_name = os.path.basename(vault_path) # Get the simple name from the path
        items.append(
            ExtensionResultItem(
                icon=ICON_ADD_FILE,
                name=f"Create '{name}' in vault: {vault_name}",
                description=f"Creates a new note named '{name}.md' in the '{vault_name}' vault.",
                on_enter=ExtensionCustomAction(
                    {"type": "create-note", "name": name, "full_vault_path": vault_path, "vault_name": vault_name}, # Pass full_vault_path and vault_name
                    keep_app_open=False, # Changed to False as note creation usually completes an action
                ),
            )
        )
    return items


def quick_capture_note(content: str, vault_name: str, full_vault_path: str) -> list: # Added vault_name, full_vault_path
    """
    Generates Ulauncher items for quick capture.
    The first option appends to the daily note in a specified vault.
    The second option allows selecting an existing note in any vault.
    """
    items = []

    # Option 1: Quick Capture to Daily Note in a specific vault
    items.append(
        ExtensionResultItem(
            icon=ICON_ADD_FILE, # Usually an 'add' icon is suitable for this
            name=f"Quick Capture to Daily Note ({vault_name})", # Show which vault
            description=f"Append text to your daily note in the '{vault_name}' vault",
            on_enter=ExtensionCustomAction(
                {"type": "quick-capture", "content": content, "full_vault_path": full_vault_path, "vault_name": vault_name}, # Pass vault info
                keep_app_open=False, # Changed to False, as this action usually completes
            ),
        )
    )

    # Option 2: Quick Capture to a selected note (searches all vaults)
    items.append(
        ExtensionResultItem(
            icon=ICON_FILE, # Generic icon for search/selection
            name="Quick Capture to existing note",
            description="Search for and append text to an existing note in any vault",
            on_enter=ExtensionCustomAction(
                {"type": "quick-capture-to-note", "content": content},
                keep_app_open=True, # Keep open to allow further search
            ),
        )
    )
    return items



def show_notes(notes: List[Note], limit = 10) -> list: # Removed 'vault' parameter
    """
    Generates Ulauncher items for displaying search results (notes).
    Assumes Note objects now contain 'vault_name' and 'full_vault_path' attributes.
    """
    items = []
    for note in notes[:limit]:
        # Construct the description to include the vault name
        description_text = f"In vault: {note.vault_name}"
        if note.description and note.description != note.path:
            description_text = f"{note.description} ({description_text})"

        # Use the generate_url function from src.functions, passing all required arguments
        # note.path is the full_file_path from find_note_in_vault or find_string_in_vault
        url = generate_url(note.vault_name, note.path, note.full_vault_path, mode="open")

        items.append(
            ExtensionResultItem(
                icon=ICON_FILE,
                name=note.name,
                description=description_text,
                on_enter=OpenAction(url),
            )
        )
    return items


def select_note(notes: List[Note], limit = 10) -> list:
    """
    Generates Ulauncher items for selecting an existing note to append content to.
    Passes a dictionary representation of the selected note, including vault info.
    """
    items = []
    for note in notes[:limit]:
        items.append(
            ExtensionResultItem(
                icon=ICON_FILE,
                name=note.name,
                description=f"{note.description} (in vault: {note.vault_name})", # Updated description
                on_enter=ExtensionCustomAction(
                    {
                        "type": "select-note",
                        "selected_note_data": { # Pass a dictionary of the note's relevant data
                            "name": note.name,
                            "path": note.path, # This is the full file path
                            "vault_name": note.vault_name,
                            "full_vault_path": note.full_vault_path,
                        },
                    },
                    keep_app_open=False, # Changed to False, as this action usually leads to append and then closes
                ),
            )
        )
    return items


def cancel():
    return [
        ExtensionResultItem(
            icon=ICON_FILE,
            name="Cancel",
            description="Cancel the current operation",
            on_enter=ExtensionCustomAction({"type": "cancel"}, keep_app_open=False), # Changed to False
        )
    ]
