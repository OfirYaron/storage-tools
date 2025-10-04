"""Tests for the folder analyzer module."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from storage_tools.analyzer import (
    FolderAnalysisOptions,
    FolderAnalyzer,
    StorageStats,
    format_analysis_output,
    format_directory_analysis,
)


class TestStorageStats:
    """Tests for StorageStats class."""

    def test_creation(self) -> None:
        """Test creating StorageStats."""
        stats = StorageStats()
        assert stats.total_size == 0
        assert stats.file_count == 0
        assert stats.directory_count == 0
        assert stats.extension_stats == {}
        assert stats.largest_files == []
        assert stats.deepest_path is None
        assert stats.deepest_level == 0

    def test_total_size_formatted(self) -> None:
        """Test formatted total size."""
        stats = StorageStats(total_size=1024 * 1024)
        assert stats.total_size_formatted == "1.00 MB"

    def test_average_file_size(self) -> None:
        """Test average file size calculation."""
        stats = StorageStats(total_size=1000, file_count=10)
        assert stats.average_file_size == 100

        # Test with no files
        stats2 = StorageStats(total_size=1000, file_count=0)
        assert stats2.average_file_size == 0

    def test_average_file_size_formatted(self) -> None:
        """Test formatted average file size."""
        stats = StorageStats(total_size=2048, file_count=2)
        assert stats.average_file_size_formatted == "1.00 KB"


class TestFolderAnalysisOptions:
    """Tests for FolderAnalysisOptions."""

    def test_default_options(self) -> None:
        """Test default options."""
        options = FolderAnalysisOptions()
        assert not options.follow_symlinks
        assert not options.include_hidden
        assert options.exclude_patterns is None
        assert options.max_depth is None
        assert options.track_largest_n == 10
        assert options.sort_by == "size"

    def test_custom_options(self) -> None:
        """Test custom options."""
        options = FolderAnalysisOptions(
            follow_symlinks=True,
            include_hidden=True,
            exclude_patterns=["*.tmp"],
            max_depth=3,
            track_largest_n=5,
            sort_by="name",
        )
        assert options.follow_symlinks
        assert options.include_hidden
        assert options.exclude_patterns == ["*.tmp"]
        assert options.max_depth == 3
        assert options.track_largest_n == 5
        assert options.sort_by == "name"


class TestFolderAnalyzer:
    """Tests for FolderAnalyzer class."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create test files with different sizes and types
            (tmp_path / "file1.txt").write_text("a" * 100)
            (tmp_path / "file2.txt").write_text("b" * 200)
            (tmp_path / "file3.pdf").write_text("c" * 300)
            (tmp_path / "file4.py").write_text("d" * 400)

            # Create subdirectories
            subdir1 = tmp_path / "subdir1"
            subdir1.mkdir()
            (subdir1 / "sub_file1.txt").write_text("e" * 500)
            (subdir1 / "sub_file2.log").write_text("f" * 600)

            subdir2 = tmp_path / "subdir2"
            subdir2.mkdir()
            (subdir2 / "sub_file3.txt").write_text("g" * 700)

            # Create nested directory
            nested = subdir1 / "nested"
            nested.mkdir()
            (nested / "deep_file.txt").write_text("h" * 800)

            # Create hidden file
            (tmp_path / ".hidden.txt").write_text("i" * 100)

            yield tmp_path

    def test_analyze_basic(self, temp_dir: Path) -> None:
        """Test basic folder analysis."""
        analyzer = FolderAnalyzer()
        stats = analyzer.analyze(temp_dir)

        # Should find all non-hidden files
        assert stats.file_count == 8
        assert stats.directory_count == 3  # subdir1, subdir2, nested
        assert stats.total_size == 100 + 200 + 300 + 400 + 500 + 600 + 700 + 800

    def test_analyze_with_hidden(self, temp_dir: Path) -> None:
        """Test analysis including hidden files."""
        options = FolderAnalysisOptions(include_hidden=True)
        analyzer = FolderAnalyzer(options)
        stats = analyzer.analyze(temp_dir)

        # Should include hidden file
        assert stats.file_count == 9
        assert stats.total_size == 100 + 200 + 300 + 400 + 500 + 600 + 700 + 800 + 100

    def test_analyze_with_depth_limit(self, temp_dir: Path) -> None:
        """Test analysis with depth limit."""
        options = FolderAnalysisOptions(max_depth=1)
        analyzer = FolderAnalyzer(options)
        stats = analyzer.analyze(temp_dir)

        # Should not include files in nested directory (depth > 1)
        assert stats.file_count == 7  # Excludes deep_file.txt
        assert stats.directory_count == 2  # subdir1, subdir2 (not nested)

    def test_extension_stats(self, temp_dir: Path) -> None:
        """Test extension statistics."""
        analyzer = FolderAnalyzer()
        stats = analyzer.analyze(temp_dir)

        # Check extension stats
        assert "txt" in stats.extension_stats
        assert "pdf" in stats.extension_stats
        assert "py" in stats.extension_stats
        assert "log" in stats.extension_stats

        # txt files: file1.txt (100), file2.txt (200), sub_file1.txt (500),
        # sub_file3.txt (700), deep_file.txt (800)
        txt_count, txt_size = stats.extension_stats["txt"]
        assert txt_count == 5
        assert txt_size == 100 + 200 + 500 + 700 + 800

    def test_largest_files(self, temp_dir: Path) -> None:
        """Test tracking of largest files."""
        options = FolderAnalysisOptions(track_largest_n=3)
        analyzer = FolderAnalyzer(options)
        stats = analyzer.analyze(temp_dir)

        # Should track top 3 largest files
        assert len(stats.largest_files) == 3
        assert stats.largest_files[0].size == 800  # deep_file.txt
        assert stats.largest_files[1].size == 700  # sub_file3.txt
        assert stats.largest_files[2].size == 600  # sub_file2.log

    def test_deepest_path(self, temp_dir: Path) -> None:
        """Test tracking of deepest path."""
        analyzer = FolderAnalyzer()
        stats = analyzer.analyze(temp_dir)

        # deepest file should be in nested directory
        assert stats.deepest_path is not None
        assert "nested" in str(stats.deepest_path)
        assert stats.deepest_level == 3  # subdir1/nested/deep_file.txt

    def test_oldest_newest_files(self, temp_dir: Path) -> None:
        """Test tracking of oldest and newest files."""
        analyzer = FolderAnalyzer()
        stats = analyzer.analyze(temp_dir)

        # All files were just created, so oldest and newest should exist
        assert stats.oldest_file is not None
        assert stats.newest_file is not None

        # They should have recent timestamps
        now = datetime.now().timestamp()
        assert abs(stats.oldest_file.modified_time - now) < 60  # Within 1 minute
        assert abs(stats.newest_file.modified_time - now) < 60

    def test_average_file_size(self, temp_dir: Path) -> None:
        """Test average file size calculation."""
        analyzer = FolderAnalyzer()
        stats = analyzer.analyze(temp_dir)

        expected_avg = stats.total_size // stats.file_count
        assert stats.average_file_size == expected_avg

    def test_analyze_by_directory(self, temp_dir: Path) -> None:
        """Test directory-by-directory analysis."""
        analyzer = FolderAnalyzer()
        dir_stats = analyzer.analyze_by_directory(temp_dir)

        # Should have stats for root and subdirectories
        assert len(dir_stats) > 0

        # Find subdir1 stats
        subdir1 = temp_dir / "subdir1"
        subdir1_stats = dir_stats.get(subdir1)
        if subdir1_stats:
            # subdir1 has sub_file1.txt (500) and sub_file2.log (600)
            assert subdir1_stats.file_count == 2
            assert subdir1_stats.total_size == 500 + 600

    def test_analyze_nonexistent_path(self) -> None:
        """Test analyzing nonexistent path raises error."""
        analyzer = FolderAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("/nonexistent/path/xyz123")

    def test_analyze_file_not_directory(self, temp_dir: Path) -> None:
        """Test analyzing a file (not directory) raises error."""
        file_path = temp_dir / "file1.txt"
        analyzer = FolderAnalyzer()
        with pytest.raises(NotADirectoryError):
            analyzer.analyze(file_path)

    def test_analyze_empty_directory(self) -> None:
        """Test analyzing empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = FolderAnalyzer()
            stats = analyzer.analyze(tmpdir)

            assert stats.file_count == 0
            assert stats.directory_count == 0
            assert stats.total_size == 0
            assert stats.average_file_size == 0


class TestFormatOutput:
    """Tests for output formatting functions."""

    def test_format_analysis_output_basic(self) -> None:
        """Test basic analysis output formatting."""
        stats = StorageStats(
            total_size=1024 * 1024,
            file_count=100,
            directory_count=10,
        )
        output = format_analysis_output(stats)

        assert "FOLDER ANALYSIS SUMMARY" in output
        assert "1.00 MB" in output
        assert "100" in output
        assert "10" in output

    def test_format_analysis_output_with_extensions(self) -> None:
        """Test output with extension stats."""
        stats = StorageStats(
            total_size=1000,
            file_count=10,
            directory_count=2,
            extension_stats={
                "txt": (5, 500),
                "pdf": (3, 300),
                "py": (2, 200),
            },
        )
        output = format_analysis_output(stats, show_extensions=True)

        assert "FILE TYPE DISTRIBUTION" in output
        assert "txt" in output
        assert "pdf" in output
        assert "py" in output

    def test_format_analysis_output_no_extensions(self) -> None:
        """Test output without extension stats."""
        stats = StorageStats(
            total_size=1000,
            file_count=10,
            extension_stats={"txt": (5, 500)},
        )
        output = format_analysis_output(stats, show_extensions=False)

        assert "FILE TYPE DISTRIBUTION" not in output

    def test_format_directory_analysis(self) -> None:
        """Test directory analysis formatting."""
        dir_stats = {
            Path("/tmp/test"): StorageStats(
                total_size=1000,
                file_count=5,
                directory_count=2,
            ),
            Path("/tmp/test2"): StorageStats(
                total_size=2000,
                file_count=10,
                directory_count=3,
            ),
        }

        output = format_directory_analysis(dir_stats, Path("/tmp"), sort_by="size")

        assert "DIRECTORY ANALYSIS" in output
        assert "test" in output
        assert "test2" in output

    def test_format_directory_analysis_sort_by_count(self) -> None:
        """Test directory analysis sorted by count."""
        dir_stats = {
            Path("/tmp/small"): StorageStats(
                total_size=100,
                file_count=20,
                directory_count=1,
            ),
            Path("/tmp/large"): StorageStats(
                total_size=10000,
                file_count=5,
                directory_count=2,
            ),
        }

        output = format_directory_analysis(dir_stats, Path("/tmp"), sort_by="count")

        # When sorted by count, 'small' (20 files) should appear before 'large' (5 files)
        assert "DIRECTORY ANALYSIS" in output
        small_pos = output.find("small")
        large_pos = output.find("large")
        assert small_pos < large_pos
