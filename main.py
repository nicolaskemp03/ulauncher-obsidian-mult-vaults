import os
import gi
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from gi.repository import Notify

gi.require_version("Gdk", "3.0")
gi.require_version("Notify", "0.7")
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
    def __init__(self):
        # This will store temporary data needed across multiple Ulauncher interactions
        # For example, the content for quick capture when a note is being selected.
        self.context_data = {}

    def on_event(self, event, extension):
        data = event.get_data()
        type = data.get("type")

        # Get general preferences which might be needed for fallbacks or specific logic
        # This should only be used as a fallback or for general configuration,
        # specific vault info should come from 'data'.
        vault_paths_str = extension.preferences.get("obsidian_vaults", "").strip()
        vault_paths = [path.strip() for path in vault_paths_str.split(',') if path.strip()]

        # --- Your existing 'cancel' logic (no change needed) ---
        if type == "cancel":
            extension.reset() # This resets extension.state and extension.content
            self.context_data = {} # Also clear context_data
            return SetUserQueryAction("")

        # --- Modified 'create-note' when in 'quick-capture-to-note' state ---
        elif type == "create-note" and extension.state == "quick-capture-to-note":
            # Data for create-note action now comes from src/items.py's create_note
            target_vault_path = data.get("full_vault_path")
            target_vault_name = data.get("vault_name")
            note_name_to_create = data.get("name") # This is the user's typed name for the new note

            # Retrieve content to append from context_data
            content_to_append = self.context_data.get("content", "")

            if not target_vault_path or not note_name_to_create or not content_to_append:
                logger.error(f"Missing data for create-note with quick-capture: {data}, content: {content_to_append}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", "Missing data to create/append note.", None).show()
                extension.reset()
                self.context_data = {}
                return HideWindowAction()

            try:
                # 1. Create the new note file
                created_note_full_path = create_note_in_vault(target_vault_path, note_name_to_create)

                # 2. Append content to the newly created note
                append_to_note_in_vault(target_vault_path, created_note_full_path, content_to_append)

                # 3. Generate URL and open
                url = generate_url(target_vault_name, created_note_full_path, target_vault_path)

                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Success", f"Created and appended to '{note_name_to_create}' in '{target_vault_name}' vault.", None).show()
                extension.reset()
                self.context_data = {}
                return OpenAction(url)
            except Exception as e:
                logger.error(f"Error creating/appending note in quick-capture-to-note state: {e}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", f"Failed to create/append note: {e}", None).show()
                extension.reset()
                self.context_data = {}
                return HideWindowAction()


        # --- Modified 'create-note' (general, not quick-capture) ---
        elif type == "create-note": # This handles the 'o cn <name>' or 'o search <name>' -> Create option
            target_vault_path = data.get("full_vault_path")
            target_vault_name = data.get("vault_name")
            note_name_to_create = data.get("name")

            if not target_vault_path or not note_name_to_create:
                logger.error(f"Missing data for general create-note: {data}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", "Missing data to create note.", None).show()
                return HideWindowAction()

            try:
                path = create_note_in_vault(target_vault_path, note_name_to_create)
                url = generate_url(target_vault_name, path, target_vault_path) # Uses target_vault_name for URI

                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Success", f"Created note '{note_name_to_create}' in '{target_vault_name}' vault.", None).show()
                return OpenAction(url)
            except Exception as e:
                logger.error(f"Error creating general note: {e}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", f"Failed to create note: {e}", None).show()
                return HideWindowAction()


        # --- Modified 'quick-capture' (to daily note) ---
        elif type == "quick-capture":
            content = data.get("content")
            target_vault_path = data.get("full_vault_path")
            target_vault_name = data.get("vault_name")

            if not target_vault_path or not content:
                logger.error(f"Missing data for quick-capture: {data}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", "Missing data for quick capture.", None).show()
                return HideWindowAction()

            try:
                # If obsidian_quick_capture_note is defined, use that filename. Otherwise, append to daily.
                # append_to_note_in_vault handles if file_name_or_path is empty (goes to daily)
                quick_capture_note_filename = extension.preferences.get("obsidian_quick_capture_note", "").strip()

                append_to_note_in_vault(target_vault_path, quick_capture_note_filename, content)

                Notify.init("Ulauncher Obsidian")
                note_target_description = "daily note" if not quick_capture_note_filename else f"'{quick_capture_note_filename}'"
                Notify.Notification.new("Obsidian Success", f"Appended to {note_target_description} in '{target_vault_name}' vault.", None).show()
                return HideWindowAction()
            except Exception as e:
                logger.error(f"Error during quick capture: {e}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", f"Failed to quick capture: {e}", None).show()
                return HideWindowAction()

        # --- Modified 'quick-capture-to-note' (initial trigger) ---
        elif type == "quick-capture-to-note":
            keyword_quick_capture = extension.preferences["obsidian_quick_capture"]
            extension.state = "quick-capture-to-note"
            self.context_data["content"] = data.get("content", "") # Store content in context

            # Set user query to initiate a search within quick-capture context
            # This will trigger KeywordQueryEventListener for the next input
            return SetUserQueryAction(keyword_quick_capture + " ")

        # --- Modified 'select-note' (after searching for note to append to) ---
        elif extension.state == "quick-capture-to-note" and type == "select-note":
            selected_note_data = data.get("selected_note_data") # This is now a dictionary
            content_to_append = self.context_data.get("content", "") # Retrieve content from context

            if not selected_note_data or not content_to_append:
                logger.error(f"Missing data for select-note with quick-capture: {data}, content: {content_to_append}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", "Missing data to append to selected note.", None).show()
                extension.reset()
                self.context_data = {}
                return HideWindowAction()

            note_name = selected_note_data.get("name")
            note_path = selected_note_data.get("path") # Full path of the selected file
            vault_name = selected_note_data.get("vault_name")
            full_vault_path = selected_note_data.get("full_vault_path")

            try:
                # append_to_note_in_vault needs vault_path and the specific file_path within that vault
                append_to_note_in_vault(full_vault_path, note_path, content_to_append)

                # Generate URL to open the selected note
                url = generate_url(vault_name, note_path, full_vault_path)

                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Success", f"Appended to '{note_name}' in '{vault_name}' vault.", None).show()
                extension.reset()
                self.context_data = {} # Clear context after successful operation
                return OpenAction(url)
            except Exception as e:
                logger.error(f"Error appending to selected note: {e}")
                Notify.init("Ulauncher Obsidian")
                Notify.Notification.new("Obsidian Error", f"Failed to append to selected note: {e}", None).show()
                extension.reset()
                self.context_data = {}
                return HideWindowAction()

        # --- Default/Fallback action ---
        return DoNothingAction()


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        # Get multiple vault paths from preferences
        vault_paths_str = extension.preferences.get("obsidian_vaults", "").strip()

        # --- Handle empty configuration ---
        if not vault_paths_str:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Obsidian Vaults Not Configured',
                                    description='Please set your Obsidian vault paths in Ulauncher preferences (comma-separated).',
                                    highlightable=False)
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

        # --- Retrieve keywords and settings ---
        keyword_search_note_vault = extension.preferences["obsidian_search_note_vault"]
        keyword_search_string_vault = extension.preferences["obsidian_search_string_vault"]
        keyword_open_daily = extension.preferences["obsidian_open_daily"]
        keyword_quick_capture = extension.preferences["obsidian_quick_capture"]
        number_of_notes = int(extension.preferences.get("number_of_notes", 8))

        keyword = event.get_keyword()
        search = event.get_argument() # User's query after the keyword

        items = [] # List to collect all result items

        # --- Quick Capture to Note (Step 2: User is searching for a note to append to) ---
        if extension.state == "quick-capture-to-note":
            all_notes_for_selection = []
            for vault_path in vault_paths:
                # find_note_in_vault now takes vault_path directly
                notes_in_vault = find_note_in_vault(vault_path, search)
                all_notes_for_selection.extend(notes_in_vault)

            # Sort the results (e.g., by name for consistency)
            all_notes_for_selection.sort(key=lambda note: note.name.lower())

            items.extend(select_note(all_notes_for_selection, number_of_notes))
            items.extend(create_note(search, vault_paths)) # Offer to create a new note to append to
            items.extend(cancel())
            return RenderResultListAction(items)


        # --- Search Note by Name (keyword_search_note_vault) ---
        elif keyword == keyword_search_note_vault:
            all_found_notes = []
            for vault_path in vault_paths:
                # find_note_in_vault returns Note objects which now have vault_name and full_vault_path
                found_in_vault = find_note_in_vault(vault_path, search)
                all_found_notes.extend(found_in_vault)

            # Sort aggregated notes (e.g., by name)
            all_found_notes.sort(key=lambda note: note.name.lower())

            items.extend(show_notes(all_found_notes, number_of_notes)) # show_notes no longer needs a separate 'vault' argument

            # If no notes found, offer to create
            if not all_found_notes and search:
                items.extend(create_note(search, vault_paths)) # Pass vault_paths for multi-vault creation

            items.extend(cancel())
            return RenderResultListAction(items)


        # --- Search String in Note Content (keyword_search_string_vault) ---
        elif keyword == keyword_search_string_vault:
            all_found_notes_by_string = []
            for vault_path in vault_paths:
                # find_string_in_vault returns Note objects with description as context
                found_in_vault = find_string_in_vault(vault_path, search)
                all_found_notes_by_string.extend(found_in_vault)

            # Sort aggregated notes
            all_found_notes_by_string.sort(key=lambda note: note.name.lower())

            items.extend(show_notes(all_found_notes_by_string, number_of_notes))

            # If no notes found, offer to create a new one
            if not all_found_notes_by_string and search:
                items.extend(create_note(search, vault_paths)) # Pass vault_paths

            items.extend(cancel())
            return RenderResultListAction(items)


        # --- Open Daily Note (keyword_open_daily) ---
        elif keyword == keyword_open_daily:
            daily_note_options = []
            for vault_path in vault_paths:
                vault_name = os.path.basename(vault_path)
                # generate_daily_url now requires vault_name and full_vault_path
                daily_url = generate_daily_url(vault_name, vault_path) 
                daily_note_options.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=f"Open Daily Note ({vault_name})",
                        description=f"Opens today's daily note in the '{vault_name}' vault.",
                        on_enter=OpenAction(daily_url)
                    )
                )
            # If there's only one vault, automatically open it. Otherwise, show options.
            if len(daily_note_options) == 1:
                return RenderResultListAction(daily_note_options)
            else:
                items.extend(daily_note_options)
                items.extend(cancel()) # Allow canceling if multiple options are shown
                return RenderResultListAction(items)


        # --- Quick Capture (keyword_quick_capture) ---
        elif keyword == keyword_quick_capture:
            # Offer quick capture options for each vault
            quick_capture_results = []
            for vault_path in vault_paths:
                vault_name = os.path.basename(vault_path)
                # quick_capture_note now requires content, vault_name, and full_vault_path
                quick_capture_results.extend(quick_capture_note(search, vault_name, vault_path))

            # If there's content, and only one vault, just show those two items.
            # Otherwise, show options + cancel
            if len(quick_capture_results) == 2 and not search: # 'Quick Capture' and 'Quick Capture to Note' for one vault
                # If no search content, and only one vault, this might be a default.
                pass # Let it go to the cancel + results below

            items.extend(quick_capture_results)
            items.extend(cancel())
            return RenderResultListAction(items)

        # --- Default/No Match ---
        return DoNothingAction()


class SystemExitEventListener(EventListener):
    def on_event(self, event, extension):
        extension.reset()


if __name__ == "__main__":
    ObisidanExtension().run()