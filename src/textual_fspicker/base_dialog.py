"""The base dialog code for the other dialogs in the library."""

##############################################################################
# Backward compatibility.
from __future__ import annotations

##############################################################################
# Python imports.
import sys
from pathlib import Path
from typing import Callable, TypeAlias, Union, List

##############################################################################
# Textual imports.
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

##############################################################################
# Local imports.
from .parts import DirectoryNavigation, DriveNavigation


##############################################################################
class Dialog(Vertical):
    """Layout class for the main dialog area."""


##############################################################################
class InputBar(Horizontal):
    """The input bar area of the dialog."""


##############################################################################
ButtonLabel: TypeAlias = str | Callable[[str], str]
"""The type for a button label value."""

# MODIFIED: Updated ReturnType for FileSystemPickerScreen
ReturnType: TypeAlias = Union[Path, List[Path], None]
"""The possible return types from the dialog."""


##############################################################################
class FileSystemPickerScreen(ModalScreen[ReturnType]): # MODIFIED: Updated generic type
    """Base screen for the dialogs in this library."""

    DEFAULT_CSS = """
    FileSystemPickerScreen {
        align: center middle;
    }

    /* Dialog's own styling, not its children which might be overridden by subclass's CSS */
    Dialog { 
        width: 80%;
        height: 80%;
        border: $border;
        background: $panel; /* Default background for the Dialog itself */
        border-title-color: $text;
        border-title-background: $panel;
        border-subtitle-color: $text;
        border-subtitle-background: $error;
    }

    /* 
      Default styling for children of Dialog, if a subclass like BaseFileDialog 
      doesn't provide more specific rules.
      The selectors here (e.g., Dialog > #current_path_display) are less specific 
      than those in BaseFileDialog.DEFAULT_CSS (e.g., BaseFileDialog > Dialog > #current_path_display).
    */
    Dialog > #current_path_display { 
        dock: top; 
        height: auto; /* Let content determine height */
        min-height: 1; /* Ensure at least one line */
        width: 1fr;
        padding: 0 1;
        margin-bottom: 1; 
        overflow: hidden;
        text-overflow: ellipsis;
        color: $text-muted; 
    }

    Dialog > #fsp-content-area { 
        width: 1fr;
    }

    Dialog > #fsp-content-area > DirectoryNavigation {
        height: 100%;
        width: 1fr; 
    }
    Dialog > #fsp-content-area > DriveNavigation {
        height: 100%;
    }

    Dialog > InputBar { 
        dock: bottom; 
        height: auto; /* Let content determine height */
        min-height: 1; /* For content */
        width: 1fr;
        padding-top: 1; 
        align: right middle;
        Button {
            margin-left: 1;
        }
    }
    """

    ERROR_PERMISSION_ERROR = "Permission error"
    """Error to tell there user there was a problem with permissions."""

    BINDINGS = [Binding("full_stop", "hidden"), Binding("escape", "dismiss(None)")]
    """The bindings for the dialog."""

    def __init__(
        self,
        location: str | Path = ".",
        title: str = "",
        select_button: ButtonLabel = "",
        cancel_button: ButtonLabel = "",
    ) -> None:
        super().__init__()
        self._location = location
        self._title = title
        self._select_button = select_button
        self._cancel_button = cancel_button

    def _input_bar(self) -> ComposeResult:
        yield from ()

    @staticmethod
    def _label(label: ButtonLabel, default: str) -> str:
        return label(default) if callable(label) else label or default

    def compose(self) -> ComposeResult:
        with Dialog() as dialog:
            dialog.border_title = self._title

            yield Label(id="current_path_display")

            input_bar_container = InputBar()
            with input_bar_container:
                yield from self._input_bar()
                yield Button(self._label(self._select_button, "Select"), id="select")
                yield Button(self._label(self._cancel_button, "Cancel"), id="cancel")
            yield input_bar_container

            with Horizontal(id="fsp-content-area"):
                if sys.platform == "win32":
                    yield DriveNavigation(self._location)
                yield DirectoryNavigation(self._location)


    def on_mount(self) -> None:
        dir_nav = self.query_one(DirectoryNavigation)
        current_path_label = self.query_one("#current_path_display", Label)
        current_path_label.update(str(dir_nav.location))
        dir_nav.focus()

    def _set_error(self, message: str = "") -> None:
        self.query_one(Dialog).border_subtitle = message

    @on(DriveNavigation.DriveSelected)
    def _change_drive(self, event: DriveNavigation.DriveSelected) -> None:
        dir_nav = self.query_one(DirectoryNavigation)
        dir_nav.location = event.drive_root

    @on(DirectoryNavigation.Changed)
    def _on_directory_changed(self, event: DirectoryNavigation.Changed) -> None:
        self._set_error()
        current_path_label = self.query_one("#current_path_display", Label)
        current_path_label.update(str(event.control.location))

    @on(DirectoryNavigation.Changed)
    def _clear_error(self) -> None:
        self._set_error()

    @on(DirectoryNavigation.PermissionError)
    def _show_permission_error(self) -> None:
        self._set_error(self.ERROR_PERMISSION_ERROR)

    @on(Button.Pressed, "#cancel")
    def _cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(None)

    def _action_hidden(self) -> None:
        self.query_one(DirectoryNavigation).toggle_hidden()