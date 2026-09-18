"""Persistent settings for Duplicate Size Scanner."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths

APP_SETTINGS_DIR = "DuplicateSizeScanner"
SETTINGS_FILE_NAME = "settings.ini"


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Store user scan settings."""

    first_path: str = ""
    second_path: str = ""
    include_first_subfolders: bool = True
    include_second_subfolders: bool = True
    excluded_extensions: str = ""
    search_first_location_only: bool = False
    minimum_size_mb: int = 0


def load_settings(path: Path | None = None) -> AppSettings:
    """Load saved application settings.

    Args:
        path: Optional settings file path. When omitted, the platform-specific
            application configuration location is used.

    Returns:
        Saved settings, or defaults if no valid settings file exists.
    """

    settings_path = path or settings_file_path()
    if not settings_path.exists():
        return AppSettings()

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with settings_path.open(encoding="utf-8") as settings_file:
            parser.read_file(settings_file)
        return AppSettings(
            first_path=parser.get("paths", "first_path", fallback=""),
            second_path=parser.get("paths", "second_path", fallback=""),
            include_first_subfolders=parser.getboolean(
                "scan",
                "include_first_subfolders",
                fallback=True,
            ),
            include_second_subfolders=parser.getboolean(
                "scan",
                "include_second_subfolders",
                fallback=True,
            ),
            excluded_extensions=parser.get(
                "scan",
                "excluded_extensions",
                fallback="",
            ),
            search_first_location_only=parser.getboolean(
                "scan",
                "search_first_location_only",
                fallback=False,
            ),
            minimum_size_mb=parser.getint(
                "scan",
                "minimum_size_mb",
                fallback=0,
            ),
        )
    except OSError, configparser.Error, ValueError:
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    """Save application settings.

    Args:
        settings: Settings values to persist.
        path: Optional settings file path. When omitted, the platform-specific
            application configuration location is used.

    Returns:
        The path where the settings were saved.

    Raises:
        OSError: If the settings directory or file cannot be written.
    """

    settings_path = path or settings_file_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    parser = configparser.ConfigParser(interpolation=None)
    parser["paths"] = {
        "first_path": settings.first_path,
        "second_path": settings.second_path,
    }
    parser["scan"] = {
        "include_first_subfolders": str(settings.include_first_subfolders),
        "include_second_subfolders": str(settings.include_second_subfolders),
        "excluded_extensions": settings.excluded_extensions,
        "search_first_location_only": str(settings.search_first_location_only),
        "minimum_size_mb": str(settings.minimum_size_mb),
    }

    with settings_path.open("w", encoding="utf-8") as settings_file:
        parser.write(settings_file)

    return settings_path


def settings_file_path() -> Path:
    """Return the platform-specific application settings path."""

    config_location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericConfigLocation
    )
    if config_location:
        return Path(config_location) / APP_SETTINGS_DIR / SETTINGS_FILE_NAME

    return Path.home() / ".config" / APP_SETTINGS_DIR / SETTINGS_FILE_NAME
