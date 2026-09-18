"""Tests for safe actions on result files."""

from contextlib import nullcontext
import os
from pathlib import Path
import sys
from unittest.mock import Mock

from PySide6.QtCore import QFile, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
import pytest

from src.file_actions import (
    FileActionError,
    _windows_launch_environment,
    move_file_to_trash,
    open_file,
    rename_file,
)


def test_move_file_to_trash_uses_qt_for_regular_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Send a validated regular file to Qt's platform Trash operation."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    expected_trash_path = tmp_path / "Trash" / file_path.name
    received_paths: list[str] = []

    def fake_move_to_trash(path: str) -> tuple[bool, str]:
        received_paths.append(path)
        return True, str(expected_trash_path)

    monkeypatch.setattr(QFile, "moveToTrash", fake_move_to_trash)

    trash_path = move_file_to_trash(file_path)

    assert received_paths == [str(file_path)]
    assert trash_path == expected_trash_path


def test_move_file_to_trash_accepts_boolean_qt_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Support PySide builds that return only a success boolean."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    monkeypatch.setattr(QFile, "moveToTrash", lambda _path: True)

    trash_path = move_file_to_trash(file_path)

    assert trash_path is None


def test_move_file_to_trash_rejects_missing_path(tmp_path: Path) -> None:
    """Reject a result path if its file no longer exists."""

    with pytest.raises(FileActionError, match="no longer exists"):
        move_file_to_trash(tmp_path / "missing.bin")


def test_move_file_to_trash_rejects_directory(tmp_path: Path) -> None:
    """Do not allow the result action to move a directory."""

    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(FileActionError, match="not a regular file"):
        move_file_to_trash(directory)


def test_move_file_to_trash_rejects_symbolic_link(tmp_path: Path) -> None:
    """Do not allow the result action to move a symbolic link."""

    target = tmp_path / "target.bin"
    target.write_bytes(b"content")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(target)
    except OSError as err:
        pytest.skip(f"Symbolic links are not available: {err}")

    with pytest.raises(FileActionError, match="not a regular file"):
        move_file_to_trash(link)


def test_move_file_to_trash_reports_qt_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report failure when the operating system does not accept the file."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    monkeypatch.setattr(QFile, "moveToTrash", lambda _path: (False, ""))

    with pytest.raises(FileActionError, match="operating system"):
        move_file_to_trash(file_path)


def test_open_file_linux_passes_path_as_one_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Launch xdg-open without interpreting special filename characters."""

    file_path = tmp_path / "video #1;$%.mp4"
    file_path.write_bytes(b"content")
    process = Mock()
    process.startDetached.return_value = (True, 123)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(
        QStandardPaths,
        "findExecutable",
        lambda _name: "/usr/bin/xdg-open",
    )
    monkeypatch.setattr("src.file_actions.QProcess", lambda: process)

    open_file(file_path)

    process.setProgram.assert_called_once_with("/usr/bin/xdg-open")
    process.setArguments.assert_called_once_with([str(file_path)])
    process.setProcessEnvironment.assert_called_once()
    process.startDetached.assert_called_once_with()


def test_open_file_linux_sanitizes_frozen_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not expose bundled libraries or Qt plugins to xdg-open."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    process = Mock()
    process.startDetached.return_value = True
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/system/lib")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/bundle/qt/plugins")
    monkeypatch.setenv("QML2_IMPORT_PATH", "/bundle/qt/qml")
    monkeypatch.setattr(QStandardPaths, "findExecutable", lambda _name: "xdg-open")
    monkeypatch.setattr("src.file_actions.QProcess", lambda: process)

    open_file(file_path)

    environment = process.setProcessEnvironment.call_args.args[0]
    assert environment.value("LD_LIBRARY_PATH") == "/system/lib"
    assert not environment.contains("QT_PLUGIN_PATH")
    assert not environment.contains("QML2_IMPORT_PATH")


def test_open_file_linux_removes_library_path_without_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove the bundled library path when no original value was saved."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    process = Mock()
    process.startDetached.return_value = True
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setattr(QStandardPaths, "findExecutable", lambda _name: "xdg-open")
    monkeypatch.setattr("src.file_actions.QProcess", lambda: process)

    open_file(file_path)

    environment = process.setProcessEnvironment.call_args.args[0]
    assert not environment.contains("LD_LIBRARY_PATH")


def test_open_file_linux_reports_missing_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report when xdg-open is not installed."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(QStandardPaths, "findExecutable", lambda _name: "")

    with pytest.raises(FileActionError, match="could not be found"):
        open_file(file_path)


def test_open_file_linux_reports_detached_start_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report when the system opener process cannot start."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    process = Mock()
    process.startDetached.return_value = (False, 0)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(QStandardPaths, "findExecutable", lambda _name: "xdg-open")
    monkeypatch.setattr("src.file_actions.QProcess", lambda: process)

    with pytest.raises(FileActionError, match="could not be started"):
        open_file(file_path)


def test_open_file_windows_uses_file_association(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass a Windows file directly to the native association service."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    opened_files: list[tuple[str, str]] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        os,
        "startfile",
        lambda path, operation: opened_files.append((path, operation)),
        raising=False,
    )
    monkeypatch.setattr(
        "src.file_actions._windows_launch_environment",
        nullcontext,
    )

    open_file(file_path)

    assert opened_files == [(str(file_path), "open")]


def test_windows_launch_environment_restores_frozen_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove bundle paths during launch and restore them afterward."""

    bundle_root = tmp_path / "bundle"
    system_bin = tmp_path / "system-bin"
    bundle_bin = bundle_root / "bin"
    bundle_root.mkdir()
    system_bin.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root), raising=False)
    original_path = os.pathsep.join((str(bundle_bin), str(system_bin)))
    monkeypatch.setenv("PATH", original_path)
    monkeypatch.setenv("QT_PLUGIN_PATH", str(bundle_root / "plugins"))
    monkeypatch.setenv("QML2_IMPORT_PATH", str(bundle_root / "qml"))
    dll_directories: list[str | None] = []
    monkeypatch.setattr(
        "src.file_actions._set_windows_dll_directory",
        dll_directories.append,
    )

    with _windows_launch_environment():
        assert os.environ["PATH"] == str(system_bin)
        assert "QT_PLUGIN_PATH" not in os.environ
        assert "QML2_IMPORT_PATH" not in os.environ

    assert os.environ["PATH"] == original_path
    assert os.environ["QT_PLUGIN_PATH"] == str(bundle_root / "plugins")
    assert os.environ["QML2_IMPORT_PATH"] == str(bundle_root / "qml")
    assert dll_directories == [None, str(bundle_root.resolve())]


def test_open_file_fallback_reports_desktop_service_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report Qt desktop-service failure on other operating systems."""

    file_path = tmp_path / "duplicate.bin"
    file_path.write_bytes(b"content")
    received_urls: list[QUrl] = []

    def fake_open_url(url: QUrl) -> bool:
        received_urls.append(url)
        return False

    monkeypatch.setattr(sys, "platform", "other")
    monkeypatch.setattr(QDesktopServices, "openUrl", fake_open_url)

    with pytest.raises(FileActionError, match="could not open"):
        open_file(file_path)

    assert Path(received_urls[0].toLocalFile()) == file_path


def test_rename_file_changes_only_the_filename(tmp_path: Path) -> None:
    """Rename a file in place and preserve its contents."""

    file_path = tmp_path / "before.txt"
    file_path.write_bytes(b"content")

    renamed_path = rename_file(file_path, "after.log")

    assert renamed_path == tmp_path / "after.log"
    assert not file_path.exists()
    assert renamed_path.read_bytes() == b"content"


@pytest.mark.parametrize("new_name", ["", ".", "..", "folder/file", r"folder\file"])
def test_rename_file_rejects_invalid_filename(
    tmp_path: Path,
    new_name: str,
) -> None:
    """Reject names that are empty or attempt to select another folder."""

    file_path = tmp_path / "before.txt"
    file_path.write_bytes(b"content")

    with pytest.raises(FileActionError, match="without folder separators"):
        rename_file(file_path, new_name)

    assert file_path.exists()


def test_rename_file_does_not_replace_existing_file(tmp_path: Path) -> None:
    """Preserve both files when the requested filename already exists."""

    file_path = tmp_path / "before.txt"
    existing_path = tmp_path / "existing.txt"
    file_path.write_bytes(b"before")
    existing_path.write_bytes(b"existing")

    with pytest.raises(FileActionError, match="already exists"):
        rename_file(file_path, existing_path.name)

    assert file_path.read_bytes() == b"before"
    assert existing_path.read_bytes() == b"existing"
