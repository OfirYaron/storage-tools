"""Utility functions and classes for storage tools."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Pattern, Union


def format_size(size_bytes: int, decimal_places: int = 2) -> str:
    """
    Convert bytes to human-readable format.

    Args:
        size_bytes: Size in bytes
        decimal_places: Number of decimal places to show

    Returns:
        Human-readable size string (e.g., "1.23 GB")

    Examples:
        >>> format_size(1024)
        '1.00 KB'
        >>> format_size(1536, 1)
        '1.5 KB'
        >>> format_size(1073741824)
        '1.00 GB'
    """
    if size_bytes < 0:
        raise ValueError("Size cannot be negative")

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:  # Bytes - no decimal places
        return f"{int(size)} {units[unit_index]}"

    return f"{size:.{decimal_places}f} {units[unit_index]}"


def parse_size(size_str: str) -> int:
    """
    Parse human-readable size string to bytes.

    Args:
        size_str: Size string like "10MB", "1.5GB", "100KB"

    Returns:
        Size in bytes

    Raises:
        ValueError: If size string is invalid

    Examples:
        >>> parse_size("1KB")
        1024
        >>> parse_size("1.5MB")
        1572864
        >>> parse_size("100")
        100
    """
    size_str = size_str.strip().upper()

    # If no unit specified, assume bytes
    if size_str.isdigit():
        return int(size_str)

    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
    }

    # Extract number and unit
    import re

    match = re.match(r"^([\d.]+)\s*([A-Z]+)$", size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    number_str, unit = match.groups()

    if unit not in units:
        raise ValueError(f"Unknown unit: {unit}. Use one of {list(units.keys())}")

    try:
        number = float(number_str)
    except ValueError:
        raise ValueError(f"Invalid number: {number_str}")

    return int(number * units[unit])


def normalize_path(path: Union[str, Path]) -> Path:
    """
    Normalize a path by resolving it to absolute path.

    Args:
        path: Path to normalize

    Returns:
        Normalized absolute Path object

    Examples:
        >>> normalize_path("~/documents")
        PosixPath('/Users/username/documents')
        >>> normalize_path("./test")
        PosixPath('/current/dir/test')
    """
    path_obj = Path(path)
    return path_obj.expanduser().resolve()


def should_exclude_path(
    path: Path,
    exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = None,
    include_hidden: bool = False,
) -> bool:
    """
    Check if a path should be excluded based on patterns and settings.

    Args:
        path: Path to check
        exclude_patterns: List of glob patterns or regex patterns to exclude
        include_hidden: Whether to include hidden files/folders

    Returns:
        True if path should be excluded, False otherwise

    Examples:
        >>> should_exclude_path(Path("/home/user/.git"))
        True
        >>> should_exclude_path(Path("/home/user/.git"), include_hidden=True)
        False
    """
    import fnmatch

    # Check hidden files/folders
    if not include_hidden:
        # Check if any part of the path is hidden (starts with .)
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True

    # Check exclude patterns
    if exclude_patterns:
        path_str = str(path)
        for pattern in exclude_patterns:
            if isinstance(pattern, str):
                # Glob pattern matching
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
            else:
                # Regex pattern matching
                if pattern.search(path_str):
                    return True

    return False


@dataclass
class FileInfo:
    """Information about a file."""

    path: Path
    size: int
    modified_time: float
    is_symlink: bool = False

    @property
    def size_formatted(self) -> str:
        """Get human-readable size."""
        return format_size(self.size)

    @property
    def name(self) -> str:
        """Get file name."""
        return self.path.name

    @property
    def extension(self) -> str:
        """Get file extension (lowercase, without dot)."""
        return self.path.suffix.lower().lstrip(".")

    def __lt__(self, other: "FileInfo") -> bool:
        """Compare files by size (for sorting)."""
        return self.size < other.size


def walk_directory(
    root_path: Path,
    follow_symlinks: bool = False,
    exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = None,
    include_hidden: bool = False,
    max_depth: Optional[int] = None,
) -> Iterator[FileInfo]:
    """
    Walk through directory tree and yield FileInfo for each file.

    Args:
        root_path: Root directory to start walking
        follow_symlinks: Whether to follow symbolic links
        exclude_patterns: Patterns to exclude
        include_hidden: Whether to include hidden files
        max_depth: Maximum depth to traverse (None for unlimited)

    Yields:
        FileInfo objects for each file found

    Raises:
        FileNotFoundError: If root_path doesn't exist
        PermissionError: If root_path is not accessible
    """
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    if not root_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root_path}")

    def _walk_recursive(current_path: Path, current_depth: int) -> Iterator[FileInfo]:
        """Recursive helper function."""
        if max_depth is not None and current_depth > max_depth:
            return

        try:
            with os.scandir(current_path) as entries:
                for entry in entries:
                    try:
                        entry_path = Path(entry.path)

                        # Check if should be excluded
                        if should_exclude_path(entry_path, exclude_patterns, include_hidden):
                            continue

                        # Handle symlinks
                        if entry.is_symlink():
                            if not follow_symlinks:
                                continue
                            # Check for circular references
                            try:
                                entry_path.resolve(strict=True)
                            except (OSError, RuntimeError):
                                # Circular reference or broken symlink
                                continue

                        # Process files
                        if entry.is_file(follow_symlinks=follow_symlinks):
                            stat_info = entry.stat(follow_symlinks=follow_symlinks)
                            yield FileInfo(
                                path=entry_path,
                                size=stat_info.st_size,
                                modified_time=stat_info.st_mtime,
                                is_symlink=entry.is_symlink(),
                            )

                        # Recurse into directories
                        elif entry.is_dir(follow_symlinks=follow_symlinks):
                            yield from _walk_recursive(entry_path, current_depth + 1)

                    except (PermissionError, OSError):
                        # Log and continue on permission errors for individual files
                        # In production, this should use proper logging
                        continue

        except (PermissionError, OSError):
            # Log and continue on permission errors for directories
            # In production, this should use proper logging
            pass

    yield from _walk_recursive(root_path, 0)


def get_file_info(file_path: Path, follow_symlinks: bool = True) -> FileInfo:
    """
    Get FileInfo for a single file.

    Args:
        file_path: Path to the file
        follow_symlinks: Whether to follow symbolic links

    Returns:
        FileInfo object

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file is not accessible
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    stat_info = file_path.stat() if follow_symlinks else file_path.lstat()

    return FileInfo(
        path=file_path,
        size=stat_info.st_size,
        modified_time=stat_info.st_mtime,
        is_symlink=file_path.is_symlink(),
    )
