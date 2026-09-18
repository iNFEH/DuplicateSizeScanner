"""Cross-platform file scanning and duplicate-size comparison."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
from pathlib import Path

type StatusCallback = Callable[[str], None]
type WarningCallback = Callable[[str], None]


class ScanError(RuntimeError):
    """Base error for failures during a duplicate-size scan."""


class ScanValidationError(ScanError):
    """Error raised when the selected scan locations are invalid."""


@dataclass(frozen=True, slots=True)
class ScanRequest:
    """Describe scan locations, recursion, and file filters."""

    first_root: Path
    second_root: Path | None
    include_first_subfolders: bool = True
    include_second_subfolders: bool = True
    excluded_extensions: tuple[str, ...] = ()
    minimum_size_bytes: int = 0


@dataclass(frozen=True, slots=True)
class FileRecord:
    """Describe one regular file found during a scan."""

    path: Path
    size: int


@dataclass(frozen=True, slots=True)
class DuplicateSizeGroup:
    """Store files that belong to one matching-size group."""

    size: int
    first_files: tuple[FileRecord, ...]
    second_files: tuple[FileRecord, ...]


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Store grouped duplicate-size matches and scan statistics."""

    groups: tuple[DuplicateSizeGroup, ...]
    first_file_count: int
    second_file_count: int
    warnings: tuple[str, ...]

    @property
    def first_match_count(self) -> int:
        """Return the number of matching files from the first location."""
        return sum(len(group.first_files) for group in self.groups)

    @property
    def second_match_count(self) -> int:
        """Return the number of matching files from the second location."""
        return sum(len(group.second_files) for group in self.groups)


def find_duplicate_sizes(
    request: ScanRequest,
    status_callback: StatusCallback | None = None,
    warning_callback: WarningCallback | None = None,
) -> ScanResult:
    """Find files with equal sizes across two locations or within one location.

    Paths use the native operating-system format. This supports POSIX paths on
    Linux and drive-letter or UNC paths on Windows.

    Args:
        request: Locations, recursive scan options, and file filters.
        status_callback: Optional callback for current scan status text.
        warning_callback: Optional callback for skipped-entry warnings.

    Returns:
        Duplicate-size groups sorted from largest size to smallest size.

    Raises:
        ScanValidationError: If a location is invalid or locations overlap.
        ScanError: If a selected root location cannot be scanned.
    """

    if request.minimum_size_bytes < 0:
        raise ScanValidationError("The minimum file size cannot be negative.")

    first_root, second_root = _validated_roots(request)
    excluded_extensions = _normalize_extensions(request.excluded_extensions)
    warnings: list[str] = []

    first_files = _scan_root(
        first_root,
        request.include_first_subfolders,
        "location 1",
        warnings,
        status_callback,
        warning_callback,
        excluded_extensions,
        request.minimum_size_bytes,
    )
    second_files = (
        _scan_root(
            second_root,
            request.include_second_subfolders,
            "location 2",
            warnings,
            status_callback,
            warning_callback,
            excluded_extensions,
            request.minimum_size_bytes,
        )
        if second_root is not None
        else None
    )

    if status_callback is not None:
        status_callback("Comparing file sizes...")

    groups = _build_groups(first_files, second_files)
    return ScanResult(
        groups=groups,
        first_file_count=len(first_files),
        second_file_count=len(second_files) if second_files is not None else 0,
        warnings=tuple(warnings),
    )


def parse_excluded_extensions(value: str) -> tuple[str, ...]:
    """Parse a comma-separated extension list into normalized values.

    Matching is case-insensitive. Leading dots and wildcard markers are
    optional, and compound extensions such as `.tar.gz` are supported.

    Args:
        value: Comma-separated extension text from the user.

    Returns:
        Unique normalized extensions in their original order.
    """

    return _normalize_extensions(value.split(","))


def _validated_roots(request: ScanRequest) -> tuple[Path, Path | None]:
    first_root = _resolve_root(request.first_root, "Location 1")
    if request.second_root is None:
        return first_root, None

    second_root = _resolve_root(request.second_root, "Location 2")

    if (
        first_root == second_root
        or first_root in second_root.parents
        or second_root in first_root.parents
    ):
        raise ScanValidationError(
            "The selected locations must be separate and must not overlap."
        )

    return first_root, second_root


def _resolve_root(path: Path, label: str) -> Path:
    expanded_path = path.expanduser()
    try:
        resolved_path = expanded_path.resolve(strict=True)
    except (OSError, RuntimeError) as err:
        raise ScanValidationError(f"{label} does not exist: {expanded_path}") from err

    try:
        is_directory = resolved_path.is_dir()
    except OSError as err:
        raise ScanValidationError(
            f"{label} cannot be accessed: {resolved_path}"
        ) from err

    if not is_directory:
        raise ScanValidationError(f"{label} is not a folder: {resolved_path}")

    return resolved_path


def _scan_root(
    root: Path,
    recursive: bool,
    label: str,
    warnings: list[str],
    status_callback: StatusCallback | None,
    warning_callback: WarningCallback | None,
    excluded_extensions: tuple[str, ...],
    minimum_size_bytes: int,
) -> tuple[FileRecord, ...]:
    records: list[FileRecord] = []
    pending_directories = [root]

    while pending_directories:
        directory = pending_directories.pop()
        if status_callback is not None:
            status_callback(f"Scanning {label}: {directory}")

        try:
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError as err:
            if directory == root:
                raise ScanError(f"Could not scan {label}: {err}") from err
            _report_warning(
                f"Skipped folder that could not be read: {directory} ({err})",
                warnings,
                warning_callback,
            )
            continue

        child_directories: list[Path] = []
        for entry in children:
            entry_path = Path(entry.path)
            try:
                if entry.is_symlink() or entry_path.is_junction():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        child_directories.append(entry_path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if _has_excluded_extension(entry.name, excluded_extensions):
                    continue
                size = entry.stat(follow_symlinks=False).st_size
            except OSError as err:
                _report_warning(
                    f"Skipped file-system entry: {entry_path} ({err})",
                    warnings,
                    warning_callback,
                )
                continue

            if size == 0 or size < minimum_size_bytes:
                continue
            records.append(FileRecord(path=entry_path, size=size))

        pending_directories.extend(reversed(child_directories))

    return tuple(sorted(records, key=lambda record: str(record.path).casefold()))


def _normalize_extensions(extensions: Iterable[str]) -> tuple[str, ...]:
    normalized: dict[str, None] = {}
    for extension in extensions:
        extension = extension.strip().casefold().lstrip("*")
        if not extension or extension == ".":
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        normalized[extension] = None
    return tuple(normalized)


def _has_excluded_extension(
    file_name: str,
    excluded_extensions: tuple[str, ...],
) -> bool:
    normalized_name = file_name.casefold()
    return any(normalized_name.endswith(extension) for extension in excluded_extensions)


def _report_warning(
    message: str,
    warnings: list[str],
    warning_callback: WarningCallback | None,
) -> None:
    warnings.append(message)
    if warning_callback is not None:
        warning_callback(message)


def _build_groups(
    first_files: tuple[FileRecord, ...],
    second_files: tuple[FileRecord, ...] | None,
) -> tuple[DuplicateSizeGroup, ...]:
    first_by_size: defaultdict[int, list[FileRecord]] = defaultdict(list)
    second_by_size: defaultdict[int, list[FileRecord]] = defaultdict(list)

    for file_record in first_files:
        first_by_size[file_record.size].append(file_record)
    if second_files is not None:
        for file_record in second_files:
            second_by_size[file_record.size].append(file_record)

    matching_sizes = (
        (size for size, files in first_by_size.items() if len(files) > 1)
        if second_files is None
        else first_by_size.keys() & second_by_size.keys()
    )
    return tuple(
        DuplicateSizeGroup(
            size=size,
            first_files=tuple(first_by_size[size]),
            second_files=tuple(second_by_size[size]),
        )
        for size in sorted(matching_sizes, reverse=True)
    )
