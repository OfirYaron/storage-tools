"""Tests for large files finder."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from storage_tools.large_files import (
    GroupBy,
    LargeFileFinder,
    LargeFileSearchOptions,
    TopNTracker,
    format_grouped_output,
    format_large_files_output,
)
from storage_tools.utils import FileInfo


class TestTopNTracker:
    """Tests for TopNTracker class."""

    def test_tracks_top_n(self) -> None:
        """Test that tracker keeps only top N items."""
        tracker = TopNTracker(3)

        # Add 5 files
        for i in range(5):
            file_info = FileInfo(
                path=Path(f"/tmp/file{i}.txt"),
                size=i * 100,
                modified_time=1234567890.0,
            )
            tracker.add(file_info)

        # Should only keep top 3
        results = tracker.get_top_n()
        assert len(results) == 3
        # Largest first
        sizes = [f.size for f in results]
        assert sizes == sorted(sizes, reverse=True)
        assert results[0].size == 400
        assert 200 in sizes
        assert 300 in sizes

    def test_handles_fewer_than_n(self) -> None:
        """Test tracker with fewer items than N."""
        tracker = TopNTracker(10)

        # Add only 3 files
        for i in range(3):
            file_info = FileInfo(
                path=Path(f"/tmp/file{i}.txt"),
                size=i * 100,
                modified_time=1234567890.0,
            )
            tracker.add(file_info)

        results = tracker.get_top_n()
        assert len(results) == 3

    def test_invalid_n(self) -> None:
        """Test that invalid N raises error."""
        with pytest.raises(ValueError, match="n must be positive"):
            TopNTracker(0)

        with pytest.raises(ValueError, match="n must be positive"):
            TopNTracker(-1)

    def test_stable_sorting(self) -> None:
        """Test that items with same size maintain order."""
        tracker = TopNTracker(5)

        # Add files with same size
        for i in range(5):
            file_info = FileInfo(
                path=Path(f"/tmp/file{i}.txt"),
                size=100,  # Same size
                modified_time=1234567890.0,
            )
            tracker.add(file_info)

        results = tracker.get_top_n()
        assert len(results) == 5

        # Check that order is maintained (first added, first in results)
        for i, result in enumerate(results):
            assert result.path.name == f"file{i}.txt"


class TestLargeFileSearchOptions:
    """Tests for LargeFileSearchOptions."""

    def test_default_options(self) -> None:
        """Test default options."""
        options = LargeFileSearchOptions()
        assert options.top_n == 20
        assert options.min_size == 0
        assert options.extensions is None
        assert options.modified_since is None
        assert not options.follow_symlinks
        assert not options.include_hidden
        assert options.exclude_patterns is None
        assert options.group_by == GroupBy.NONE
        assert options.max_depth is None

    def test_custom_options(self) -> None:
        """Test custom options."""
        modified_date = datetime.now()
        options = LargeFileSearchOptions(
            top_n=10,
            min_size=1024,
            extensions=["txt", "pdf"],
            modified_since=modified_date,
            follow_symlinks=True,
            include_hidden=True,
            exclude_patterns=["*.tmp"],
            group_by=GroupBy.EXTENSION,
            max_depth=5,
        )
        assert options.top_n == 10
        assert options.min_size == 1024
        assert options.extensions == ["txt", "pdf"]
        assert options.modified_since == modified_date
        assert options.follow_symlinks
        assert options.include_hidden
        assert options.exclude_patterns == ["*.tmp"]
        assert options.group_by == GroupBy.EXTENSION
        assert options.max_depth == 5


class TestLargeFileFinder:
    """Tests for LargeFileFinder class."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create test files with different sizes
            (tmp_path / "small.txt").write_text("a" * 100)
            (tmp_path / "medium.txt").write_text("b" * 1000)
            (tmp_path / "large.txt").write_text("c" * 10000)
            (tmp_path / "huge.pdf").write_text("d" * 100000)

            # Create subdirectory
            subdir = tmp_path / "subdir"
            subdir.mkdir()
            (subdir / "sub_large.txt").write_text("e" * 50000)

            # Create hidden file
            (tmp_path / ".hidden.txt").write_text("f" * 5000)

            yield tmp_path

    def test_find_basic(self, temp_dir: Path) -> None:
        """Test basic file finding."""
        finder = LargeFileFinder(LargeFileSearchOptions(top_n=10))
        results = finder.find(temp_dir)

        # Should find all non-hidden files
        assert len(results) == 5
        # Should be sorted by size (largest first)
        assert results[0].size > results[1].size > results[2].size

    def test_find_with_top_n(self, temp_dir: Path) -> None:
        """Test finding with top N limit."""
        finder = LargeFileFinder(LargeFileSearchOptions(top_n=2))
        results = finder.find(temp_dir)

        assert len(results) == 2
        # Should get the two largest files - verify they're the biggest
        assert results[0].size >= results[1].size
        file_names = {r.path.name for r in results}
        # huge.pdf (100000 bytes) and sub_large.txt (50000 bytes) should be top 2
        assert "huge.pdf" in file_names
        assert "sub_large.txt" in file_names

    def test_find_with_min_size(self, temp_dir: Path) -> None:
        """Test finding with minimum size filter."""
        finder = LargeFileFinder(LargeFileSearchOptions(min_size=5000))
        results = finder.find(temp_dir)

        # Should only find files >= 5000 bytes
        assert all(f.size >= 5000 for f in results)
        assert len(results) == 3  # huge.pdf, sub_large.txt, large.txt

    def test_find_with_extension_filter(self, temp_dir: Path) -> None:
        """Test finding with extension filter."""
        finder = LargeFileFinder(LargeFileSearchOptions(extensions=["txt"]))
        results = finder.find(temp_dir)

        # Should only find .txt files
        assert all(f.extension == "txt" for f in results)
        assert len(results) == 4  # All txt files except hidden

    def test_find_with_include_hidden(self, temp_dir: Path) -> None:
        """Test finding with hidden files included."""
        finder = LargeFileFinder(LargeFileSearchOptions(include_hidden=True))
        results = finder.find(temp_dir)

        # Should find all files including hidden
        assert len(results) == 6
        assert any(f.path.name == ".hidden.txt" for f in results)

    def test_find_with_modified_since(self, temp_dir: Path) -> None:
        """Test finding with modification date filter."""
        # All test files were just created, so this should find all
        recent = datetime.now() - timedelta(hours=1)
        finder = LargeFileFinder(LargeFileSearchOptions(modified_since=recent))
        results = finder.find(temp_dir)
        assert len(results) == 5

        # Future date should find nothing
        future = datetime.now() + timedelta(days=1)
        finder = LargeFileFinder(LargeFileSearchOptions(modified_since=future))
        results = finder.find(temp_dir)
        assert len(results) == 0

    def test_find_grouped_by_extension(self, temp_dir: Path) -> None:
        """Test finding grouped by extension."""
        finder = LargeFileFinder(LargeFileSearchOptions(group_by=GroupBy.EXTENSION))
        results = finder.find_grouped(temp_dir)

        assert "txt" in results
        assert "pdf" in results
        assert len(results["txt"]) == 4  # 4 txt files
        assert len(results["pdf"]) == 1  # 1 pdf file

    def test_find_grouped_by_directory(self, temp_dir: Path) -> None:
        """Test finding grouped by directory."""
        finder = LargeFileFinder(LargeFileSearchOptions(group_by=GroupBy.DIRECTORY))
        results = finder.find_grouped(temp_dir)

        # Should have groups for main dir and subdir
        assert len(results) == 2
        assert any(str(temp_dir) in key for key in results.keys())
        assert any("subdir" in key for key in results.keys())

    def test_find_nonexistent_path(self) -> None:
        """Test finding in nonexistent path raises error."""
        finder = LargeFileFinder()
        with pytest.raises(FileNotFoundError):
            finder.find("/nonexistent/path/xyz123")

    def test_find_file_not_directory(self, temp_dir: Path) -> None:
        """Test finding on a file (not directory) raises error."""
        file_path = temp_dir / "small.txt"
        finder = LargeFileFinder()
        with pytest.raises(NotADirectoryError):
            finder.find(file_path)

    def test_find_with_max_depth(self, temp_dir: Path) -> None:
        """Test finding with depth limit."""
        # Depth 0 should only find files in root
        finder = LargeFileFinder(LargeFileSearchOptions(max_depth=0))
        results = finder.find(temp_dir)

        # Should not include files from subdir
        assert all("subdir" not in str(f.path) for f in results)
        assert len(results) == 4  # Files in root only


class TestFormatOutput:
    """Tests for output formatting functions."""

    def test_format_empty_list(self) -> None:
        """Test formatting empty file list."""
        output = format_large_files_output([])
        assert "No files found" in output

    def test_format_files_basic(self) -> None:
        """Test basic file list formatting."""
        files = [
            FileInfo(
                path=Path("/tmp/file1.txt"),
                size=1024,
                modified_time=1234567890.0,
            ),
            FileInfo(
                path=Path("/tmp/file2.txt"),
                size=2048,
                modified_time=1234567890.0,
            ),
        ]
        output = format_large_files_output(files)

        assert "file1.txt" in output
        assert "file2.txt" in output
        assert "KB" in output

    def test_format_files_relative_paths(self) -> None:
        """Test formatting with relative paths."""
        files = [
            FileInfo(
                path=Path("/tmp/test/file1.txt"),
                size=1024,
                modified_time=1234567890.0,
            ),
        ]
        output = format_large_files_output(files, relative_to=Path("/tmp/test"))

        # Should show relative path
        assert "file1.txt" in output
        assert "/tmp/test/file1.txt" not in output

    def test_format_grouped_empty(self) -> None:
        """Test formatting empty grouped results."""
        output = format_grouped_output({})
        assert "No files found" in output

    def test_format_grouped_basic(self) -> None:
        """Test basic grouped formatting."""
        grouped = {
            "txt": [
                FileInfo(
                    path=Path("/tmp/file1.txt"),
                    size=1024,
                    modified_time=1234567890.0,
                )
            ],
            "pdf": [
                FileInfo(
                    path=Path("/tmp/file2.pdf"),
                    size=2048,
                    modified_time=1234567890.0,
                )
            ],
        }
        output = format_grouped_output(grouped)

        assert "txt" in output
        assert "pdf" in output
        assert "file1.txt" in output
        assert "file2.pdf" in output
