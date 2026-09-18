"""Qt main window for Duplicate Size Scanner."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .file_actions import FileActionError, move_file_to_trash, open_file, rename_file
from .scanner import (
    FileRecord,
    ScanError,
    ScanRequest,
    ScanResult,
    find_duplicate_sizes,
    parse_excluded_extensions,
)
from .settings import AppSettings, load_settings, save_settings
from .ui_style import (
    context_menu_style,
    primary_accent_button_style,
    progress_bar_style,
    result_tree_style,
    secondary_accent_button_style,
)

LOGGER = logging.getLogger(__name__)

_BYTES_PER_MEGABYTE = 1_000_000
_FILE_PATH_ROLE = Qt.ItemDataRole.UserRole.value
_SINGLE_LOCATION_GROUP_ROLE = _FILE_PATH_ROLE + 1


class _ScanWorker(QObject):
    status_changed = Signal(str)
    warning_reported = Signal(str)
    scan_completed = Signal(object)
    scan_failed = Signal(str)
    finished = Signal()

    def __init__(self, request: ScanRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        try:
            result = find_duplicate_sizes(
                self._request,
                status_callback=self.status_changed.emit,
                warning_callback=self.warning_reported.emit,
            )
            self.scan_completed.emit(result)
        except ScanError as err:
            self.scan_failed.emit(str(err))
        except Exception as err:
            LOGGER.exception("Unexpected duplicate scan failure")
            self.scan_failed.emit(f"An unexpected scan error occurred: {err}")
        finally:
            self.finished.emit()


class DuplicateSizeScannerWindow(QMainWindow):
    """Main window for the program."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: _ScanWorker | None = None
        self._warnings: list[str] = []

        self._first_edit = QLineEdit()
        self._second_edit = QLineEdit()
        self._first_browse_button = QPushButton("Browse")
        self._second_browse_button = QPushButton("Browse")
        self._first_recursive_check = QCheckBox("Include subfolders")
        self._second_recursive_check = QCheckBox("Include subfolders")
        self._single_location_check = QCheckBox("Search location 1 only")
        self._excluded_extensions_edit = QLineEdit()
        self._minimum_size_spin = QSpinBox()
        self._search_button = QPushButton("Search")
        self._exit_button = QPushButton("Exit")
        self._progress_bar = QProgressBar()
        self._result_tree = QTreeWidget()

        self._first_recursive_check.setChecked(True)
        self._second_recursive_check.setChecked(True)
        self._build_window()
        self._single_location_check.toggled.connect(self._update_second_location_state)
        self._apply_settings(load_settings())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Save settings before the window closes."""

        if self._thread is not None:
            QMessageBox.warning(
                self,
                "Search in progress",
                "Please wait until the current search finishes before closing.",
            )
            event.ignore()
            return

        self._save_current_settings(show_warning=False)
        event.accept()

    def _build_window(self) -> None:
        self.setWindowTitle("Duplicate Size Scanner")
        self.setMinimumSize(980, 640)
        self.resize(2300, 720)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(14)

        control_layout.addWidget(
            self._build_path_group(
                "Location 1",
                "Select the first folder to compare.",
                self._first_edit,
                self._first_browse_button,
                self._first_recursive_check,
                self._browse_first_folder,
                "firstFolder",
                self._single_location_check,
            )
        )
        self._second_location_group = self._build_path_group(
            "Location 2",
            "Select the second, separate folder to compare.",
            self._second_edit,
            self._second_browse_button,
            self._second_recursive_check,
            self._browse_second_folder,
            "secondFolder",
        )
        control_layout.addWidget(self._second_location_group)
        control_layout.addWidget(self._build_filters_group())
        control_layout.addWidget(self._build_progress_panel())
        control_layout.addStretch(1)
        control_layout.addLayout(self._build_button_row())

        root_layout.addWidget(control_panel, 2)
        root_layout.addWidget(self._build_results_group(), 3)

    def _build_path_group(
        self,
        title: str,
        helper_text: str,
        line_edit: QLineEdit,
        browse_button: QPushButton,
        recursive_check: QCheckBox,
        browse_slot: Callable[[], None],
        object_prefix: str,
        additional_check: QCheckBox | None = None,
    ) -> QGroupBox:
        group_box = QGroupBox(title)
        layout = QVBoxLayout(group_box)
        layout.setSpacing(8)
        helper_label = QLabel(helper_text)
        helper_label.setWordWrap(True)

        row_layout = QHBoxLayout()
        line_edit.setClearButtonEnabled(True)
        line_edit.setMinimumHeight(34)
        line_edit.setPlaceholderText("Select or enter a folder path")
        browse_button.setMinimumHeight(34)
        _style_secondary_button(browse_button, f"{object_prefix}BrowseButton")
        browse_button.clicked.connect(browse_slot)
        row_layout.addWidget(line_edit, 1)
        row_layout.addWidget(browse_button)

        layout.addWidget(helper_label)
        layout.addLayout(row_layout)
        layout.addWidget(recursive_check)

        if additional_check is not None:
            layout.addWidget(additional_check)

        return group_box

    def _build_filters_group(self) -> QGroupBox:
        group_box = QGroupBox("Scan filters")
        layout = QGridLayout(group_box)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)
        layout.setColumnStretch(0, 9)
        layout.setColumnStretch(1, 1)

        extension_label = QLabel("Excluded file extensions")
        minimum_size_label = QLabel("Minimum size")
        self._excluded_extensions_edit.setClearButtonEnabled(True)
        self._excluded_extensions_edit.setMinimumHeight(34)
        self._excluded_extensions_edit.setPlaceholderText(
            "Example: tmp, .log, *.tar.gz"
        )
        self._excluded_extensions_edit.setToolTip(
            "Separate extensions with commas. Dots and wildcards are optional."
        )
        self._minimum_size_spin.setRange(0, 2_000_000)
        self._minimum_size_spin.setSuffix(" MB")
        self._minimum_size_spin.setMinimumHeight(34)
        self._minimum_size_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._minimum_size_spin.setToolTip(
            "Files smaller than this decimal-megabyte value are ignored. "
            "Zero-byte files are always ignored."
        )

        layout.addWidget(extension_label, 0, 0)
        layout.addWidget(minimum_size_label, 0, 1)
        layout.addWidget(self._excluded_extensions_edit, 1, 0)
        layout.addWidget(self._minimum_size_spin, 1, 1)

        return group_box

    def _build_progress_panel(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        self._progress_bar.setObjectName("scanProgressBar")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(28)
        self._progress_bar.setFormat("Ready")
        self._progress_bar.setStyleSheet(progress_bar_style("scanProgressBar"))

        layout.addWidget(self._progress_bar)

        return frame

    def _build_results_group(self) -> QGroupBox:
        group_box = QGroupBox("Duplicate files")
        layout = QVBoxLayout(group_box)
        layout.setSpacing(8)

        self._result_tree.setObjectName("resultsTree")
        self._result_tree.setColumnCount(4)
        self._result_tree.setHeaderLabels(
            ["Location", "Folder address", "File name", "Size"]
        )
        self._result_tree.setAlternatingRowColors(True)
        self._result_tree.setRootIsDecorated(True)
        self._result_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._result_tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._result_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._result_tree.customContextMenuRequested.connect(
            self._show_result_context_menu
        )
        self._result_tree.setStyleSheet(result_tree_style("resultsTree"))
        header = self._result_tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(70)
        self._result_tree.setColumnWidth(0, 120)
        self._result_tree.setColumnWidth(1, 360)
        self._result_tree.setColumnWidth(2, 600)
        self._result_tree.setColumnWidth(3, 170)

        layout.addWidget(self._result_tree, 1)

        return group_box

    def _build_button_row(self) -> QHBoxLayout:
        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self._search_button.setObjectName("searchButton")
        self._search_button.setMinimumHeight(38)
        self._search_button.setStyleSheet(primary_accent_button_style("searchButton"))
        self._search_button.clicked.connect(self._start_search)
        self._exit_button.setMinimumHeight(38)
        _style_secondary_button(self._exit_button, "exitButton")
        self._exit_button.clicked.connect(self.close)
        button_row.addWidget(self._search_button)
        button_row.addStretch(1)
        button_row.addWidget(self._exit_button)

        return button_row

    def _apply_settings(self, settings: AppSettings) -> None:
        self._first_edit.setText(settings.first_path)
        self._second_edit.setText(settings.second_path)
        self._first_recursive_check.setChecked(settings.include_first_subfolders)
        self._second_recursive_check.setChecked(settings.include_second_subfolders)
        self._excluded_extensions_edit.setText(settings.excluded_extensions)
        self._single_location_check.setChecked(settings.search_first_location_only)
        self._minimum_size_spin.setValue(max(0, settings.minimum_size_mb))
        self._update_second_location_state(settings.search_first_location_only)

    def _browse_first_folder(self) -> None:
        self._browse_folder("Select location 1", self._first_edit)

    def _browse_second_folder(self) -> None:
        self._browse_folder("Select location 2", self._second_edit)

    def _browse_folder(self, title: str, line_edit: QLineEdit) -> None:
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            title,
            self._initial_browse_path(line_edit.text()),
        )
        if selected_folder:
            line_edit.setText(selected_folder)

    def _start_search(self) -> None:
        first_text = self._first_edit.text().strip()
        second_text = self._second_edit.text().strip()
        search_first_only = self._single_location_check.isChecked()
        if not first_text or (not search_first_only and not second_text):
            QMessageBox.warning(
                self,
                "Missing locations",
                "Select each enabled location before you start a search.",
            )
            return

        request = ScanRequest(
            first_root=Path(first_text).expanduser(),
            second_root=(None if search_first_only else Path(second_text).expanduser()),
            include_first_subfolders=self._first_recursive_check.isChecked(),
            include_second_subfolders=self._second_recursive_check.isChecked(),
            excluded_extensions=parse_excluded_extensions(
                self._excluded_extensions_edit.text()
            ),
            minimum_size_bytes=(self._minimum_size_spin.value() * _BYTES_PER_MEGABYTE),
        )
        self._save_current_settings()
        self._reset_search_ui()
        self._set_controls_enabled(False)
        self._search_button.setText("Searching...")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFormat("Preparing search...")

        self._thread = QThread(self)
        self._worker = _ScanWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status_changed.connect(self._set_progress_message)
        self._worker.warning_reported.connect(self._append_warning)
        self._worker.scan_completed.connect(self._handle_scan_completed)
        self._worker.scan_failed.connect(self._handle_scan_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._handle_thread_finished)
        self._thread.start()

    @Slot(object)
    def _handle_scan_completed(self, result: ScanResult) -> None:
        self._populate_results(result)
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._progress_bar.setFormat("Finished")
        self._search_button.setText("Search again")

        if self._warnings:
            visible_warnings = "\n".join(self._warnings[:10])
            remaining_count = len(self._warnings) - 10
            if remaining_count > 0:
                visible_warnings += f"\n...and {remaining_count} more warnings."
            QMessageBox.warning(
                self,
                "Search finished with warnings",
                "The search finished, but some entries were skipped:\n\n"
                + visible_warnings,
            )

    def _handle_scan_failed(self, message: str) -> None:
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Failed")
        self._search_button.setText("Search")
        QMessageBox.critical(self, "Search failed", message)

    def _handle_thread_finished(self) -> None:
        self._set_controls_enabled(True)
        self._thread = None
        self._worker = None

    def _populate_results(self, result: ScanResult) -> None:
        self._result_tree.clear()
        if not result.groups:
            return

        for group in result.groups:
            total_matches = len(group.first_files) + len(group.second_files)
            group_item = QTreeWidgetItem(
                [
                    "Matching size",
                    "",
                    f"{total_matches:,} files",
                    "",
                ]
            )
            group_item.setData(
                0,
                _SINGLE_LOCATION_GROUP_ROLE,
                not group.second_files,
            )
            _set_item_tooltips(group_item)
            self._result_tree.addTopLevelItem(group_item)
            for file_record in group.first_files:
                group_item.addChild(_file_result_item("Location 1", file_record))
            for file_record in group.second_files:
                group_item.addChild(_file_result_item("Location 2", file_record))
            group_item.setExpanded(True)

    def _show_result_context_menu(self, position: QPoint) -> None:
        item = self._result_tree.itemAt(position)
        if item is None or item.parent() is None:
            return

        path_text = item.data(0, _FILE_PATH_ROLE)
        if not isinstance(path_text, str):
            return

        self._result_tree.setCurrentItem(item)
        menu = QMenu(self._result_tree)
        menu.setObjectName("resultContextMenu")
        menu.setStyleSheet(context_menu_style("resultContextMenu"))
        open_action = menu.addAction("Open")
        rename_action = menu.addAction("Rename")
        menu.addSeparator()
        move_to_trash_action = menu.addAction("Move file to Trash...")

        selected_action = menu.exec(self._result_tree.viewport().mapToGlobal(position))
        if selected_action == open_action:
            self._open_result_file(Path(path_text))
        elif selected_action == rename_action:
            self._rename_result_file(Path(path_text))
        elif selected_action == move_to_trash_action:
            self._confirm_move_to_trash(Path(path_text))

    def _open_result_file(self, path: Path) -> None:
        try:
            open_file(path)
        except FileActionError as err:
            QMessageBox.critical(self, "File not opened", str(err))

    def _rename_result_file(self, path: Path) -> None:
        dialog, name_edit = self._build_rename_dialog(path)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            renamed_path = rename_file(path, name_edit.text())
        except FileActionError as err:
            QMessageBox.critical(self, "File not renamed", str(err))
            return

        if renamed_path == path:
            return

        self._update_result_path(path, renamed_path)
        self._progress_bar.setFormat("Renamed file")

    def _build_rename_dialog(self, path: Path) -> tuple[QDialog, QLineEdit]:
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename file")
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        label = QLabel("Enter a new filename, including its extension:")
        name_edit = QLineEdit(path.name)
        name_edit.setMinimumHeight(34)
        name_edit.selectAll()

        button_box = QDialogButtonBox()
        rename_button = QPushButton("Rename")
        cancel_button = QPushButton("Cancel")
        rename_button.setObjectName("renameConfirmButton")
        rename_button.setMinimumSize(90, 34)
        rename_button.setStyleSheet(primary_accent_button_style("renameConfirmButton"))
        cancel_button.setObjectName("renameCancelButton")
        cancel_button.setMinimumSize(90, 34)
        cancel_button.setStyleSheet(secondary_accent_button_style("renameCancelButton"))
        for button in (rename_button, cancel_button):
            button.setAutoDefault(False)
            button.setDefault(False)

        button_box.addButton(
            rename_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        button_box.addButton(
            cancel_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        rename_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        name_edit.returnPressed.connect(dialog.accept)

        layout.addWidget(label)
        layout.addWidget(name_edit)
        layout.addWidget(button_box)

        return dialog, name_edit

    def _confirm_move_to_trash(self, path: Path) -> None:
        message_box = self._build_trash_confirmation(path)
        message_box.exec()
        clicked_button = message_box.clickedButton()
        if (
            clicked_button is None
            or message_box.standardButton(clicked_button)
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            move_file_to_trash(path)
        except FileActionError as err:
            QMessageBox.critical(self, "File not moved", str(err))
            return

        self._remove_result_path(path)
        self._progress_bar.setFormat("Moved file to Trash")

    def _build_trash_confirmation(self, path: Path) -> QMessageBox:
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("Move file to Trash")
        message_box.setText(
            "Move this file to Trash?\n\n"
            f"{path}\n\n"
            "You can usually restore it from the operating system's Trash."
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        message_box.setEscapeButton(QMessageBox.StandardButton.No)

        yes_button = message_box.button(QMessageBox.StandardButton.Yes)
        no_button = message_box.button(QMessageBox.StandardButton.No)
        yes_button.setObjectName("trashConfirmYesButton")
        yes_button.setMinimumSize(90, 34)
        yes_button.setStyleSheet(primary_accent_button_style("trashConfirmYesButton"))
        no_button.setObjectName("trashConfirmNoButton")
        no_button.setMinimumSize(90, 34)
        no_button.setStyleSheet(secondary_accent_button_style("trashConfirmNoButton"))
        for button in (yes_button, no_button):
            button.setAutoDefault(False)
            button.setDefault(False)

        return message_box

    def _remove_result_path(self, path: Path) -> None:
        path_text = str(path)
        for group_index in range(self._result_tree.topLevelItemCount()):
            group_item = self._result_tree.topLevelItem(group_index)
            for child_index in range(group_item.childCount()):
                child_item = group_item.child(child_index)
                if child_item.data(0, _FILE_PATH_ROLE) != path_text:
                    continue

                child_item.setHidden(True)
                removed_item = group_item.takeChild(child_index)
                del removed_item
                self._update_result_group_after_removal(group_item, group_index)
                self._result_tree.clearSelection()
                self._result_tree.doItemsLayout()
                self._result_tree.viewport().update()
                return

    def _update_result_path(self, old_path: Path, new_path: Path) -> None:
        old_path_text = str(old_path)
        for group_index in range(self._result_tree.topLevelItemCount()):
            group_item = self._result_tree.topLevelItem(group_index)
            for child_index in range(group_item.childCount()):
                child_item = group_item.child(child_index)
                if child_item.data(0, _FILE_PATH_ROLE) != old_path_text:
                    continue

                child_item.setData(0, _FILE_PATH_ROLE, str(new_path))
                child_item.setText(1, str(new_path.parent))
                child_item.setText(2, new_path.name)
                _set_item_tooltips(child_item)
                self._result_tree.viewport().update()
                return

    def _update_result_group_after_removal(
        self,
        group_item: QTreeWidgetItem,
        group_index: int,
    ) -> None:
        remaining_count = group_item.childCount()
        single_location = bool(group_item.data(0, _SINGLE_LOCATION_GROUP_ROLE))
        remaining_locations = {
            group_item.child(index).text(0) for index in range(remaining_count)
        }
        group_is_valid = (
            remaining_count >= 2
            if single_location
            else remaining_locations == {"Location 1", "Location 2"}
        )
        if not group_is_valid:
            removed_group = self._result_tree.takeTopLevelItem(group_index)
            del removed_group
            return

        group_item.setText(2, f"{remaining_count:,} files")
        _set_item_tooltips(group_item)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self._first_edit,
            self._second_edit,
            self._first_browse_button,
            self._second_browse_button,
            self._first_recursive_check,
            self._second_recursive_check,
            self._single_location_check,
            self._excluded_extensions_edit,
            self._minimum_size_spin,
            self._search_button,
            self._exit_button,
        ):
            control.setEnabled(enabled)
        self._second_location_group.setEnabled(
            enabled and not self._single_location_check.isChecked()
        )

    def _update_second_location_state(self, search_first_only: bool) -> None:
        self._second_location_group.setEnabled(
            not search_first_only and self._thread is None
        )

    def _reset_search_ui(self) -> None:
        self._warnings.clear()
        self._progress_bar.setToolTip("")
        self._result_tree.clear()

    def _append_warning(self, message: str) -> None:
        self._warnings.append(message)
        self._progress_bar.setToolTip("\n".join(self._warnings))

    def _set_progress_message(self, message: str) -> None:
        self._progress_bar.setFormat(message)

    def _save_current_settings(self, show_warning: bool = True) -> None:
        settings = AppSettings(
            first_path=self._first_edit.text().strip(),
            second_path=self._second_edit.text().strip(),
            include_first_subfolders=self._first_recursive_check.isChecked(),
            include_second_subfolders=self._second_recursive_check.isChecked(),
            excluded_extensions=self._excluded_extensions_edit.text().strip(),
            search_first_location_only=self._single_location_check.isChecked(),
            minimum_size_mb=self._minimum_size_spin.value(),
        )
        try:
            save_settings(settings)
        except OSError as err:
            LOGGER.warning("Could not save settings: %s", err)
            if show_warning:
                QMessageBox.warning(
                    self,
                    "Settings not saved",
                    f"Your settings could not be saved: {err}",
                )

    def _initial_browse_path(self, current_text: str) -> str:
        if current_text.strip():
            current_path = Path(current_text).expanduser()
            if current_path.is_dir():
                return str(current_path)

        return str(Path.home())


def _file_result_item(location: str, file_record: FileRecord) -> QTreeWidgetItem:
    path = file_record.path
    item = QTreeWidgetItem(
        [location, str(path.parent), path.name, _format_file_size(file_record.size)]
    )
    item.setData(0, _FILE_PATH_ROLE, str(path))
    _set_item_tooltips(item)

    return item


def _set_item_tooltips(item: QTreeWidgetItem) -> None:
    for column in range(item.columnCount()):
        item.setToolTip(column, item.text(column))


def _format_file_size(size: int) -> str:
    if size < 1024:
        unit = "byte" if size == 1 else "bytes"
        return f"{size:,} {unit}"

    value = float(size)
    for unit in ("KiB", "MiB", "GiB", "TiB", "PiB"):
        value /= 1024
        if value < 1024 or unit == "PiB":
            return f"{value:.1f} {unit} ({size:,} bytes)"

    return f"{size:,} bytes"


def _style_secondary_button(button: QPushButton, object_name: str) -> None:
    button.setObjectName(object_name)
    button.setStyleSheet(
        secondary_accent_button_style(object_name, include_disabled_state=True)
    )
