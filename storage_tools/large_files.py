"""Module for finding large files in directory trees."""

import heapq
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional, Pattern, Union

from storage_tools.utils import FileInfo, normalize_path, walk_directory


class GroupBy(Enum):
    """Grouping options for large files."""

    NONE = "none"
    DIRECTORY = "dir"
    EXTENSION = "ext"


@dataclass
class LargeFileSearchOptions:
    """Configuration options for large file search."""

    top_n: int = 20
    min_size: int = 0
    extensions: Optional[list[str]] = None
    modified_since: Optional[datetime] = None
    follow_symlinks: bool = False
    include_hidden: bool = False
    exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = None
    group_by: GroupBy = GroupBy.NONE
    max_depth: Optional[int] = None


class TopNTracker:
    """
    Efficiently track top N items using a min-heap.

    This is more efficient than keeping all items and sorting,
    especially when processing millions of files.
    """

    def __init__(self, n: int):
        """
        Initialize tracker.

        Args:
            n: Number of top items to track
        """
        if n <= 0:
            raise ValueError("n must be positive")
        self.n = n
        self._heap: list[tuple[int, int, FileInfo]] = []
        self._counter = 0  # For stable sorting

    def add(self, file_info: FileInfo) -> None:
        """
        Add a file to be considered for top N.

        Args:
            file_info: File information to consider
        """
        # Use file size directly for min-heap (keeps smallest at top)
        # Include counter for stable sorting when sizes are equal
        item = (file_info.size, self._counter, file_info)
        self._counter += 1

        if len(self._heap) < self.n:
            heapq.heappush(self._heap, item)
        else:
            # Only add if larger than smallest in heap
            if file_info.size > self._heap[0][0]:
                heapq.heapreplace(self._heap, item)

    def get_top_n(self) -> list[FileInfo]:
        """
        Get the top N files sorted by size (descending).

        Returns:
            List of FileInfo objects sorted by size (largest first)
        """
        # Sort by size (descending), then by counter for stability
        sorted_items = sorted(self._heap, key=lambda x: (-x[0], x[1]))
        return [item[2] for item in sorted_items]

    def __len__(self) -> int:
        """Get current number of tracked items."""
        return len(self._heap)


class LargeFileFinder:
    """Main class for finding large files in directory trees."""

    def __init__(self, options: Optional[LargeFileSearchOptions] = None):
        """
        Initialize finder with options.

        Args:
            options: Search configuration options
        """
        self.options = options or LargeFileSearchOptions()

    def find(self, path: Union[str, Path]) -> list[FileInfo]:
        """
        Find large files in the specified path.

        Args:
            path: Root path to search

        Returns:
            List of FileInfo objects for largest files, sorted by size (descending)

        Raises:
            FileNotFoundError: If path doesn't exist
            NotADirectoryError: If path is not a directory
        """
        root_path = normalize_path(path)
        tracker = TopNTracker(self.options.top_n)

        for file_info in self._scan_files(root_path):
            if self._should_include_file(file_info):
                tracker.add(file_info)

        return tracker.get_top_n()

    def find_grouped(self, path: Union[str, Path]) -> dict[str, list[FileInfo]]:
        """
        Find large files grouped by directory or extension.

        Args:
            path: Root path to search

        Returns:
            Dictionary mapping group name to list of FileInfo objects

        Raises:
            FileNotFoundError: If path doesn't exist
            NotADirectoryError: If path is not a directory
        """
        root_path = normalize_path(path)
        groups: dict[str, TopNTracker] = {}

        for file_info in self._scan_files(root_path):
            if self._should_include_file(file_info):
                group_key = self._get_group_key(file_info)

                if group_key not in groups:
                    groups[group_key] = TopNTracker(self.options.top_n)

                groups[group_key].add(file_info)

        # Convert trackers to lists
        return {key: tracker.get_top_n() for key, tracker in groups.items()}

    def _scan_files(self, root_path: Path) -> Iterator[FileInfo]:
        """
        Scan directory tree for files.

        Args:
            root_path: Root directory to scan

        Yields:
            FileInfo objects for each file
        """
        yield from walk_directory(
            root_path=root_path,
            follow_symlinks=self.options.follow_symlinks,
            exclude_patterns=self.options.exclude_patterns,
            include_hidden=self.options.include_hidden,
            max_depth=self.options.max_depth,
        )

    def _should_include_file(self, file_info: FileInfo) -> bool:
        """
        Check if file should be included based on filters.

        Args:
            file_info: File information

        Returns:
            True if file should be included, False otherwise
        """
        # Check minimum size
        if file_info.size < self.options.min_size:
            return False

        # Check extension filter
        if self.options.extensions:
            if file_info.extension not in self.options.extensions:
                return False

        # Check modification date filter
        if self.options.modified_since:
            file_modified = datetime.fromtimestamp(file_info.modified_time)
            if file_modified < self.options.modified_since:
                return False

        return True

    def _get_group_key(self, file_info: FileInfo) -> str:
        """
        Get grouping key for a file.

        Args:
            file_info: File information

        Returns:
            Group key string
        """
        if self.options.group_by == GroupBy.DIRECTORY:
            return str(file_info.path.parent)
        elif self.options.group_by == GroupBy.EXTENSION:
            ext = file_info.extension
            return ext if ext else "(no extension)"
        else:
            return "all"


def format_large_files_output(
    files: list[FileInfo], show_paths: bool = True, relative_to: Optional[Path] = None
) -> str:
    """
    Format large files list for display.

    Args:
        files: List of FileInfo objects to format
        show_paths: Whether to show full paths
        relative_to: If provided, show paths relative to this directory

    Returns:
        Formatted string for display
    """
    if not files:
        return "No files found."

    lines = []
    total_size = sum(f.size for f in files)

    lines.append(
        f"Found {len(files)} large files (Total: {files[0].size_formatted if files else '0 B'} -> {format_size(total_size)})"
    )
    lines.append("")
    lines.append(f"{'Size':<12} {'Modified':<20} {'File'}")
    lines.append("-" * 80)

    for file_info in files:
        modified = datetime.fromtimestamp(file_info.modified_time).strftime("%Y-%m-%d %H:%M:%S")

        file_path: Union[Path, str]
        if show_paths:
            if relative_to:
                try:
                    file_path = file_info.path.relative_to(relative_to)
                except ValueError:
                    file_path = file_info.path
            else:
                file_path = file_info.path
        else:
            file_path = file_info.path.name

        lines.append(f"{file_info.size_formatted:<12} {modified:<20} {file_path}")

    return "\n".join(lines)


def format_grouped_output(grouped_files: dict[str, list[FileInfo]], show_paths: bool = True) -> str:
    """
    Format grouped large files for display.

    Args:
        grouped_files: Dictionary of group name to file list
        show_paths: Whether to show full paths

    Returns:
        Formatted string for display
    """
    if not grouped_files:
        return "No files found."

    lines = []

    # Sort groups by total size (descending)
    sorted_groups = sorted(
        grouped_files.items(),
        key=lambda x: sum(f.size for f in x[1]),
        reverse=True,
    )

    for group_name, files in sorted_groups:
        if not files:
            continue

        total_size = sum(f.size for f in files)
        lines.append(f"\n{'='*80}")
        lines.append(f"Group: {group_name}")
        lines.append(f"Total: {format_size(total_size)} ({len(files)} files)")
        lines.append(f"{'='*80}\n")

        lines.append(f"{'Size':<12} {'Modified':<20} {'File'}")
        lines.append("-" * 80)

        for file_info in files:
            modified = datetime.fromtimestamp(file_info.modified_time).strftime("%Y-%m-%d %H:%M:%S")
            file_name: Union[Path, str] = file_info.path if show_paths else file_info.path.name

            lines.append(f"{file_info.size_formatted:<12} {modified:<20} {file_name}")

    return "\n".join(lines)


def format_size(size: int) -> str:
    """Helper to import format_size from utils."""
    from storage_tools.utils import format_size as _format_size

    return _format_size(size)
