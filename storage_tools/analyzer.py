"""Module for analyzing folder disk usage and statistics."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Pattern, Union

from storage_tools.utils import FileInfo, format_size, normalize_path, walk_directory


@dataclass
class StorageStats:
    """Statistics about storage usage in a directory."""

    total_size: int = 0
    file_count: int = 0
    directory_count: int = 0
    extension_stats: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )  # ext -> (count, size)
    largest_files: list[FileInfo] = field(default_factory=list)
    deepest_path: Optional[Path] = None
    deepest_level: int = 0
    oldest_file: Optional[FileInfo] = None
    newest_file: Optional[FileInfo] = None

    @property
    def total_size_formatted(self) -> str:
        """Get human-readable total size."""
        return format_size(self.total_size)

    @property
    def average_file_size(self) -> int:
        """Calculate average file size."""
        return self.total_size // self.file_count if self.file_count > 0 else 0

    @property
    def average_file_size_formatted(self) -> str:
        """Get human-readable average file size."""
        return format_size(self.average_file_size)


@dataclass
class FolderAnalysisOptions:
    """Configuration options for folder analysis."""

    follow_symlinks: bool = False
    include_hidden: bool = False
    exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = None
    max_depth: Optional[int] = None
    track_largest_n: int = 10
    sort_by: str = "size"  # size, name, count


class FolderAnalyzer:
    """Analyzes folder disk usage and provides detailed statistics."""

    def __init__(self, options: Optional[FolderAnalysisOptions] = None):
        """
        Initialize analyzer with options.

        Args:
            options: Analysis configuration options
        """
        self.options = options or FolderAnalysisOptions()
        self._stats = StorageStats()
        self._directory_sizes: dict[Path, int] = {}

    def analyze(self, path: Union[str, Path]) -> StorageStats:
        """
        Analyze a directory and return detailed statistics.

        Args:
            path: Root path to analyze

        Returns:
            StorageStats object with analysis results

        Raises:
            FileNotFoundError: If path doesn't exist
            NotADirectoryError: If path is not a directory
        """
        root_path = normalize_path(path)
        self._stats = StorageStats()
        self._directory_sizes = {}

        # Count directories first
        self._count_directories(root_path)

        # Analyze files
        for file_info in walk_directory(
            root_path=root_path,
            follow_symlinks=self.options.follow_symlinks,
            exclude_patterns=self.options.exclude_patterns,
            include_hidden=self.options.include_hidden,
            max_depth=self.options.max_depth,
        ):
            self._process_file(file_info, root_path)

        # Sort largest files
        self._stats.largest_files.sort(key=lambda f: f.size, reverse=True)
        self._stats.largest_files = self._stats.largest_files[: self.options.track_largest_n]

        return self._stats

    def analyze_by_directory(self, path: Union[str, Path]) -> dict[Path, StorageStats]:
        """
        Analyze and return statistics for each subdirectory.

        Args:
            path: Root path to analyze

        Returns:
            Dictionary mapping directory paths to their StorageStats
        """
        root_path = normalize_path(path)

        # First do a complete analysis
        self.analyze(root_path)

        # Create stats for each directory
        dir_stats: dict[Path, StorageStats] = {}

        for file_info in walk_directory(
            root_path=root_path,
            follow_symlinks=self.options.follow_symlinks,
            exclude_patterns=self.options.exclude_patterns,
            include_hidden=self.options.include_hidden,
            max_depth=self.options.max_depth,
        ):
            parent_dir = file_info.path.parent

            if parent_dir not in dir_stats:
                dir_stats[parent_dir] = StorageStats()

            stats = dir_stats[parent_dir]
            stats.total_size += file_info.size
            stats.file_count += 1

            # Track extension stats
            ext = file_info.extension
            if ext:
                count, size = stats.extension_stats.get(ext, (0, 0))
                stats.extension_stats[ext] = (count + 1, size + file_info.size)

        # Count subdirectories for each directory
        for dir_path in dir_stats.keys():
            try:
                subdirs = [d for d in dir_path.iterdir() if d.is_dir() and not d.is_symlink()]
                dir_stats[dir_path].directory_count = len(subdirs)
            except (PermissionError, OSError):
                pass

        return dir_stats

    def _count_directories(self, root_path: Path) -> None:
        """
        Count total number of directories.

        Args:
            root_path: Root path to start counting from
        """

        def _count_recursive(current_path: Path, current_depth: int) -> None:
            if self.options.max_depth is not None and current_depth >= self.options.max_depth:
                return

            try:
                for entry in current_path.iterdir():
                    if entry.is_dir() and not entry.is_symlink():
                        # Only count if within depth limit
                        if self.options.max_depth is None or current_depth < self.options.max_depth:
                            self._stats.directory_count += 1
                            _count_recursive(entry, current_depth + 1)
            except (PermissionError, OSError):
                pass

        _count_recursive(root_path, 0)

    def _process_file(self, file_info: FileInfo, root_path: Path) -> None:
        """
        Process a single file and update statistics.

        Args:
            file_info: File information to process
            root_path: Root path being analyzed
        """
        # Update basic counts
        self._stats.total_size += file_info.size
        self._stats.file_count += 1

        # Track extension statistics
        ext = file_info.extension
        if ext:
            count, size = self._stats.extension_stats.get(ext, (0, 0))
            self._stats.extension_stats[ext] = (count + 1, size + file_info.size)

        # Track largest files
        self._stats.largest_files.append(file_info)

        # Track deepest path
        try:
            relative_path = file_info.path.relative_to(root_path)
            depth = len(relative_path.parts)
            if depth > self._stats.deepest_level:
                self._stats.deepest_level = depth
                self._stats.deepest_path = file_info.path
        except ValueError:
            pass

        # Track oldest and newest files
        if (
            self._stats.oldest_file is None
            or file_info.modified_time < self._stats.oldest_file.modified_time
        ):
            self._stats.oldest_file = file_info

        if (
            self._stats.newest_file is None
            or file_info.modified_time > self._stats.newest_file.modified_time
        ):
            self._stats.newest_file = file_info


def format_analysis_output(
    stats: StorageStats, show_extensions: bool = True, show_largest: bool = True
) -> str:
    """
    Format analysis statistics for display.

    Args:
        stats: Statistics to format
        show_extensions: Whether to show extension breakdown
        show_largest: Whether to show largest files

    Returns:
        Formatted string for display
    """
    lines = []

    # Summary
    lines.append("=" * 80)
    lines.append("FOLDER ANALYSIS SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Total Size:       {stats.total_size_formatted}")
    lines.append(f"File Count:       {stats.file_count:,}")
    lines.append(f"Directory Count:  {stats.directory_count:,}")
    lines.append(f"Average File Size: {stats.average_file_size_formatted}")
    lines.append("")

    # Deepest path
    if stats.deepest_path:
        lines.append(f"Deepest Path:     {stats.deepest_path}")
        lines.append(f"Depth Level:      {stats.deepest_level}")
        lines.append("")

    # Oldest and newest files
    if stats.oldest_file:
        oldest_date = datetime.fromtimestamp(stats.oldest_file.modified_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        lines.append(f"Oldest File:      {stats.oldest_file.path.name}")
        lines.append(f"                  {oldest_date}")

    if stats.newest_file:
        newest_date = datetime.fromtimestamp(stats.newest_file.modified_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        lines.append(f"Newest File:      {stats.newest_file.path.name}")
        lines.append(f"                  {newest_date}")
        lines.append("")

    # Extension breakdown
    if show_extensions and stats.extension_stats:
        lines.append("=" * 80)
        lines.append("FILE TYPE DISTRIBUTION")
        lines.append("=" * 80)
        lines.append(f"{'Extension':<15} {'Count':>10} {'Size':>15} {'% of Total':>12}")
        lines.append("-" * 80)

        # Sort by size (descending)
        sorted_exts = sorted(stats.extension_stats.items(), key=lambda x: x[1][1], reverse=True)

        for ext, (count, size) in sorted_exts[:20]:  # Top 20 extensions
            percentage = (size / stats.total_size * 100) if stats.total_size > 0 else 0
            lines.append(f"{ext:<15} {count:>10,} {format_size(size):>15} {percentage:>11.1f}%")
        lines.append("")

    # Largest files
    if show_largest and stats.largest_files:
        lines.append("=" * 80)
        lines.append(f"LARGEST FILES (Top {len(stats.largest_files)})")
        lines.append("=" * 80)
        lines.append(f"{'Size':<15} {'Modified':<20} {'File'}")
        lines.append("-" * 80)

        for file_info in stats.largest_files:
            modified = datetime.fromtimestamp(file_info.modified_time).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{file_info.size_formatted:<15} {modified:<20} {file_info.path.name}")
        lines.append("")

    return "\n".join(lines)


def format_directory_analysis(
    dir_stats: dict[Path, StorageStats], root_path: Path, sort_by: str = "size"
) -> str:
    """
    Format directory-by-directory analysis.

    Args:
        dir_stats: Dictionary of directory statistics
        root_path: Root path being analyzed
        sort_by: Sort criterion (size, name, count)

    Returns:
        Formatted string for display
    """
    lines = []

    lines.append("=" * 80)
    lines.append("DIRECTORY ANALYSIS")
    lines.append("=" * 80)
    lines.append(f"{'Directory':<45} {'Files':>8} {'Dirs':>8} {'Size':>15}")
    lines.append("-" * 80)

    # Sort directories
    if sort_by == "size":
        sorted_dirs = sorted(dir_stats.items(), key=lambda x: x[1].total_size, reverse=True)
    elif sort_by == "count":
        sorted_dirs = sorted(dir_stats.items(), key=lambda x: x[1].file_count, reverse=True)
    else:  # name
        sorted_dirs = sorted(dir_stats.items(), key=lambda x: str(x[0]))

    for dir_path, stats in sorted_dirs[:50]:  # Top 50 directories
        try:
            rel_path = dir_path.relative_to(root_path)
            display_path = str(rel_path) if str(rel_path) != "." else "(root)"
        except ValueError:
            display_path = str(dir_path)

        # Truncate if too long
        if len(display_path) > 43:
            display_path = "..." + display_path[-40:]

        lines.append(
            f"{display_path:<45} {stats.file_count:>8,} "
            f"{stats.directory_count:>8,} {stats.total_size_formatted:>15}"
        )

    lines.append("")
    return "\n".join(lines)
