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
    """The file type filtering widget."""


##############################################################################
class BaseFileDialog(FileSystemPickerScreen):
    """The base dialog for file-oriented picking dialogs."""

    DEFAULT_CSS = """
        BaseFileDialog > Dialog {
            width: 80%;
            height: 80%;
            /* background: $panel; Reverted from purple */
            padding: 1; 
        }

        BaseFileDialog > Dialog > #current_path_display {
            dock: top; 
            height: 2; 
            width: 1fr;
            padding: 0 1; 
            margin-bottom: 1; 
            /* background: $panel; Reverted from orange */
            overflow: hidden;
            text-overflow: ellipsis;
            color: $text-muted; /* Ensure this is visible against panel */
        }
        
        BaseFileDialog > Dialog > #fsp-content-area {
            width: 1fr; 
            /* background: $panel; Reverted from red */
        }

        BaseFileDialog > Dialog > #fsp-content-area > DirectoryNavigation {
            height: 100%; 
            width: 1fr; 
            /* background: $panel; Reverted from green */
        }
        
        BaseFileDialog > Dialog > #fsp-content-area > DriveNavigation {
            height: 100%; 
            /* background: $panel; Reverted from blue */
        }

        BaseFileDialog > Dialog > InputBar { 
            dock: bottom; 
            height: 3; 
            width: 1fr;
            padding-top: 1; 
            /* background: $panel; Reverted from yellow */
            align: right middle; 
            
            Button {
                margin-left: 1;
            }
            FileFilter { 
                max-height: 1;
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
        allow_multiple: bool = False,
    ) -> None:
        super().__init__(
            location, title, select_button=select_button, cancel_button=cancel_button
        )
        self._filters = filters
        self._default_file = default_file
        self._allow_multiple = allow_multiple

    def _input_bar(self) -> ComposeResult:
        if not self._allow_multiple:
            yield Input(Path(self._default_file or "").name, id="filename_input")

        if self._filters:
            yield FileFilter(
                self._filters.selections,
                prompt="File filter",
                value=0,
                allow_blank=False,
                id="file_filter_select"
            )

    @on(Mount)
    def _configure_navigation_on_mount(self) -> None:
        dir_nav = self.query_one(DirectoryNavigation)
        if self._filters:
            dir_nav.file_filter = self._filters[0]
        dir_nav.allow_multiple = self._allow_multiple

        if self._allow_multiple:
            pass
        else:
            try:
                filename_input_widget = self.query_one("#filename_input", Input)
                filename_input_widget.focus()
            except NoMatches:
                pass

    @on(DirectoryNavigation.Selected)
    def _select_file(self, event: DirectoryNavigation.Selected) -> None:
        if not self._allow_multiple:
            try:
                file_name_input = self.query_one("#filename_input", Input)
                file_name_input.value = str(event.path.name)
                file_name_input.focus()
            except NoMatches:
                pass

    @on(Input.Changed, "#filename_input")
    def _clear_error_on_input_change(self) -> None:
        super()._clear_error()

    @on(Select.Changed, "#file_filter_select")
    def _change_filter(self, event: Select.Changed) -> None:
        if self._filters is not None and isinstance(event.value, int):
            self.query_one(DirectoryNavigation).file_filter = self._filters[event.value]
        else:
            self.query_one(DirectoryNavigation).file_filter = None
        self.query_one(DirectoryNavigation).focus()

    def _validate_and_return_single_file(self, candidate: Path) -> bool:
        if not candidate.is_file():
            self._set_error(f"{self.ERROR_SELECTION_IS_NOT_A_FILE}: {candidate.name}")
            return False
        return True

    def _validate_and_return_multiple_files(self, candidates: List[Path]) -> bool:
        for candidate in candidates:
            if not candidate.is_file():
                self._set_error(f"{self.ERROR_SELECTION_IS_NOT_A_FILE}: {candidate.name}")
                return False
        return True

    @on(Input.Submitted)
    @on(Button.Pressed, "#select")
    def _handle_select_button_press(self, event: Button.Pressed) -> None:
        event.stop()
        self._process_confirmation()

    @on(Input.Submitted, "#filename_input")
    def _handle_filename_input_submission(self, event: Input.Submitted) -> None:
        event.stop()
        self._process_confirmation()

    def _process_confirmation(self) -> None:
        dir_nav = self.query_one(DirectoryNavigation)

        if self._allow_multiple:
            selected_files = list(dir_nav.selected_paths)
            if not selected_files:
                self._set_error(self.ERROR_NO_FILES_SELECTED)
                dir_nav.focus()
                return

            if self._validate_and_return_multiple_files(selected_files):
                self.dismiss(result=selected_files)
            else:
                dir_nav.focus()
        else:
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
                        file_name_input.value = ""
                        dir_nav.focus()
                        return
                except PermissionError:
                    self._set_error(self.ERROR_PERMISSION_ERROR); dir_nav.focus(); return

                if self._validate_and_return_single_file(chosen):
                    self.dismiss(result=chosen)
                else:
                    file_name_input.focus()

            except NoMatches:
                 self._set_error(self.ERROR_INPUT_NOT_FOUND)
                 dir_nav.focus()