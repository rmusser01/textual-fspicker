"""Base file-oriented dialog."""

##############################################################################
# Backward compatibility.
from __future__ import annotations

##############################################################################
# Python imports.
import sys
from pathlib import Path
from typing import List

##############################################################################
# Textual imports.
from textual import on
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.events import Mount
from textual.widgets import Button, Input, Select


##############################################################################
# Local imports.
from .base_dialog import ButtonLabel, FileSystemPickerScreen
from .parts import DirectoryNavigation, DriveNavigation
from .path_filters import Filters
from .path_maker import MakePath


##############################################################################
class FileFilter(Select[int]):
    """The file type filtering widget.

    This widget provides a file filter drop-down selection for all dialogs
    that inherit from
    [`BaseFileDialog`][textual_fspicker.file_dialog.BaseFileDialog].
    """


##############################################################################
class BaseFileDialog(FileSystemPickerScreen):
    """The base dialog for file-oriented picking dialogs."""

    DEFAULT_CSS = """
        FileSystemPickerScreen {
            align: center middle;

            Dialog {
                width: 80%;
                height: 80%;
                border: $border;
                background: $panel;
                /* ... other Dialog styles ... */
            }

            #current_path_display {
                width: 1fr;
                padding: 0 1;
                margin-bottom: 1;
                overflow: hidden;
                text-overflow: ellipsis;
                color: $text-muted;
            }

            DirectoryNavigation {
                height: 1fr;
            }

            InputBar {
                /* height: auto; Original value */
                min-height: 3; /* MODIFIED: Force a min-height (typical button height + padding) */
                height: auto;  /* Can keep auto, min-height will ensure it's at least this */
                align: right middle;
                padding-top: 1;
                padding-right: 1;
                padding-bottom: 1; /* Total vertical padding is 2 */
                Button {
                    margin-left: 1;
                }
            }
        }
        """

    ERROR_A_FILE_MUST_BE_CHOSEN = "A file must be chosen"
    ERROR_NO_FILES_SELECTED = "No files selected"
    ERROR_SELECTION_IS_NOT_A_FILE = "Selection must be a file"
    ERROR_INPUT_NOT_FOUND = "Internal error: Filename input not found."


    def __init__(
        self,
        location: str | Path = ".",
        title: str = "Open",
        select_button: ButtonLabel = "",
        cancel_button: ButtonLabel = "",
        *,
        filters: Filters | None = None,
        default_file: str | Path | None = None,
        allow_multiple: bool = False, # MODIFIED: Added allow_multiple
    ) -> None:
        """Initialise the base dialog.

        Args:
            location: Optional starting location.
            title: Optional title.
            select_button: The label for the select button.
            cancel_button: The label for the cancel button.
            filters: Optional filters to show in the dialog.
            default_file: The default filename to place in the input.
            allow_multiple: Allow selection of multiple files.
        """
        super().__init__(
            location, title, select_button=select_button, cancel_button=cancel_button
        )
        self._filters = filters
        """The filters for the dialog."""
        self._default_file = default_file
        self._allow_multiple = allow_multiple # MODIFIED: Store allow_multiple

    def _input_bar(self) -> ComposeResult:
        """Provide any widgets for the input before, before the buttons."""

        # MODIFIED: Conditionally yield the Input widget
        if not self._allow_multiple:
            # Only yield the filename input if not in multiple selection mode
            yield Input(Path(self._default_file or "").name)
        # If self._allow_multiple is True, the Input widget for the filename is not yielded at all.

        if self._filters:
            yield FileFilter(
                self._filters.selections,
                prompt="File filter",
                value=0,
                allow_blank=False,
            )

    @on(Mount)
    @on(Mount)
    def _configure_navigation_on_mount(self) -> None:
        """Set the initial filter and allow_multiple for DirectoryNavigation."""
        dir_nav = self.query_one(DirectoryNavigation)
        if self._filters:
            dir_nav.file_filter = self._filters[0]
        dir_nav.allow_multiple = self._allow_multiple

        if self._allow_multiple:
            dir_nav.focus()
        else:
            # In single-select mode, try to focus the filename input.
            # If it's not there or focus fails, DirectoryNavigation should get focus
            # (which might already be the case from FileSystemPickerScreen.on_mount).
            try:
                filename_input_widget = self.query_one("#filename_input", Input)
                filename_input_widget.focus()
            except NoMatches:  # Corrected error type
                # If #filename_input doesn't exist, ensure dir_nav is focused.
                # FileSystemPickerScreen.on_mount already focuses DirectoryNavigation.
                # So, this explicit focus might only be needed if super().on_mount()
                # behavior changes or isn't called by a subclass.
                # For now, assuming DirectoryNavigation is already focused by the superclass
                # if #filename_input is not present.
                # If not, uncomment:
                # dir_nav.focus()
                pass

    @on(DirectoryNavigation.Selected)
    def _select_file(self, event: DirectoryNavigation.Selected) -> None:
        """Handle a file being selected in the picker.

        Args:
            event: The event to handle.
        """
        # Only update filename input if not in multi-select mode
        if not self._allow_multiple:
            try:
                file_name_input = self.query_one("#filename_input", Input)
                file_name_input.value = str(event.path.name)
                file_name_input.focus()
            except NoMatches:
                pass

    @on(Input.Changed, "#filename_input") # Only if #filename_input exists and changes
    def _clear_error_on_input_change(self) -> None:
        """Clear any error that might be showing when filename input changes."""
        super()._clear_error() # From FileSystemPickerScreen

    @on(Select.Changed, "#file_filter_select") # If FileFilter (Select widget) has this ID
    def _change_filter(self, event: Select.Changed) -> None:
        """Handle a change in the filter.

        Args:
            event: The event to handle.
        """
        if self._filters is not None and isinstance(event.value, int):
            self.query_one(DirectoryNavigation).file_filter = self._filters[event.value]
        else:
            self.query_one(DirectoryNavigation).file_filter = None
        self.query_one(DirectoryNavigation).focus()

    def _validate_and_return_single_file(self, candidate: Path) -> bool:
        """Validation hook for single file selection. To be implemented/extended by subclasses."""
        if not candidate.is_file():
            self._set_error(f"{self.ERROR_SELECTION_IS_NOT_A_FILE}: {candidate.name}")
            return False
        return True

    def _validate_and_return_multiple_files(self, candidates: List[Path]) -> bool:
        """Called by _confirm_file for multiple file selection validation."""
        # Similar to _validate_and_return_single_file, subclasses can override
        # for more specific checks on each file in the list.
        for candidate in candidates:
            if not candidate.is_file():
                self._set_error(f"{self.ERROR_SELECTION_IS_NOT_A_FILE}: {candidate.name}")
                return False
        return True

    @on(Input.Submitted)
    @on(Button.Pressed, "#select")
    def _handle_select_button_press(self, event: Button.Pressed) -> None:
        """Handle the main select ('Open', 'Save', etc.) button press."""
        event.stop()
        self._process_confirmation()

    @on(Input.Submitted, "#filename_input")
    def _handle_filename_input_submission(self, event: Input.Submitted) -> None:
        """Handle submission from the filename input (if it exists)."""
        event.stop()
        # This handler implies not self._allow_multiple because #filename_input would exist.
        self._process_confirmation()

    def _process_confirmation(self) -> None:
        """Contains the core logic for confirming file/directory selections."""
        dir_nav = self.query_one(DirectoryNavigation)

        if self._allow_multiple:
            selected_files = list(dir_nav.selected_paths)
            if not selected_files:
                self._set_error(self.ERROR_NO_FILES_SELECTED)
                dir_nav.focus()
                return

            # Call the multi-file validation hook
            if self._validate_and_return_multiple_files(selected_files):
                self.dismiss(result=selected_files)
            else:
                # Error message should have been set by _validate_and_return_multiple_files
                dir_nav.focus()
        else: # Single file selection mode
            try:
                file_name_input = self.query_one("#filename_input", Input)
                current_input_value = file_name_input.value

                if not current_input_value:
                    self._set_error(self.ERROR_A_FILE_MUST_BE_CHOSEN)
                    file_name_input.focus()
                    return

                chosen: Path
                if current_input_value.startswith("~"):
                    try:
                        chosen = MakePath.of(current_input_value).expanduser().resolve()
                    except RuntimeError as error:
                        self._set_error(str(error)); file_name_input.focus(); return
                    except FileNotFoundError:
                        self._set_error(f"Path not found: {current_input_value}"); file_name_input.focus(); return
                else:
                    chosen = (dir_nav.location / current_input_value).resolve()

                try:
                    if chosen.is_dir():
                        if sys.platform == "win32":
                            if drive_letter := MakePath.of(chosen).drive:
                                try:
                                    drive_widget = self.query_one(DriveNavigation)
                                    drive_widget.drive = drive_letter
                                except NoMatches:
                                    pass
                                except Exception:
                                    pass
                        dir_nav.location = chosen
                        file_name_input.value = "" # Clear input after navigation
                        dir_nav.focus()
                        return
                except PermissionError:
                    self._set_error(self.ERROR_PERMISSION_ERROR); dir_nav.focus(); return

                # If not a directory navigation, proceed to validate as a file
                if self._validate_and_return_single_file(chosen):
                    self.dismiss(result=chosen)
                else:
                    # Error set by _validate_and_return_single_file
                    file_name_input.focus()

            except NoMatches:
                 self._set_error(self.ERROR_INPUT_NOT_FOUND)
                 dir_nav.focus() # Fallback focus

### file_dialog.py ends here
