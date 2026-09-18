"""Tests for application settings persistence."""

from pathlib import Path
from unittest.mock import Mock

from PySide6.QtCore import QStandardPaths
from pytest import MonkeyPatch

from src.settings import (
    APP_SETTINGS_DIR,
    SETTINGS_FILE_NAME,
    AppSettings,
    load_settings,
    save_settings,
    settings_file_path,
)


def test_settings_file_path_uses_single_application_directory(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Store settings in one application directory under the config root."""

    writable_location = Mock(return_value=str(tmp_path))
    monkeypatch.setattr(QStandardPaths, "writableLocation", writable_location)

    assert settings_file_path() == (tmp_path / APP_SETTINGS_DIR / SETTINGS_FILE_NAME)
    writable_location.assert_called_once_with(
        QStandardPaths.StandardLocation.GenericConfigLocation
    )


def test_settings_round_trip_preserves_paths_and_options(tmp_path: Path) -> None:
    """Preserve native-looking Linux and Windows path text exactly."""

    settings_path = tmp_path / "settings.ini"
    settings = AppSettings(
        first_path="/home/example/My Files",
        second_path=r"C:\Users\%USERNAME%\My Files",
        include_first_subfolders=False,
        include_second_subfolders=True,
        excluded_extensions="tmp, .log, *.tar.gz",
        search_first_location_only=True,
        minimum_size_mb=25,
    )

    saved_path = save_settings(settings, settings_path)

    assert saved_path == settings_path
    assert load_settings(settings_path) == settings


def test_missing_or_invalid_settings_use_defaults(tmp_path: Path) -> None:
    """Use safe defaults when settings are missing or malformed."""

    settings_path = tmp_path / "settings.ini"
    assert load_settings(settings_path) == AppSettings()

    settings_path.write_text(
        "[scan]\ninclude_first_subfolders = invalid\n",
        encoding="utf-8",
    )
    assert load_settings(settings_path) == AppSettings()
