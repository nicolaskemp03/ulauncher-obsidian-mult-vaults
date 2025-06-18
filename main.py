import os
import gi
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction

gi.require_version("Gdk", "3.0")
from src.items import quick_capture_note, show_notes, create_note, select_note, cancel
from src.functions import (
    append_to_note_in_vault,
    find_note_in_vault,
    find_string_in_vault,
    create_note_in_vault,
    generate_daily_url,
    generate_url,
)
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
    KeywordQueryEvent,
    ItemEnterEvent,
    SystemExitEvent,
)
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
import logging

logger = logging.getLogger(__name__)


class ObisidanExtension(Extension):
    def __init__(self):
        super(ObisidanExtension, self).__init__()

        self.state = "default"
        self.content = ""
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        self.subscribe(SystemExitEvent, SystemExitEventListener())

    def reset(self):
        self.state = "default"
        self.content = ""


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        type = data.get("type")

        if type == "cancel":
            extension.reset()
            return SetUserQueryAction("")

        elif type == "create-note" and extension.state == "quick-capture-to-note":
            # Need to know which vault to create the note in.
            # Assuming 'create-note' action from quick_capture_note/create_note also carries vault info
            target_vault_path = data.get("full_vault_path") or vault_paths[0] # Fallback to first vault if not explicitly passed
            path = create_note_in_vault(target_vault_path, data.get("name"))
            append_to_note_in_vault(target_vault_path, path, extension.content)
            extension.reset()
            return HideWindowAction()

        elif type == "create-note":
            # Need to know which vault to create the note in.
            # Assuming 'create-note' action from create_note also carries vault info
            target_vault_path = data.get("full_vault_path") or vault_paths[0] # Fallback to first vault
            target_vault_name = os.path.basename(target_vault_path) # Need the name for the URL
            path = create_note_in_vault(target_vault_path, data.get("name"))
            url = generate_url(target_vault_name, path, target_vault_path) # generate_url will need to handle full_path
            return OpenAction(url)

        elif type == "quick-capture":
            # The quick_capture_note item needs to pass the vault info
            target_vault_path = data.get("full_vault_path") # Get target vault from passed data
            if not target_vault_path: # Fallback if not passed
                target_vault_path = extension.preferences.get("obsidian_vaults", "").split(',')[0].strip() # Get first vault

            quick_capture_note_path = extension.preferences["obsidian_quick_capture_note"] # This is the FILENAME, not a path
            # append_to_note_in_vault needs vault_path, filename, and content
            append_to_note_in_vault(target_vault_path, quick_capture_note_path, data.get("content"))
            return HideWindowAction()

        elif type == "quick-capture-to-note":
            keyword_quick_capture = extension.preferences["obsidian_quick_capture"]
            extension.state = "quick-capture-to-note"
            extension.content = data.get("content")
            return SetUserQueryAction(keyword_quick_capture + " ")

        elif extension.state == "quick-capture-to-note" and type == "select-note":
            # 'data.get("note")' likely returns an object with .path, .vault_name, .full_vault_path
            selected_note_data = data.get("note")
            if selected_note_data:
                quick_capture_note_path = selected_note_data['path'] # Full path to the selected note file
                target_vault_path = selected_note_data['full_vault_path'] # Full path to its vault

                # append_to_note_in_vault needs vault_path, file_path, and content
                append_to_note_in_vault(target_vault_path, quick_capture_note_path, extension.content)
                extension.reset()
                return HideWindowAction()
            else:
                return HideWindowAction() # Fallback if note data is missing

        return DoNothingAction()


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        # Get multiple vault paths from preferences (using the new ID)
        vault_paths_str = extension.preferences.get("obsidian_vaults", "").strip()

        # Handle empty configuration
        if not vault_paths_str:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Obsidian Vaults Not Configured',
                                    description='Please set your Obsidian vault paths in Ulauncher preferences (comma-separated).',
                                    highlightable=False) # No on_enter action needed here, just inform
            ])

        # Split the string into a list of individual paths and clean them up
        vault_paths = [path.strip() for path in vault_paths_str.split(',') if path.strip()]

        # If after splitting, we still have no valid paths
        if not vault_paths:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='No Valid Obsidian Vault Paths',
                                    description='Please enter at least one valid path in Ulauncher preferences.',
                                    highlightable=False)
            ])

        # --- Continue with the original preference retrievals ---
        keyword_search_note_vault = extension.preferences["obsidian_search_note_vault"]
        keyword_search_string_vault = extension.preferences["obsidian_search_string_vault"]
        keyword_open_daily = extension.preferences["obsidian_open_daily"]
        keyword_quick_capture = extension.preferences["obsidian_quick_capture"]
        number_of_notes = int(extension.preferences.get("number_of_notes", 8))

        keyword = event.get_keyword()
        search = event.get_argument()


        if extension.state == "quick-capture-to-note":
            all_notes = []
            for vault_path in vault_paths: # Loop through each vault
                vault_name = os.path.basename(vault_path)
                # We need to modify find_note_in_vault to accept vault_path
                notes_in_vault = find_note_in_vault(vault_path, search)
                for note_data in notes_in_vault: # notes_in_vault will return a list of dicts or custom objects
                    # Ensure 'note_data' has 'path' and 'name'
                    note_data['vault_name'] = vault_name
                    note_data['full_vault_path'] = vault_path
                    all_notes.append(note_data)

            # Sort if desired, e.g., by note name
            all_notes.sort(key=lambda x: x.get('name', '').lower())

            # Pass all_notes to select_note. We'll need to adapt select_note.
            items = select_note(all_notes, number_of_notes) 
            items += create_note(search) # This might also need vault context if creating in a specific vault
            items += cancel()
            return RenderResultListAction(items)

        if keyword == keyword_search_note_vault:
            all_notes = []
            for vault_path in vault_paths:
                vault_name = os.path.basename(vault_path)
                # find_note_in_vault will need to accept vault_path
                notes_in_vault = find_note_in_vault(vault_path, search)
                for note_data in notes_in_vault:
                    note_data['vault_name'] = vault_name
                    note_data['full_vault_path'] = vault_path
                    all_notes.append(note_data)

            all_notes.sort(key=lambda x: x.get('name', '').lower()) # Sort by note name

            # show_notes will need to be adapted to handle the new note_data structure
            items = show_notes(all_notes, number_of_notes) # No longer passes a single 'vault' here directly
            items += create_note(search) # This might still need a default vault
            items += cancel()
            return RenderResultListAction(items)

        elif keyword == keyword_search_string_vault:
            all_notes = [] # 'all_notes' will contain matches with preview snippets
            for vault_path in vault_paths:
                vault_name = os.path.basename(vault_path)
                # find_string_in_vault will need to accept vault_path
                notes_in_vault = find_string_in_vault(vault_path, search)
                for note_data in notes_in_vault: # Assuming note_data includes 'preview' for content matches
                    note_data['vault_name'] = vault_name
                    note_data['full_vault_path'] = vault_path
                    all_notes.append(note_data)

            all_notes.sort(key=lambda x: x.get('name', '').lower())

            # show_notes will need to handle content matches as well
            items = show_notes(all_notes, number_of_notes)
            items += create_note(search)
            items += cancel()
            return RenderResultListAction(items)

        elif keyword == keyword_open_daily:
            if not vault_paths:
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png',
                                        name='No Vaults Configured',
                                        description='Cannot open daily note without a configured vault.',
                                        highlightable=False)
                ])
            else:
                # For simplicity, open the daily note in the first configured vault
                target_vault_path = vault_paths[0]
                target_vault_name = os.path.basename(target_vault_path)

                # generate_daily_url will need to accept vault_name
                daily_note_url = generate_daily_url(target_vault_name) 
                return OpenAction(daily_note_url)
            
        elif keyword == keyword_quick_capture:
            if not vault_paths:
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png',
                                        name='No Vaults Configured',
                                        description='Cannot quick capture without a configured vault.',
                                        highlightable=False)
                ])
            else:
                # For quick capture, we need to pass the target vault name/path
                # quick_capture_note will need to be adapted to accept this
                # For simplicity, we'll pass the first vault's name and path
                target_vault_path = vault_paths[0]
                target_vault_name = os.path.basename(target_vault_path)

                # Now, quick_capture_note needs to be adjusted to accept vault info.
                # It likely prepares an item that triggers 'quick-capture' type in ItemEnterEventListener
                # We'll need to pass the target_vault_path/name through it.
                items = quick_capture_note(search, target_vault_name, target_vault_path) # Pass new args
                return RenderResultListAction(items)

        return DoNothingAction()


class SystemExitEventListener(EventListener):
    def on_event(self, event, extension):
        extension.reset()


if __name__ == "__main__":
    ObisidanExtension().run()