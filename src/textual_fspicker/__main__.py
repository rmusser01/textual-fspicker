"""Main entry point for testing the library."""

##############################################################################
# Backward compatibility.
from __future__ import annotations

##############################################################################
# Python imports.
from pathlib import Path
from typing import Union, List

##############################################################################
# Textual imports.
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal
from textual.widgets import Button, Footer, Label

##############################################################################
# Local imports.
from textual_fspicker import FileOpen, FileSave, Filters, SelectDirectory


##############################################################################
class TestApp(App[None]):
    """A simple test application."""

    CSS = """
    Screen#_default { /* MODIFIED: Changed from Screen to Screen#_default for specificity */
        align: center middle;
    } /* MODIFIED: Added closing brace */

    Horizontal {
        align: center middle;
        height: auto;
        margin-bottom: 1;
    }

    Horizontal Button {
        margin-left: 1;
        margin-right: 1;
    }

    /* MODIFIED: Ensure Label in Center can wrap text */
    Center > Label {
        width: 80%;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the layout of the test application."""
        with Horizontal():
            yield Button("Open a file", id="open")
            yield Button("Save a file", id="save")
            yield Button("Select a directory", id="directory")
        with Center():
            yield Label("Press the button to pick something")
        yield Footer()

    def show_selected(self, to_show: Union[Path, List[Path], None]) -> None:
        """Show the file that was selected by the user.

        Args:
            to_show: The file to show.
        """
        label = self.query_one("Screen#_default > Center > Label", Label) # More specific query
        if to_show is None:
            label.update("Cancelled")
        elif isinstance(to_show, list):
            # MODIFIED: Handle list of paths
            if to_show:
                paths_str = "\n".join(str(p) for p in to_show)
                label.update(f"Selected files:\n{paths_str}")
            else:
                label.update("No files selected (empty list).") # Should ideally not happen if dialog prevents
        else: # It's a single Path
            label.update(str(to_show))

    @on(Button.Pressed, "#open")
    def open_file(self) -> None:
        """Show the `FileOpen` dialog when the button is pushed."""
        self.push_screen(
            FileOpen(
                ".",
                filters=Filters(
                    ("Python", lambda p: p.suffix.lower() == ".py"),
                    ("Any", lambda _: True),
                    ("Emacs", lambda p: p.suffix.lower() == ".el"),
                    ("Lisp", lambda p: p.suffix.lower() in (".lisp", ".lsp", ".cl")),
                    ("Pascal", lambda p: p.suffix.lower() == ".pas"),
                    ("Clipper", lambda p: p.suffix.lower() in (".prg", ".ch")),
                    ("C", lambda p: p.suffix.lower() in (".c", ".h")),
                    ("C++", lambda p: p.suffix.lower() in (".cpp", ".cc", ".h")),
                ),
                allow_multiple=True, # MODIFIED: Enable multiple selection
                # must_exist=True # Default is True
            ),
            callback=self.show_selected,
        )

    @on(Button.Pressed, "#save")
    def save_file(self) -> None:
        """Show the `FileSave` dialog when the button is pushed."""
        self.push_screen(FileSave(can_overwrite=False), callback=self.show_selected)

    @on(Button.Pressed, "#directory")
    def select_directory(self) -> None:
        """show the `SelectDirectory` dialog when the button is pushed."""
        self.push_screen(SelectDirectory(), callback=self.show_selected)


##############################################################################
if __name__ == "__main__":
    TestApp().run()

### __main__.py ends here
