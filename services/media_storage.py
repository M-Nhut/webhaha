"""Local uploaded-media helpers."""

from __future__ import annotations

import os
import secrets
from os import PathLike
from typing import Protocol


class UploadedFile(Protocol):
    filename: str

    def save(self, destination: str) -> None: ...


def save_picture(upload: UploadedFile, folder_path: str | PathLike[str]) -> str:
    """Persist an uploaded picture using the legacy random file-name strategy."""
    _, extension = os.path.splitext(upload.filename)
    filename = f"{secrets.token_hex(8)}{extension}"
    upload.save(os.path.join(os.fspath(folder_path), filename))
    return filename
