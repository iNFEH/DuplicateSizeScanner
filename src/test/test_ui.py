"""Focused Qt widget tests for result actions."""

import os
from pathlib import Path
from typing import cast
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGridLayout, QMessageBox, QPushButton
import pytest

from src.scanner import DuplicateSizeGroup, FileRecord, ScanResult
from src.ui import _FILE_PATH_ROLE, DuplicateSizeScannerWindow
from src.ui_style import (
    ACCENT_DEFAULT_HEX,
    SELECTION_BACKGROUND_RGBA,
    context_menu_style,
    result_tree_style,
)


@pytest.fixture(scope="module")
def application() -> QApplication:
    """Return the QApplication required to construct widgets."""

    existing_application = QApplication.instance()
    if existing_application is not None:
        return cast(QApplication, existing_application)
    return QApplication([])


def test_selection_styles_use_checkbox_accent() -> None:
    """Use the restrained checkbox accent for rows and context menus."""

    for style in (result_tree_style("resultsTree"), context_menu_style("resultMenu")):
        assert f"background-color: {SELECTION_BACKGROUND_RGBA};" in style
        assert f"color: {ACCENT_DEFAULT_HEX};" in style
        assert "#FFFF74" not in style


def test_trash_confirmation_buttons_have_explicit_interactive_styles(
    application: QApplication,
) -> None:
    """Style both confirmation buttons without a persistent default state."""

    window = DuplicateSizeScannerWindow()
    message_box = window._build_trash_confirmation(Path("/example/file.bin"))
    yes_button = cast(
        QPushButton,
        message_box.button(QMessageBox.StandardButton.Yes),
    )
    no_button = cast(
        QPushButton,
        message_box.button(QMessageBox.StandardButton.No),
    )

    assert ":hover" in yes_button.styleSheet()
    assert ":hover" in no_button.styleSheet()
    assert yes_button.styleSheet() != no_button.styleSheet()
    assert not yes_button.isDefault()
    assert not no_button.isDefault()
    assert not yes_button.autoDefault()
    assert not no_button.autoDefault()

    message_box.deleteLater()
    window.deleteLater()
    application.processEvents()


def test_remove_result_path_updates_two_location_group(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Extract a removed path and discard a group that no longer matches."""

    window = DuplicateSizeScannerWindow()
    first_a = tmp_path / "one" / "a.bin"
    first_b = tmp_path / "one" / "b.bin"
    second_c = tmp_path / "two" / "c.bin"
    result = ScanResult(
        groups=(
            DuplicateSizeGroup(
                size=3,
                first_files=(
                    FileRecord(first_a, 3),
                    FileRecord(first_b, 3),
                ),
                second_files=(FileRecord(second_c, 3),),
            ),
        ),
        first_file_count=2,
        second_file_count=1,
        warnings=(),
    )
    window._populate_results(result)
    group_item = window._result_tree.topLevelItem(0)

    window._remove_result_path(first_a)

    assert group_item.childCount() == 2
    assert group_item.text(2) == "2 files"
    remaining_paths = {
        group_item.child(index).data(0, _FILE_PATH_ROLE)
        for index in range(group_item.childCount())
    }
    assert remaining_paths == {str(first_b), str(second_c)}

    window._remove_result_path(second_c)

    assert window._result_tree.topLevelItemCount() == 0
    window.deleteLater()
    application.processEvents()


def test_confirmed_trash_move_removes_two_location_result(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove the displayed row after a confirmed successful Trash move."""

    first_path = tmp_path / "one" / "a.bin"
    second_path = tmp_path / "two" / "b.bin"
    window = DuplicateSizeScannerWindow()
    window._populate_results(
        ScanResult(
            groups=(
                DuplicateSizeGroup(
                    size=3,
                    first_files=(FileRecord(first_path, 3),),
                    second_files=(FileRecord(second_path, 3),),
                ),
            ),
            first_file_count=1,
            second_file_count=1,
            warnings=(),
        )
    )
    accepted_message_box = Mock()
    accepted_message_box.clickedButton.return_value = Mock()
    accepted_message_box.standardButton.return_value = QMessageBox.StandardButton.Yes
    moved_paths: list[Path] = []
    monkeypatch.setattr(
        DuplicateSizeScannerWindow,
        "_build_trash_confirmation",
        lambda _self, _path: accepted_message_box,
    )
    monkeypatch.setattr("src.ui.move_file_to_trash", moved_paths.append)

    window._confirm_move_to_trash(first_path)

    assert moved_paths == [first_path]
    assert window._result_tree.topLevelItemCount() == 0
    window.deleteLater()
    application.processEvents()


def test_update_result_path_refreshes_filename_and_stored_path(
    application: QApplication,
    tmp_path: Path,
) -> None:
    """Update visible and hidden path data after a successful rename."""

    old_path = tmp_path / "before.txt"
    new_path = tmp_path / "after.log"
    other_path = tmp_path / "other" / "match.bin"
    window = DuplicateSizeScannerWindow()
    window._populate_results(
        ScanResult(
            groups=(
                DuplicateSizeGroup(
                    size=3,
                    first_files=(FileRecord(old_path, 3),),
                    second_files=(FileRecord(other_path, 3),),
                ),
            ),
            first_file_count=1,
            second_file_count=1,
            warnings=(),
        )
    )
    item = window._result_tree.topLevelItem(0).child(0)

    window._update_result_path(old_path, new_path)

    assert item.data(0, _FILE_PATH_ROLE) == str(new_path)
    assert item.text(1) == str(new_path.parent)
    assert item.text(2) == new_path.name
    assert item.toolTip(2) == new_path.name
    window.deleteLater()
    application.processEvents()


def test_scan_filter_controls_use_ninety_ten_column_stretch(
    application: QApplication,
) -> None:
    """Configure the filter row with 9:1 column stretch factors."""

    window = DuplicateSizeScannerWindow()
    layout = window._minimum_size_spin.parentWidget().layout()

    assert isinstance(layout, QGridLayout)
    assert layout.columnStretch(0) == 9
    assert layout.columnStretch(1) == 1
    assert window._minimum_size_spin.suffix() == " MB"
    window.deleteLater()
    application.processEvents()
