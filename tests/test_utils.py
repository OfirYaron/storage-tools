"""Tests for utility functions."""

import re
from pathlib import Path

import pytest

from storage_tools.utils import (
    FileInfo,
    format_size,
    normalize_path,
    parse_size,
    should_exclude_path,
)


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_size(1024) == "1.00 KB"
        assert format_size(1536) == "1.50 KB"
        assert format_size(2048) == "2.00 KB"

    def test_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_size(1024**2) == "1.00 MB"
        assert format_size(int(1.5 * 1024**2)) == "1.50 MB"

    def test_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_size(1024**3) == "1.00 GB"
        assert format_size(int(2.5 * 1024**3)) == "2.50 GB"

    def test_terabytes(self) -> None:
        """Test formatting terabytes."""
        assert format_size(1024**4) == "1.00 TB"

    def test_decimal_places(self) -> None:
        """Test custom decimal places."""
        assert format_size(1536, 1) == "1.5 KB"
        assert format_size(1536, 3) == "1.500 KB"

    def test_negative_size(self) -> None:
        """Test that negative sizes raise error."""
        with pytest.raises(ValueError, match="Size cannot be negative"):
            format_size(-100)


class TestParseSize:
    """Tests for parse_size function."""

    def test_bytes_only(self) -> None:
        """Test parsing plain bytes."""
        assert parse_size("100") == 100
        assert parse_size("0") == 0

    def test_kilobytes(self) -> None:
        """Test parsing kilobytes."""
        assert parse_size("1KB") == 1024
        assert parse_size("1 KB") == 1024
        assert parse_size("1kb") == 1024
        assert parse_size("2KB") == 2048

    def test_megabytes(self) -> None:
        """Test parsing megabytes."""
        assert parse_size("1MB") == 1024**2
        assert parse_size("1.5MB") == int(1.5 * 1024**2)

    def test_gigabytes(self) -> None:
        """Test parsing gigabytes."""
        assert parse_size("1GB") == 1024**3
        assert parse_size("2.5GB") == int(2.5 * 1024**3)

    def test_terabytes(self) -> None:
        """Test parsing terabytes."""
        assert parse_size("1TB") == 1024**4

    def test_invalid_format(self) -> None:
        """Test invalid format raises error."""
        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("abc")

        with pytest.raises(ValueError, match="Invalid number"):
            parse_size("1.2.3MB")

    def test_invalid_unit(self) -> None:
        """Test invalid unit raises error."""
        with pytest.raises(ValueError, match="Unknown unit"):
            parse_size("100XB")

    def test_invalid_number(self) -> None:
        """Test invalid number raises error."""
        with pytest.raises(ValueError, match="Invalid size format"):
            parse_size("abcMB")


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_absolute_path(self) -> None:
        """Test normalizing absolute path."""
        path = Path("/tmp/test")
        result = normalize_path(path)
        assert result.is_absolute()

    def test_relative_path(self) -> None:
        """Test normalizing relative path."""
        result = normalize_path(".")
        assert result.is_absolute()

    def test_home_expansion(self) -> None:
        """Test expanding ~ in path."""
        result = normalize_path("~")
        assert result.is_absolute()
        assert "~" not in str(result)

    def test_string_input(self) -> None:
        """Test string input."""
        result = normalize_path("/tmp/test")
        assert isinstance(result, Path)
        assert result.is_absolute()


class TestShouldExcludePath:
    """Tests for should_exclude_path function."""

    def test_hidden_file_excluded_by_default(self) -> None:
        """Test that hidden files are excluded by default."""
        assert should_exclude_path(Path("/home/user/.hidden"))
        assert should_exclude_path(Path("/home/.hidden/file.txt"))

    def test_hidden_file_included_when_enabled(self) -> None:
        """Test that hidden files can be included."""
        assert not should_exclude_path(Path("/home/user/.hidden"), include_hidden=True)

    def test_regular_file_not_excluded(self) -> None:
        """Test that regular files are not excluded."""
        assert not should_exclude_path(Path("/home/user/file.txt"))

    def test_glob_pattern_exclusion(self) -> None:
        """Test glob pattern matching."""
        patterns = ["*.tmp", "*.log"]
        assert should_exclude_path(Path("/tmp/test.tmp"), patterns)
        assert should_exclude_path(Path("/tmp/test.log"), patterns)
        assert not should_exclude_path(Path("/tmp/test.txt"), patterns)

    def test_regex_pattern_exclusion(self) -> None:
        """Test regex pattern matching."""
        patterns = [re.compile(r".*\.tmp$"), re.compile(r".*\.log$")]
        assert should_exclude_path(Path("/tmp/test.tmp"), patterns)
        assert should_exclude_path(Path("/tmp/test.log"), patterns)
        assert not should_exclude_path(Path("/tmp/test.txt"), patterns)

    def test_path_pattern_exclusion(self) -> None:
        """Test path-based pattern matching."""
        patterns = ["*/node_modules/*", "*/.git/*"]
        assert should_exclude_path(Path("/project/node_modules/pkg"), patterns)
        assert should_exclude_path(Path("/project/.git/config"), patterns)


class TestFileInfo:
    """Tests for FileInfo class."""

    def test_creation(self) -> None:
        """Test creating FileInfo."""
        info = FileInfo(
            path=Path("/tmp/test.txt"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info.path == Path("/tmp/test.txt")
        assert info.size == 1024
        assert info.modified_time == 1234567890.0
        assert not info.is_symlink

    def test_size_formatted(self) -> None:
        """Test size_formatted property."""
        info = FileInfo(
            path=Path("/tmp/test.txt"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info.size_formatted == "1.00 KB"

    def test_name_property(self) -> None:
        """Test name property."""
        info = FileInfo(
            path=Path("/tmp/test.txt"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info.name == "test.txt"

    def test_extension_property(self) -> None:
        """Test extension property."""
        info = FileInfo(
            path=Path("/tmp/test.txt"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info.extension == "txt"

        # Test no extension
        info2 = FileInfo(
            path=Path("/tmp/test"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info2.extension == ""

        # Test multiple dots
        info3 = FileInfo(
            path=Path("/tmp/test.tar.gz"),
            size=1024,
            modified_time=1234567890.0,
        )
        assert info3.extension == "gz"

    def test_comparison(self) -> None:
        """Test file comparison by size."""
        info1 = FileInfo(
            path=Path("/tmp/small.txt"),
            size=100,
            modified_time=1234567890.0,
        )
        info2 = FileInfo(
            path=Path("/tmp/large.txt"),
            size=200,
            modified_time=1234567890.0,
        )
        assert info1 < info2
        assert not info2 < info1
