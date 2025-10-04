"""Tests for the CLI module."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from storage_tools.cli import main


def test_main_help() -> None:
    """Test that the main CLI shows help."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Storage Tools" in result.output


def test_version() -> None:
    """Test that version option works."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_analyze_command() -> None:
    """Test the analyze command with temp directory."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.txt").write_text("a" * 100)
        (tmp_path / "file2.txt").write_text("b" * 1000)

        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert result.exit_code == 0
        assert "Analyzing folder" in result.output
        assert "FOLDER ANALYSIS SUMMARY" in result.output


def test_analyze_with_options() -> None:
    """Test analyze command with various options."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.txt").write_text("a" * 1000)
        (tmp_path / "file2.pdf").write_text("b" * 2000)

        # Test with --top option
        result = runner.invoke(main, ["analyze", str(tmp_path), "--top", "5"])
        assert result.exit_code == 0

        # Test with --depth option
        result = runner.invoke(main, ["analyze", str(tmp_path), "--depth", "1"])
        assert result.exit_code == 0

        # Test with --by-directory option
        result = runner.invoke(main, ["analyze", str(tmp_path), "--by-directory"])
        assert result.exit_code == 0
        assert "DIRECTORY ANALYSIS" in result.output


def test_analyze_nonexistent_path() -> None:
    """Test that analyze handles nonexistent path."""
    runner = CliRunner()
    result = runner.invoke(main, ["analyze", "/nonexistent/path/xyz123"])
    assert result.exit_code != 0


def test_find_duplicates_command() -> None:
    """Test the find-duplicates command."""
    runner = CliRunner()
    result = runner.invoke(main, ["find-duplicates"])
    assert result.exit_code == 0
    assert "Coming soon" in result.output


def test_find_duplicate_folders_command() -> None:
    """Test the find-duplicate-folders command."""
    runner = CliRunner()
    result = runner.invoke(main, ["find-duplicate-folders"])
    assert result.exit_code == 0
    assert "Coming soon" in result.output


def test_find_large_files_command() -> None:
    """Test the find-large-files command with temp directory."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.txt").write_text("a" * 100)
        (tmp_path / "file2.txt").write_text("b" * 1000)

        result = runner.invoke(main, ["find-large-files", str(tmp_path)])
        assert result.exit_code == 0
        assert "Searching for large files" in result.output


def test_find_large_files_with_options() -> None:
    """Test find-large-files with various options."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.txt").write_text("a" * 1000)
        (tmp_path / "file2.pdf").write_text("b" * 2000)

        # Test with --top option
        result = runner.invoke(main, ["find-large-files", str(tmp_path), "--top", "5"])
        assert result.exit_code == 0

        # Test with --extension option
        result = runner.invoke(main, ["find-large-files", str(tmp_path), "--extension", "txt"])
        assert result.exit_code == 0

        # Test with --min-size option
        result = runner.invoke(main, ["find-large-files", str(tmp_path), "--min-size", "500B"])
        assert result.exit_code == 0


def test_find_large_files_invalid_size() -> None:
    """Test that invalid size format is handled."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["find-large-files", str(tmpdir), "--min-size", "invalid"])
        assert result.exit_code != 0


def test_find_large_files_invalid_date() -> None:
    """Test that invalid date format is handled."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            main, ["find-large-files", str(tmpdir), "--modified-since", "invalid"]
        )
        assert result.exit_code != 0


def test_find_large_files_nonexistent_path() -> None:
    """Test that nonexistent path is handled."""
    runner = CliRunner()
    result = runner.invoke(main, ["find-large-files", "/nonexistent/path/xyz123"])
    assert result.exit_code != 0
