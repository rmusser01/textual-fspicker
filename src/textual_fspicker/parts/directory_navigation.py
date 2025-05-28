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


##############################################################################
class DirectoryEntryStyling(NamedTuple):
    """Styling for directory entries."""

    hidden: Style
    """Styling for hidden entries."""

    name: Style
    """Styling for a name."""

    size: Style
    """Styling for a size."""

    time: Style
    selected: Style # MODIFIED: Added style for selected items


##############################################################################
class DirectoryEntry(Option):
    """A directory entry for the `DirectoryNavigation` class."""

    FOLDER_ICON: Final[Text] = Text.from_markup(":file_folder:")
    """The icon to use for a folder."""

    FILE_ICON: Final[Text] = Text.from_markup(":page_facing_up:")
    """The icon to use for a file."""

    LINK_ICON: Final[Text] = Text.from_markup(":link:")
    SELECTED_ICON: Final[Text] = Text.from_markup("[#00FF00 bold]✓[/]") # MODIFIED: Icon for selected files

    def __init__(self, location: Path, styles: DirectoryEntryStyling, selected: bool = False) -> None: # MODIFIED: Added selected flag
        self.location: Path = location.absolute()
        """The location of this directory entry."""
        self._styles = styles
        self._selected = selected # MODIFIED: Store selected state
        # The prompt itself is generated dynamically in _as_renderable
        super().__init__(self._as_renderable(location))

    @classmethod
    def _name(cls, location: Path) -> Text:
        """Get a formatted name for the given location.

        Args:
            location: The location to get the name for.

        Returns:
            The formatted name.
        """
        return Text.assemble(
            location.name, " ", cls.LINK_ICON if is_symlink(location) else ""
        )

    @staticmethod
    def _mtime(location: Path) -> str:
        """Get a formatted modification time for the given location.

        Args:
            location: The location to get the modification time for.

        Returns:
            The formatted modification time, to the nearest second.
        """
        try:
            mtime = location.stat().st_mtime
        except FileNotFoundError:
            mtime = 0
        try:
            mdatetime = datetime.fromtimestamp(int(mtime))
        except OSError:
            # It's possible, on Windows anyway, for the attempt to convert a
            # time like this to throw an OSError. So we'll capture that and
            # default to the epoch.
            #
            # https://github.com/davep/textual-fspicker/issues/6#issuecomment-2669234263
            mdatetime = datetime.fromtimestamp(0)
        return mdatetime.isoformat().replace("T", " ")

    @staticmethod
    def _size(location: Path) -> str:
        """Get a formatted size for the given location.

        Args:
            location: The location to get the size for.

        Returns:
            The formatted size.
        """
        try:
            entry_size = location.stat().st_size
        except FileNotFoundError:
            entry_size = 0
        # TODO: format well for a file browser.
        return str(entry_size)

    def _style(self, base: Style, location: Path) -> Style:
        """Decide the best style to use.

        Args:
            base: The base style to start with.
            location: The location to decide the style for.
        """
        style = base
        if DirectoryNavigation.is_hidden(location):
            style += Style(
                color=self._styles.hidden.color,
                italic=self._styles.hidden.italic,
                bold=self._styles.hidden.bold,
                underline=self._styles.hidden.underline,
            )
        # MODIFIED: Apply selected style if the entry is selected (and not a directory for selection styling)
        if self._selected and not is_dir(location):
             style = Style.combine([style, self._styles.selected])
        return style

    def _as_renderable(self, location: Path) -> RenderableType:
        """Create the renderable for this entry.

        Args:
            location: The location to turn into a renderable.

        Returns:
            The entry as a Rich renderable.
        """

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

        # MODIFIED: Add selection marker
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

    # MODIFIED: Method to update selection state and re-render prompt
    def set_selected_state(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            # Crucially, Option.prompt is a Rich renderable, not a widget.
            # To update its appearance, we need to replace it.
            # This will be handled by DirectoryNavigation by replacing the option.
            pass


##############################################################################
class DirectoryNavigation(OptionList):
    """A directory navigation widget.

    Provides a single-pane widget that lets the user navigate their way
    through a filesystenm, changing in and out of directories, and selecting
    a file.
    """

    BINDINGS = [
        ("backspace", "navigate_up"),
        # MODIFIED: Add a binding for toggling selection (e.g., spacebar)
        ("space", "toggle_selection"),
    ]

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "directory-navigation--hidden",
        "directory-navigation--name",
        "directory-navigation--size",
        "directory-navigation--time",
        "directory-navigation--selected", # MODIFIED: Style for selected items
    }
    """Component styles for the directory navigation widget."""

    DEFAULT_CSS = """
    DirectoryNavigation, DirectoryNavigation:focus {
        border: blank;
    }

    DirectoryNavigation > .directory-navigation--hidden {
        color: $text-muted;
        text-style: italic;
    }
    /* ... other styles ... */
    DirectoryNavigation > .directory-navigation--selected { /* MODIFIED */
        background: $accent-darken-2; /* Example style */
        color: $text;
        /* text-style: bold; You might want this on the name part directly */
    }
    """
    """Default styling for the widget."""

    @dataclass
    class _BaseMessage(Message):
        """Base class for directory navigation messages."""

        navigation: DirectoryNavigation
        """The directory navigation control sending the message."""

        @property
        def control(self) -> DirectoryNavigation:
            """An alias for `navigation`."""
            return self.navigation

    class Changed(_BaseMessage):
        """Message sent when the current directory has changed."""

    @dataclass
    class _PathMessage(_BaseMessage):
        """Base class for messages relating to a location in the filesystem."""

        path: Path = MakePath.of()
        """The path to the entry that was selected."""

    class Highlighted(_PathMessage):
        """Message sent when an entry in the display is highlighted."""

    class Selected(_PathMessage):
        """Message sent when an entry in the filesystem is selected."""

    class PermissionError(_PathMessage):
        """Message sent when there's a permission problem with a path."""

    _location: var[Path] = var[Path](MakePath.of(".").absolute(), init=False)
    """The current location for the directory."""

    file_filter: var[Filter | None] = var[Optional[Filter]](None)
    """The active file filter."""

    show_files: var[bool] = var(True)
    """Should files be shown and be selectable?"""

    show_hidden: var[bool] = var(False)
    """Should hidden entries be shown?"""

    sort_display: var[bool] = var(True)

    # MODIFIED: New reactive variables for multiple selection
    allow_multiple: var[bool] = var(False)
    """Should multiple files be selectable?"""

    # MODIFIED: Corrected declaration of selected_paths
    # Declare with a default set(). This set will be shared if not overridden in __init__.
    selected_paths: var[Set[Path]] = var(set())
    """The set of currently selected file paths."""


    def __init__(self, location: Path | str = ".") -> None:
        """Initialise the directory navigation widget.

        Args:
            location: The starting location.
        """
        super().__init__()
        self._mounted = False
        self._entries: list[DirectoryEntry] = [] # This stores all possible entries

        self.selected_paths = set()

        self.location = MakePath.of(location).expanduser().absolute()

    @property
    def location(self) -> Path:
        """The current location of the navigation widget."""
        return self._location

    @location.setter
    def location(self, new_location: Path | str) -> None:
        new_location = MakePath.of(new_location).expanduser().absolute()
        if self._mounted:
            self._location = new_location
        else:
            self._initial_location = new_location

    def on_mount(self) -> None:
        """Populate the widget once the DOM is ready."""
        self._mounted = True
        if hasattr(self, '_initial_location'):
            self.location = self._initial_location

    def _settle_highlight(self) -> None:
        """Settle the highlight somewhere useful if it's not anywhere."""
        if self.highlighted is None:
            self.highlighted = 0

    @property
    def is_root(self) -> bool:
        """Are we at the root of the filesystem?"""
        return self._location == MakePath.of(self._location.parent)

    @staticmethod
    def is_hidden(path: Path) -> bool:
        """Does the given path appear to be hidden?

        Args:
            path: The path to test.

        Returns:
            `True` if the path appears to be hidden, `False` if not.

        Note:
            For the moment this simply checks for the 'dot hack'. Eventually
            I'll extend this to detect hidden files in the most appropriate
            way for the current operating system.
        """
        return path.name.startswith(".") and path.name != ".."

    def hide(self, path: Path) -> bool | None:
        """Should we hide the given path?

        Args:
            path: The path to test.

        Returns:
            `True` if the path should be hidden, `False` if not.
        """
        # If there's a custom filter in place, give that a go first...
        if self.file_filter is not None and is_file(path):
            if not self.file_filter(path):
                return True
        # Either there is no custom filter, or whatever we're looking at
        # passed so far; not do final checks.


    def _clear_selections_on_nav(self) -> None:
        """Clear selections when navigating to a new directory if allow_multiple is true."""
        if self.allow_multiple and self.selected_paths:
            self.selected_paths.clear()
            # We need to re-render options to remove visual selection indicators
            self._repopulate_display() # This might be too slow if dir is large.
                                      # A more optimized way would be to update only affected options.

    def action_navigate_up(self) -> None:
        """Navigate to the parent location"""
        self._location = self._location.parent

    def _sort(self, entries: Iterable[DirectoryEntry]) -> Iterable[DirectoryEntry]:
        """Sort the entries as per the value of `sort_display`."""
        if self.sort_display:
            return sorted(
                entries,
                key=lambda entry: (not is_dir(entry.location), entry.location.name),
            )
        return entries

    @property
    def _styles(self) -> DirectoryEntryStyling:
        """The styles to use for a directory entry."""
        return DirectoryEntryStyling(
            self.get_component_rich_style("directory-navigation--hidden"),
            self.get_component_rich_style("directory-navigation--name", partial=True),
            self.get_component_rich_style("directory-navigation--size", partial=True),
            self.get_component_rich_style("directory-navigation--time", partial=True),
            self.get_component_rich_style("directory-navigation--selected", partial=True), # MODIFIED
        )

    def _repopulate_display(self) -> None:
        """Repopulate the display of directories."""
        styles = self._styles

        current_highlighted_location: Path | None = None
        # MODIFIED: Correct way to get the highlighted option's data
        highlighted_index = self.highlighted  # This is the index of the highlighted option
        if highlighted_index is not None and self.option_count > 0:  # Make sure index is valid
            try:
                # Get the option at the current highlighted index BEFORE clearing options
                highlighted_widget_before_clear = self.get_option_at_index(highlighted_index)
                if isinstance(highlighted_widget_before_clear, DirectoryEntry):
                    current_highlighted_location = highlighted_widget_before_clear.location
            except IndexError:  # Should not happen if self.highlighted is valid for current option_count
                current_highlighted_location = None

        with self.app.batch_update():
            self.clear_options()

            options_to_add: list[DirectoryEntry] = []

            if not self.is_root:
                parent_dir_entry = DirectoryEntry(self._location / "..", styles, selected=False)
                options_to_add.append(parent_dir_entry)

            # self._entries contains DirectoryEntry instances from the last _load.
            for loaded_entry_template in self._entries:
                path_location = loaded_entry_template.location
                if not self.hide(path_location):
                    is_currently_selected = path_location in self.selected_paths and self.allow_multiple
                    display_entry = DirectoryEntry(path_location, styles, selected=is_currently_selected)
                    options_to_add.append(display_entry)

            self.add_options(self._sort(options_to_add))

        # Restore highlight
        if current_highlighted_location:
            found_new_highlight_index = -1
            for i in range(self.option_count):
                option_widget = self.get_option_at_index(i)
                if isinstance(option_widget, DirectoryEntry) and option_widget.location == current_highlighted_location:
                    found_new_highlight_index = i
                    break

            if found_new_highlight_index != -1:
                self.highlighted = found_new_highlight_index
            elif self.option_count > 0:
                self.highlighted = 0
        elif self.option_count > 0:
            self.highlighted = 0

        self._settle_highlight()  # This existing method should ensure highlight is valid


    @work(exclusive=True, thread=True)
    def _load(self) -> None:
        """Load the current directory data."""
        loaded_paths: list[Path] = []
        worker = get_current_worker()
        try:
            for entry_path in self._location.iterdir(): # Use self.location directly
                if is_dir(entry_path) or (is_file(entry_path) and self.show_files):
                    loaded_paths.append(entry_path)
                if worker.is_cancelled:
                    return
        except PermissionError:
            # Ensure self is passed as the first argument for instance methods/messages
            self.post_message(self.PermissionError(self, self._location)) # Pass self (navigation instance)

        def process_loaded_paths():
            self._entries = []
            current_styles = self._styles
            for path_obj in loaded_paths:
                # Determine selection state when creating the entry
                is_selected = path_obj in self.selected_paths and self.allow_multiple
                self._entries.append(DirectoryEntry(path_obj, current_styles, selected=is_selected))
            self._repopulate_display()

        self.app.call_from_thread(process_loaded_paths)


    def _watch__location(self) -> None:
        """Reload the content if the location changes."""
        if not self._mounted: # Crucial check
            return
        self.post_message(self.Changed(self))
        if self.allow_multiple:
             self.selected_paths.clear()
        self._load()

    def _watch_selected_paths(self, old_paths: Set[Path], new_paths: Set[Path]) -> None:
        """When selected_paths change, refresh the display to show selection markers."""
        # This is a crucial part for visual feedback.
        # We need to find which options (DirectoryEntry) correspond to the changed paths
        # and tell them to re-render or replace them.

        # Simple approach: just call _repopulate_display. This rebuilds all options.
        # More complex: find specific options and update them.
        # OptionList.replace_option might be useful if we can identify the option by ID.
        if self._mounted: # Only run if mounted and options exist
             self._repopulate_display()

    def _watch_show_hidden(self) -> None:
        """Refresh the display if the show-hidden flag has changed."""
        self._repopulate_display()

    def _watch_show_files(self) -> None:
        """Reload the content if the show-files flag has changed."""
        self._load()

    def _watch_sort_display(self) -> None:
        """Refresh the display if the sort option has been changed."""
        self._repopulate_display()

    def _watch_file_filter(self) -> None:
        """Refresh the display when the file filter has been changed."""
        self._repopulate_display()

    def _watch_allow_multiple(self) -> None:
        """If allow_multiple is turned off, clear any existing selections."""
        if not self.allow_multiple and self.selected_paths:
            self.selected_paths.clear()
        # Potentially re-populate if visual state depends on allow_multiple itself
        if self._mounted:
            self._repopulate_display()

    def toggle_hidden(self) -> None:
        """Toggle the display of hidden filesystem entries."""
        self.show_hidden = not self.show_hidden

    def action_toggle_selection(self) -> None:
        """Toggle the selection state of the currently highlighted item."""
        if not self.allow_multiple:
            return

        # MODIFIED: Correct way to get the highlighted option
        highlighted_idx = self.highlighted
        if highlighted_idx is None:  # No item is highlighted
            return

        try:
            # Get the option at the current highlighted index
            highlighted_opt_widget = self.get_option_at_index(highlighted_idx)
        except IndexError:
            # This should ideally not happen if highlighted_idx is not None
            # and within the bounds of option_count, but good to be safe.
            return

        if isinstance(highlighted_opt_widget, DirectoryEntry):
            # Only allow selection of files, not directories (e.g., "..")
            # You might want to refine this if selecting directories for some other purpose
            # becomes a feature, but for file selection, this is typical.
            if is_file(highlighted_opt_widget.location):
                path_to_toggle = highlighted_opt_widget.location

                # Create a new set to trigger the reactive variable's watcher
                new_selected_paths = self.selected_paths.copy()
                if path_to_toggle in new_selected_paths:
                    new_selected_paths.remove(path_to_toggle)
                else:
                    new_selected_paths.add(path_to_toggle)

                # Assigning to self.selected_paths will trigger _watch_selected_paths,
                # which in turn calls _repopulate_display to update visuals.
                self.selected_paths = new_selected_paths
            # else:
            # Optionally, provide feedback if user tries to select a directory
            # self.app.bell()
            # else:
            # Highlighted item is not a DirectoryEntry, which shouldn't happen
            # in this specific OptionList setup.
            pass

    def _on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Handle an entry in the list being highlighted.

        Args:
            event: The event to handle.
        """
        event.stop()
        if event.option is not None:
            assert isinstance(event.option, DirectoryEntry)
            self.post_message(self.Highlighted(self, event.option.location))

    def _on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle an entry in the list being selected.

        Args:
            event: The event to handle.
        """
        event.stop()
        assert isinstance(event.option, DirectoryEntry)
        selected_location = event.option.location.resolve() # Resolve symlinks etc.

        if is_dir(selected_location):
            self.location = selected_location # Navigate
        else: # It's a file
            if self.allow_multiple:
                # In multi-select mode, Enter on a file could mean "finalize selection"
                # or "toggle and finalize if this is the only one".
                # Current Textual OptionList behavior for allow_multiple=True:
                # Space toggles, Enter usually finalizes.
                # For our custom logic:
                # We use Space (action_toggle_selection) for toggling.
                # Enter on a file when allow_multiple=True could:
                #  1. Do nothing different from space (just toggle).
                #  2. Finalize with the current self.selected_paths.
                #  3. If no other files are selected, select just this one and finalize.
                # The main dialog's "Select" button will be the primary way to finalize.
                # So, let's make Enter on a file behave like a toggle when allow_multiple is true.
                self.action_toggle_selection()
                # And then, we still post a "Selected" message for the specific file clicked,
                # so the filename input in BaseFileDialog can be updated.
                self.post_message(self.Selected(self, selected_location))

            else: # Single selection mode
                self.post_message(self.Selected(self, selected_location))

### directory_navigation.py ends here