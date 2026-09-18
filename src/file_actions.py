"""Safe cross-platform actions for files shown in scan results."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys
from threading import Lock

from PySide6.QtCore import (
    QFile,
    QProcess,
    QProcessEnvironment,
    QStandardPaths,
    QUrl,
)
from PySide6.QtGui import QDesktopServices

_WINDOWS_LAUNCH_LOCK = Lock()


class FileActionError(RuntimeError):
    """Error raised when an action on a result file cannot be completed."""


def move_file_to_trash(path: Path) -> Path | None:
    """Move one regular file to the operating system's Trash location.

    Args:
        path: File to move to Linux Trash or the Windows Recycle Bin.

    Returns:
        The resulting Trash path when Qt provides one, otherwise `None`.

    Raises:
        FileActionError: If the path is missing, is not a regular file or
            cannot be moved to Trash.
    """

    _validate_regular_file(path)

    try:
        trash_result = QFile.moveToTrash(str(path))
    except (OSError, RuntimeError) as err:
        raise FileActionError(f"The file could not be moved to Trash: {err}") from err

    if isinstance(trash_result, tuple):
        moved, trash_path = trash_result
    else:
        moved = trash_result
        trash_path = ""

    if not moved:
        raise FileActionError(
            f"The operating system could not move the file to Trash: {path}"
        )

    return Path(trash_path) if trash_path else None


def open_file(path: Path) -> None:
    """Open one file with the operating system's default application.

    Args:
        path: File to open.

    Raises:
        FileActionError: If the path is invalid or no application accepts it.
    """

    _validate_regular_file(path)
    match sys.platform:
        case "linux":
            _open_file_linux(path)
        case "win32":
            _open_file_windows(path)
        case _:
            _open_file_with_qt(path)


def _open_file_linux(path: Path) -> None:
    launcher = QStandardPaths.findExecutable("xdg-open")
    if not launcher:
        raise FileActionError("The system file opener `xdg-open` could not be found.")

    process = QProcess()
    process.setProgram(launcher)
    process.setArguments([str(path)])
    process.setProcessEnvironment(_external_process_environment())
    try:
        start_result = process.startDetached()
    except (OSError, RuntimeError) as err:
        raise FileActionError(f"The selected file could not be opened: {err}") from err

    started = start_result[0] if isinstance(start_result, tuple) else start_result
    if not started:
        raise FileActionError("The system file opener could not be started.")


def _external_process_environment() -> QProcessEnvironment:
    environment = QProcessEnvironment.systemEnvironment()
    if not getattr(sys, "frozen", False):
        return environment

    if environment.contains("LD_LIBRARY_PATH_ORIG"):
        environment.insert(
            "LD_LIBRARY_PATH",
            environment.value("LD_LIBRARY_PATH_ORIG"),
        )
    else:
        environment.remove("LD_LIBRARY_PATH")

    environment.remove("QT_PLUGIN_PATH")
    environment.remove("QML2_IMPORT_PATH")
    return environment


def _open_file_windows(path: Path) -> None:
    start_file = getattr(os, "startfile", None)
    if start_file is None:
        raise FileActionError("The Windows file association service is unavailable.")

    try:
        with _windows_launch_environment():
            start_file(str(path), "open")
    except OSError as err:
        raise FileActionError(f"The selected file could not be opened: {err}") from err


@contextmanager
def _windows_launch_environment() -> Iterator[None]:
    bundle_root_text = getattr(sys, "_MEIPASS", None)
    if not getattr(sys, "frozen", False) or bundle_root_text is None:
        yield
        return

    bundle_root = Path(bundle_root_text).resolve()
    variable_names = ("PATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH")
    original_values = {name: os.environ.get(name) for name in variable_names}

    with _WINDOWS_LAUNCH_LOCK:
        _set_windows_dll_directory(None)
        os.environ.pop("QT_PLUGIN_PATH", None)
        os.environ.pop("QML2_IMPORT_PATH", None)
        if path_value := os.environ.get("PATH"):
            clean_paths = (
                entry
                for entry in path_value.split(os.pathsep)
                if not _is_path_within_bundle(entry, bundle_root)
            )
            os.environ["PATH"] = os.pathsep.join(clean_paths)

        try:
            yield  # yep!
        finally:
            for name, value in original_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            _set_windows_dll_directory(str(bundle_root))


def _is_path_within_bundle(value: str, bundle_root: Path) -> bool:
    if not value:
        return False
    try:
        return Path(value).resolve().is_relative_to(bundle_root)
    except OSError, RuntimeError:
        return False


def _set_windows_dll_directory(path: str | None) -> None:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_dll_directory = kernel32.SetDllDirectoryW
    set_dll_directory.argtypes = [ctypes.c_wchar_p]
    set_dll_directory.restype = ctypes.c_bool
    if not set_dll_directory(path):
        raise ctypes.WinError(ctypes.get_last_error())


def _open_file_with_qt(path: Path) -> None:
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        raise FileActionError(
            f"The operating system could not open the selected file: {path}"
        )


def rename_file(path: Path, new_name: str) -> Path:
    """Rename one file without changing its location.

    Args:
        path: File to rename.
        new_name: New filename, including its extension.

    Returns:
        The renamed file path.

    Raises:
        FileActionError: If the filename is invalid, already exists or the
            operating system cannot rename the file.
    """

    _validate_regular_file(path)
    if (
        not new_name
        or new_name in {".", ".."}
        or any(separator in new_name for separator in ("/", "\\", "\0"))
    ):
        raise FileActionError("Enter a filename without folder separators.")

    if new_name == path.name:
        return path

    destination = path.with_name(new_name)
    if destination.exists() or destination.is_symlink():
        raise FileActionError(f"A file with that name already exists: {destination}")

    try:
        return path.rename(destination)
    except (OSError, ValueError) as err:
        raise FileActionError(f"The file could not be renamed: {err}") from err


def _validate_regular_file(path: Path) -> None:
    try:
        file_status = path.lstat()
    except FileNotFoundError as err:
        raise FileActionError(f"The file no longer exists: {path}") from err
    except OSError as err:
        raise FileActionError(
            f"The file could not be accessed: {path} ({err})"
        ) from err

    if not stat.S_ISREG(file_status.st_mode):
        raise FileActionError(f"The selected path is not a regular file: {path}")
