"""Provides a widget for directory navigation."""

##############################################################################
# Backward compatibility.
from __future__ import annotations

##############################################################################
# Python imports.
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Iterable, NamedTuple, Optional, Set
import logging # For more structured logging if needed later

##############################################################################
# Rich imports.
from rich.console import RenderableType
from rich.style import Style
from rich.table import Table
from rich.text import Text

##############################################################################
# Textual imports.
from textual import work
from textual.message import Message
from textual.reactive import var
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.worker import get_current_worker
from typing_extensions import Final

##############################################################################
# Local imports.
from ..path_filters import Filter
from ..path_maker import MakePath
from ..safe_tests import is_dir, is_file, is_symlink


# Simple print-based logging for now
def debug_log(message: str):
    print(f"DEBUG: {message}", flush=True)


##############################################################################
class DirectoryEntryStyling(NamedTuple):
    """Styling for directory entries."""

    hidden: Style
    name: Style
    size: Style
    time: Style
    selected: Style


##############################################################################
class DirectoryEntry(Option):
    """A directory entry for the `DirectoryNavigation` class."""

    FOLDER_ICON: Final[Text] = Text.from_markup(":file_folder:")
    FILE_ICON: Final[Text] = Text.from_markup(":page_facing_up:")
    LINK_ICON: Final[Text] = Text.from_markup(":link:")
    SELECTED_ICON: Final[Text] = Text.from_markup("[#00FF00 bold]✓[/]")

    def __init__(self, location: Path, styles: DirectoryEntryStyling, selected: bool = False) -> None:
        self.location: Path = location.absolute()
        self._styles = styles
        self._selected = selected
        super().__init__(self._as_renderable(location))

    @classmethod
    def _name(cls, location: Path) -> Text:
        return Text.assemble(
            location.name, " ", cls.LINK_ICON if is_symlink(location) else ""
        )

    @staticmethod
    def _mtime(location: Path) -> str:
        try:
            mtime = location.stat().st_mtime
        except FileNotFoundError:
            mtime = 0
        try:
            mdatetime = datetime.fromtimestamp(int(mtime))
        except OSError:
            mdatetime = datetime.fromtimestamp(0)
        return mdatetime.isoformat().replace("T", " ")

    @staticmethod
    def _size(location: Path) -> str:
        try:
            entry_size = location.stat().st_size
        except FileNotFoundError:
            entry_size = 0
        return str(entry_size)

    def _style(self, base: Style, location: Path) -> Style:
        style = base
        if DirectoryNavigation.is_hidden(location):
            style += Style(
                color=self._styles.hidden.color,
                italic=self._styles.hidden.italic,
                bold=self._styles.hidden.bold,
                underline=self._styles.hidden.underline,
            )
        if self._selected and not is_dir(location):
             style = Style.combine([style, self._styles.selected])
        return style

    def _as_renderable(self, location: Path) -> RenderableType:
        # debug_log(f"DirectoryEntry._as_renderable for {location} with styles: {self._styles}")
        prompt = Table.grid(expand=True)
        prompt.add_column(no_wrap=True, width=1)
        prompt.add_column(no_wrap=True, justify="left", width=3)
        prompt.add_column(
            no_wrap=True,
            justify="left",
            ratio=1,
            style=self._style(self._styles.name, location),
        )
        prompt.add_column(
            no_wrap=True,
            justify="right",
            width=10,
            style=self._style(self._styles.size, location),
        )
        prompt.add_column(
            no_wrap=True,
            justify="right",
            width=20,
            style=self._style(self._styles.time, location),
        )
        prompt.add_column(no_wrap=True, width=1)

        selection_marker = self.SELECTED_ICON if self._selected and not is_dir(location) else " "

        prompt.add_row(
            selection_marker,
            self.FOLDER_ICON if is_dir(location) else self.FILE_ICON,
            self._name(location),
            self._size(location),
            self._mtime(location),
            "",
        )
        return prompt

    def set_selected_state(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected


##############################################################################
class DirectoryNavigation(OptionList):

    BINDINGS = [
        ("backspace", "navigate_up"),
        ("space", "toggle_selection"),
    ]

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "directory-navigation--hidden",
        "directory-navigation--name",
        "directory-navigation--size",
        "directory-navigation--time",
        "directory-navigation--selected",
    }

    DEFAULT_CSS = """
    DirectoryNavigation, DirectoryNavigation:focus {
        border: round green;
    }
    DirectoryNavigation > .directory-navigation--hidden { color: $text-muted; text-style: italic; }
    DirectoryNavigation > .directory-navigation--name { color: $text; }
    DirectoryNavigation > .directory-navigation--size { color: $text; }
    DirectoryNavigation > .directory-navigation--time { color: $text; }
    DirectoryNavigation > .directory-navigation--selected { background: $accent-darken-2; color: $text; }
    DirectoryNavigation > .option-list--option-highlighted { background: $accent; color: $text; }
    """

    @dataclass
    class _BaseMessage(Message):
        navigation: DirectoryNavigation
        @property
        def control(self) -> DirectoryNavigation: return self.navigation

    class Changed(_BaseMessage): pass
    @dataclass
    class _PathMessage(_BaseMessage): path: Path = MakePath.of()
    class Highlighted(_PathMessage): pass
    class Selected(_PathMessage): pass
    class PermissionError(_PathMessage): pass

    _location: var[Path] = var[Path](MakePath.of(".").absolute(), init=False)
    file_filter: var[Filter | None] = var[Optional[Filter]](None)
    show_files: var[bool] = var(True)
    show_hidden: var[bool] = var(False)
    sort_display: var[bool] = var(True)
    allow_multiple: var[bool] = var(False)
    selected_paths: var[Set[Path]] = var(set())

    def __init__(self, location: Path | str = ".") -> None:
        super().__init__()
        self._mounted = False
        self._entries: list[DirectoryEntry] = []
        self.selected_paths = set()
        self._initial_location = MakePath.of(location).expanduser().absolute()
        debug_log(f"DirectoryNavigation.__init__ - initial_location set to: {self._initial_location}")


    @property
    def location(self) -> Path:
        return self._location

    @location.setter
    def location(self, new_location: Path | str) -> None:
        resolved_new_location = MakePath.of(new_location).expanduser().absolute()
        debug_log(f"DirectoryNavigation.location.setter - Attempting to set to: {resolved_new_location} (was {self._location if '_location' in self.__dict__ else 'not set'})")
        if self._mounted:
            if self._location != resolved_new_location:
                self._location = resolved_new_location # Triggers _watch__location
            else:
                debug_log("DirectoryNavigation.location.setter - New location is same as current, not re-assigning.")
        else:
            self._initial_location = resolved_new_location
            debug_log(f"DirectoryNavigation.location.setter - Not mounted, _initial_location updated to: {self._initial_location}")


    def on_mount(self) -> None:
        debug_log("DirectoryNavigation.on_mount - Start.")
        self._mounted = True
        if hasattr(self, '_initial_location'):
            debug_log(f"DirectoryNavigation.on_mount - Has _initial_location: {self._initial_location}. Setting self.location.")
            # This assignment will now use the reactive setter
            self.location = self._initial_location
        else:
            # This case should ideally not happen if __init__ sets _initial_location
            debug_log("DirectoryNavigation.on_mount - No _initial_location. Triggering _load manually for current _location.")
            self._location = MakePath.of(".").absolute() # Ensure _location is a Path
            self._load()
        debug_log("DirectoryNavigation.on_mount - End.")


    def _settle_highlight(self) -> None:
        if self.highlighted is None and self.option_count > 0:
            self.highlighted = 0

    @property
    def is_root(self) -> bool:
        return self._location == MakePath.of(self._location.parent)

    @staticmethod
    def is_hidden(path: Path) -> bool:
        return path.name.startswith(".") and path.name != ".."

    def _clear_selections_on_nav(self) -> None:
        if self.allow_multiple and self.selected_paths:
            self.selected_paths.clear()
            self._repopulate_display()

    def action_navigate_up(self) -> None:
        self.location = self._location.parent

    def _sort(self, entries: Iterable[DirectoryEntry]) -> Iterable[DirectoryEntry]:
        if self.sort_display:
            return sorted(entries, key=lambda entry: (not is_dir(entry.location), entry.location.name))
        return entries

    @property
    def _styles(self) -> DirectoryEntryStyling:
        return DirectoryEntryStyling(
            self.get_component_rich_style("directory-navigation--hidden"),
            self.get_component_rich_style("directory-navigation--name", partial=True),
            self.get_component_rich_style("directory-navigation--size", partial=True),
            self.get_component_rich_style("directory-navigation--time", partial=True),
            self.get_component_rich_style("directory-navigation--selected", partial=True),
        )

    def _repopulate_display(self) -> None:
        debug_log(f"_repopulate_display started. Current location: {self.location}. Num raw _entries: {len(self._entries)}")
        styles = self._styles
        current_highlighted_location: Path | None = None
        highlighted_index = self.highlighted
        if highlighted_index is not None and self.option_count > 0:
            try:
                highlighted_widget_before_clear = self.get_option_at_index(highlighted_index)
                if isinstance(highlighted_widget_before_clear, DirectoryEntry):
                    current_highlighted_location = highlighted_widget_before_clear.location
            except IndexError: pass

        with self.app.batch_update():
            self.clear_options()
            options_to_add: list[DirectoryEntry] = []
            if not self.is_root:
                parent_dir_entry = DirectoryEntry(self._location / "..", styles, selected=False)
                options_to_add.append(parent_dir_entry)

            for loaded_entry_template in self._entries:
                path_location = loaded_entry_template.location
                # debug_log(f"  Processing entry: {path_location.name}")

                if not self.show_hidden and self.is_hidden(path_location) and path_location.name != "..":
                    # debug_log(f"    Skipping hidden: {path_location.name}")
                    continue

                if self.file_filter is not None and is_file(path_location):
                    if not self.file_filter(path_location):
                        # debug_log(f"    Skipping due to filter: {path_location.name}")
                        continue

                is_currently_selected = path_location in self.selected_paths and self.allow_multiple
                display_entry = DirectoryEntry(path_location, styles, selected=is_currently_selected)
                options_to_add.append(display_entry)

            debug_log(f"_repopulate_display - About to add {len(options_to_add)} options.")
            if options_to_add: # Only add if there's something to add
                self.add_options(self._sort(options_to_add))
            debug_log(f"_repopulate_display - Options added. Option count now: {self.option_count}")


        if current_highlighted_location:
            found_new_highlight_index = -1
            for i in range(self.option_count): # Iterate over current options
                option_widget = self.get_option_at_index(i)
                if isinstance(option_widget, DirectoryEntry) and option_widget.location == current_highlighted_location:
                    found_new_highlight_index = i
                    break
            if found_new_highlight_index != -1:
                self.highlighted = found_new_highlight_index
            elif self.option_count > 0: self.highlighted = 0
        elif self.option_count > 0: self.highlighted = 0
        self._settle_highlight()
        debug_log(f"_repopulate_display finished. Highlighted index: {self.highlighted}")


    @work(exclusive=True, thread=True)
    def _load(self) -> None:
        debug_log(f"_load started in worker for location: {self.location}")
        loaded_paths: list[Path] = []
        worker = get_current_worker()
        try:
            # Ensure self.location is actually a Path object for iterdir
            current_location_path = MakePath.of(self.location)
            if not current_location_path.is_dir(): # Check if it's a directory
                debug_log(f"_load - Location {current_location_path} is not a directory. Aborting load.")
                # Optionally post an error or clear entries
                self.app.call_from_thread(lambda: setattr(self, '_entries', []))
                self.app.call_from_thread(self._repopulate_display)
                return

            for entry_path in current_location_path.iterdir():
                if is_dir(entry_path) or (is_file(entry_path) and self.show_files):
                    loaded_paths.append(entry_path)
                if worker.is_cancelled:
                    debug_log("_load - Worker cancelled during iterdir.")
                    return
            debug_log(f"_load - iterdir completed. Found {len(loaded_paths)} potential paths.")
        except PermissionError:
            debug_log(f"_load - PermissionError for location: {self.location}")
            self.post_message(self.PermissionError(self, self.location))
            loaded_paths = [] # Ensure loaded_paths is empty on error to clear display
        except Exception as e:
            debug_log(f"_load - Unexpected error for location {self.location}: {e}")
            loaded_paths = []


        def process_loaded_paths_in_main_thread():
            debug_log(f"process_loaded_paths_in_main_thread - Received {len(loaded_paths)} paths.")
            self._entries = []  # Clear previous raw entries
            current_styles = self._styles
            for path_obj in loaded_paths:
                is_selected = path_obj in self.selected_paths and self.allow_multiple
                self._entries.append(DirectoryEntry(path_obj, current_styles, selected=is_selected))
            debug_log(f"process_loaded_paths_in_main_thread - self._entries populated with {len(self._entries)} items.")
            self._repopulate_display()

        if not worker.is_cancelled:
            self.app.call_from_thread(process_loaded_paths_in_main_thread)
        else:
            debug_log("_load - Worker was cancelled, not calling process_loaded_paths_in_main_thread.")


    def _watch__location(self, old_location: Path, new_location: Path) -> None:
        debug_log(f"_watch__location: changed from {old_location} to {new_location}. Mounted: {self._mounted}")
        if not self._mounted:
            return
        # self.post_message(self.Changed(self)) # Already done by _location reactive var
        if self.allow_multiple:
             self.selected_paths.clear() # This will trigger its own watcher
        if old_location != new_location: # Only load if location actually changed
            self._load()
        else:
            debug_log("_watch__location: new location is same as old, _load not called.")


    def _watch_selected_paths(self, old_paths: Set[Path], new_paths: Set[Path]) -> None:
        debug_log(f"_watch_selected_paths. Mounted: {self._mounted}, Option count: {self.option_count}")
        if self._mounted and self.option_count >= 0: # Allow 0 if list becomes empty
             self._repopulate_display()

    def _watch_show_hidden(self, old_val: bool, new_val: bool) -> None:
        debug_log(f"_watch_show_hidden: changed to {new_val}. Mounted: {self._mounted}")
        if self._mounted:
            self._repopulate_display()

    def _watch_show_files(self, old_val: bool, new_val: bool) -> None:
        debug_log(f"_watch_show_files: changed to {new_val}. Mounted: {self._mounted}")
        if self._mounted:
            self._load()

    def _watch_sort_display(self, old_val: bool, new_val: bool) -> None:
        debug_log(f"_watch_sort_display: changed to {new_val}. Mounted: {self._mounted}")
        if self._mounted:
            self._repopulate_display()

    def _watch_file_filter(self) -> None: # Filter object itself changes
        debug_log(f"_watch_file_filter changed. Mounted: {self._mounted}")
        if self._mounted:
            self._repopulate_display()

    def _watch_allow_multiple(self, old_val: bool, new_val: bool) -> None:
        debug_log(f"_watch_allow_multiple: changed to {new_val}. Mounted: {self._mounted}")
        if not new_val and self.selected_paths:
            self.selected_paths.clear()
        if self._mounted:
            self._repopulate_display()
    # ... (rest of the DirectoryNavigation class remains the same)
    def toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden

    def action_toggle_selection(self) -> None:
        if not self.allow_multiple:
            return
        highlighted_idx = self.highlighted
        if highlighted_idx is None:
            return
        try:
            highlighted_opt_widget = self.get_option_at_index(highlighted_idx)
        except IndexError:
            return

        if isinstance(highlighted_opt_widget, DirectoryEntry):
            if is_file(highlighted_opt_widget.location):
                path_to_toggle = highlighted_opt_widget.location
                new_selected_paths = self.selected_paths.copy()
                if path_to_toggle in new_selected_paths:
                    new_selected_paths.remove(path_to_toggle)
                else:
                    new_selected_paths.add(path_to_toggle)
                self.selected_paths = new_selected_paths
            pass

    def _on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        event.stop()
        if event.option is not None:
            assert isinstance(event.option, DirectoryEntry)
            self.post_message(self.Highlighted(self, event.option.location))

    def _on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        assert isinstance(event.option, DirectoryEntry)
        selected_location = event.option.location.resolve()

        if is_dir(selected_location):
            self.location = selected_location
        else:
            if self.allow_multiple:
                self.action_toggle_selection()
                self.post_message(self.Selected(self, selected_location))

            else:
                self.post_message(self.Selected(self, selected_location))