"""Tests for duplicate-size file scanning."""

from pathlib import Path

import pytest

from src.scanner import (
    ScanRequest,
    ScanValidationError,
    find_duplicate_sizes,
    parse_excluded_extensions,
)


def test_parse_excluded_extensions_normalizes_flexible_input() -> None:
    """Normalize dots, wildcards, case, duplicates, and empty entries."""

    result = parse_excluded_extensions(" TXT, .txt, *.Tar.Gz, ., , log ")

    assert result == (".txt", ".tar.gz", ".log")


def test_find_duplicate_sizes_returns_cross_location_matches(tmp_path: Path) -> None:
    """Only return sizes that are present in both selected locations."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "match-one.txt").write_bytes(b"abc")
    (first / "first-only.txt").write_bytes(b"12345")
    (second / "match-two.txt").write_bytes(b"xyz")
    (second / "second-only.txt").write_bytes(b"123456789")

    result = find_duplicate_sizes(ScanRequest(first, second))

    assert [group.size for group in result.groups] == [3]
    assert [record.path.name for record in result.groups[0].first_files] == [
        "match-one.txt"
    ]
    assert [record.path.name for record in result.groups[0].second_files] == [
        "match-two.txt"
    ]
    assert result.first_file_count == 2
    assert result.second_file_count == 2


def test_groups_files_sorts_sizes_and_ignores_empty_files(tmp_path: Path) -> None:
    """Group matches by descending size without counting zero-size files."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "empty-a").write_bytes(b"")
    (first / "empty-b").write_bytes(b"")
    (first / "large-a").write_bytes(b"1234")
    (first / "large-b").write_bytes(b"5678")
    (first / "small").write_bytes(b"12")
    (second / "empty-c").write_bytes(b"")
    (second / "large").write_bytes(b"abcd")
    (second / "small").write_bytes(b"ab")

    result = find_duplicate_sizes(ScanRequest(first, second))

    assert [group.size for group in result.groups] == [4, 2]
    assert len(result.groups[0].first_files) == 2
    assert len(result.groups[0].second_files) == 1
    assert result.first_file_count == 3
    assert result.second_file_count == 2
    assert result.first_match_count == 3
    assert result.second_match_count == 2


def test_recursion_is_configured_independently_for_each_location(
    tmp_path: Path,
) -> None:
    """Apply each location's subfolder option only to that location."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first_nested = first / "nested"
    second_nested = second / "nested"
    first_nested.mkdir(parents=True)
    second_nested.mkdir(parents=True)
    (first_nested / "first.bin").write_bytes(b"1234")
    (second / "second.bin").write_bytes(b"abcd")
    (second_nested / "unused.bin").write_bytes(b"123456")

    without_first_recursion = find_duplicate_sizes(
        ScanRequest(first, second, include_first_subfolders=False)
    )
    with_first_recursion = find_duplicate_sizes(
        ScanRequest(
            first,
            second,
            include_first_subfolders=True,
            include_second_subfolders=False,
        )
    )

    assert without_first_recursion.groups == ()
    assert [group.size for group in with_first_recursion.groups] == [4]
    assert with_first_recursion.second_file_count == 1


def test_excluded_extensions_filter_both_locations(tmp_path: Path) -> None:
    """Exclude simple and compound extensions from both scan locations."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "keep.dat").write_bytes(b"abcd")
    (first / "ignored.TXT").write_bytes(b"same")
    (first / "archive.TAR.GZ").write_bytes(b"123456")
    (second / "keep.bin").write_bytes(b"wxyz")
    (second / "ignored.txt").write_bytes(b"also")
    (second / "archive.tar.gz").write_bytes(b"abcdef")

    result = find_duplicate_sizes(
        ScanRequest(
            first,
            second,
            excluded_extensions=("TXT", "*.tar.gz"),
        )
    )

    assert result.first_file_count == 1
    assert result.second_file_count == 1
    assert [group.size for group in result.groups] == [4]
    assert result.groups[0].first_files[0].path.name == "keep.dat"
    assert result.groups[0].second_files[0].path.name == "keep.bin"


def test_single_location_groups_repeated_sizes(tmp_path: Path) -> None:
    """Find repeated non-zero sizes within the first location only."""

    first = tmp_path / "first"
    first.mkdir()
    (first / "match-a.bin").write_bytes(b"abc")
    (first / "match-b.bin").write_bytes(b"xyz")
    (first / "unique.bin").write_bytes(b"12")
    (first / "empty-a").write_bytes(b"")
    (first / "empty-b").write_bytes(b"")

    result = find_duplicate_sizes(ScanRequest(first, None))

    assert [group.size for group in result.groups] == [3]
    assert [record.path.name for record in result.groups[0].first_files] == [
        "match-a.bin",
        "match-b.bin",
    ]
    assert result.groups[0].second_files == ()
    assert result.first_file_count == 3
    assert result.second_file_count == 0


def test_single_location_respects_recursion_and_exclusions(tmp_path: Path) -> None:
    """Apply Location 1 recursion and exclusions in single-location mode."""

    first = tmp_path / "first"
    nested = first / "nested"
    nested.mkdir(parents=True)
    (nested / "match-a.dat").write_bytes(b"abc")
    (nested / "match-b.bin").write_bytes(b"xyz")
    (nested / "ignored-a.TXT").write_bytes(b"1234")
    (nested / "ignored-b.txt").write_bytes(b"5678")

    without_recursion = find_duplicate_sizes(
        ScanRequest(first, None, include_first_subfolders=False)
    )
    with_recursion = find_duplicate_sizes(
        ScanRequest(first, None, excluded_extensions=("txt",))
    )

    assert without_recursion.groups == ()
    assert [group.size for group in with_recursion.groups] == [3]
    assert with_recursion.first_file_count == 2


def test_minimum_size_filters_below_but_includes_boundary(tmp_path: Path) -> None:
    """Apply an inclusive byte threshold to both scan locations."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    below_minimum = 999_999
    minimum_size = 1_000_000
    (first / "below.bin").write_bytes(b"a" * below_minimum)
    (second / "below.bin").write_bytes(b"b" * below_minimum)
    (first / "boundary.bin").write_bytes(b"a" * minimum_size)
    (second / "boundary.bin").write_bytes(b"b" * minimum_size)

    result = find_duplicate_sizes(
        ScanRequest(first, second, minimum_size_bytes=minimum_size)
    )

    assert [group.size for group in result.groups] == [minimum_size]
    assert result.first_file_count == 1
    assert result.second_file_count == 1


def test_minimum_size_applies_to_single_location_mode(tmp_path: Path) -> None:
    """Apply the same minimum threshold to Location 1-only searches."""

    first = tmp_path / "first"
    first.mkdir()
    (first / "small-a.bin").write_bytes(b"a")
    (first / "small-b.bin").write_bytes(b"b")
    (first / "large-a.bin").write_bytes(b"a" * 1_000_000)
    (first / "large-b.bin").write_bytes(b"b" * 1_000_000)

    result = find_duplicate_sizes(
        ScanRequest(first, None, minimum_size_bytes=1_000_000)
    )

    assert [group.size for group in result.groups] == [1_000_000]
    assert result.first_file_count == 2


def test_rejects_negative_minimum_size(tmp_path: Path) -> None:
    """Reject a negative backend threshold before scanning."""

    with pytest.raises(ScanValidationError, match="cannot be negative"):
        find_duplicate_sizes(ScanRequest(tmp_path, None, minimum_size_bytes=-1))


@pytest.mark.parametrize("nested_side", ["first", "second"])
def test_rejects_identical_or_nested_locations(
    tmp_path: Path,
    nested_side: str,
) -> None:
    """Reject a location that is equal to or inside the other location."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    nested = first / "nested"
    nested.mkdir(parents=True)
    second.mkdir()
    request = (
        ScanRequest(first, nested)
        if nested_side == "first"
        else ScanRequest(nested, first)
    )

    with pytest.raises(ScanValidationError, match="must not overlap"):
        find_duplicate_sizes(request)

    with pytest.raises(ScanValidationError, match="must not overlap"):
        find_duplicate_sizes(ScanRequest(second, second))


def test_rejects_missing_location(tmp_path: Path) -> None:
    """Report a missing selected location as a validation error."""

    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(ScanValidationError, match="Location 2 does not exist"):
        find_duplicate_sizes(ScanRequest(existing, tmp_path / "missing"))


def test_skips_symbolic_links(tmp_path: Path) -> None:
    """Do not count a symbolic link as another file."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    target = first / "target.bin"
    target.write_bytes(b"data")
    link = first / "link.bin"
    try:
        link.symlink_to(target)
    except OSError as err:
        pytest.skip(f"Symbolic links are not available: {err}")
    (second / "match.bin").write_bytes(b"same")

    result = find_duplicate_sizes(ScanRequest(first, second))

    assert result.first_file_count == 1
    assert [record.path.name for record in result.groups[0].first_files] == [
        "target.bin"
    ]


def test_reports_scan_status(tmp_path: Path) -> None:
    """Report native paths while scanning and a final comparison status."""

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    statuses: list[str] = []

    find_duplicate_sizes(ScanRequest(first, second), status_callback=statuses.append)

    assert str(first.resolve()) in statuses[0]
    assert str(second.resolve()) in statuses[1]
    assert statuses[-1] == "Comparing file sizes..."
