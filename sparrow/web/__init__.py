"""Bundled front-end assets (sparrow-chat.js).

Use ``asset_path()`` to locate the chat component on disk, e.g. to copy it into
your app's static directory at build time::

    from sparrow.web import asset_path
    shutil.copy(asset_path("sparrow-chat.js"), "static/js/")
"""
from pathlib import Path


def asset_path(name: str = "sparrow-chat.js") -> Path:
    """Absolute path to a bundled web asset."""
    return Path(__file__).parent / name
