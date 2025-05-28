"""Provides a file opening dialog."""

##############################################################################
# Backward compatibility.
from __future__ import annotations

##############################################################################
# Python imports.
from pathlib import Path
from typing import List

##############################################################################
# Local imports.
from .base_dialog import ButtonLabel
from .file_dialog import BaseFileDialog
from .path_filters import Filters


##############################################################################
class FileOpen(BaseFileDialog):
    """A file opening dialog."""

    ERROR_A_FILE_MUST_EXIST = "The file must exist"
    """An error to show a user when a file must exist."""

    def __init__(
        self,
        location: str | Path = ".",
        title: str = "Open",
        *,
        open_button: ButtonLabel = "",
        cancel_button: ButtonLabel = "",
        filters: Filters | None = None,
        must_exist: bool = True,
        default_file: str | Path | None = None,
        allow_multiple: bool = False, # MODIFIED: Added allow_multiple
    ) -> None:
        """Initialise the `FileOpen` dialog.

        Args:
            location: Optional starting location.
            title: Optional title.
            open_button: The label for the open button.
            cancel_button: The label for the cancel button.
            filters: Optional filters to show in the dialog.
            must_exist: Flag to say if the file must exist.
            default_file: The default filename to place in the input.
            allow_multiple: Allow selection of multiple files.

        Notes:
            `open_button` and `cancel_button` can either be strings that
            set the button label, or they can be functions that take the
            default button label as a parameter and return the label to use.
        """
        super().__init__(
            location,
            title,
            select_button=self._label(open_button, "Open"),
            cancel_button=cancel_button,
            filters=filters,
            default_file=default_file,
            allow_multiple=allow_multiple, # MODIFIED: Pass to super
        )
        self._must_exist = must_exist
        """Must the file exist?"""

    # MODIFIED: Implement the new validation hooks
    def _validate_and_return_single_file(self, candidate: Path) -> bool:
        """Perform the final checks on the chosen single file."""
        if not super()._validate_and_return_single_file(candidate): # Call base validation
            return False
        if self._must_exist and not candidate.exists():
            self._set_error(self.ERROR_A_FILE_MUST_EXIST)
            return False
        return True

    def _validate_and_return_multiple_files(self, candidates: List[Path]) -> bool:
        """Perform the final checks on the chosen multiple files."""
        if not super()._validate_and_return_multiple_files(candidates): # Call base validation
            return False
        for candidate in candidates:
            if self._must_exist and not candidate.exists():
                self._set_error(f"{self.ERROR_A_FILE_MUST_EXIST}: {candidate.name}")
                return False
        return True

### file_open.py ends here
