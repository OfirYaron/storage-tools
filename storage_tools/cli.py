"""Command-line interface for Storage Tools."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Pattern, Union

import click

from storage_tools import __version__
from storage_tools.analyzer import (
    FolderAnalysisOptions,
    FolderAnalyzer,
    format_analysis_output,
    format_directory_analysis,
)
from storage_tools.large_files import (
    GroupBy,
    LargeFileFinder,
    LargeFileSearchOptions,
    format_grouped_output,
    format_large_files_output,
)
from storage_tools.utils import parse_size


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Storage Tools - Manage and analyze your files and folders."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Maximum directory depth to traverse",
)
@click.option(
    "--sort-by",
    type=click.Choice(["size", "name", "count"], case_sensitive=False),
    default="size",
    help="Sort criterion for results (default: size)",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude patterns (glob style). Can be specified multiple times.",
)
@click.option(
    "--follow-symlinks",
    is_flag=True,
    help="Follow symbolic links",
)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Include hidden files and directories",
)
@click.option(
    "--by-directory",
    is_flag=True,
    help="Show analysis broken down by directory",
)
@click.option(
    "--top",
    "-n",
    type=int,
    default=10,
    help="Number of largest files to show in summary (default: 10)",
)
@click.option(
    "--no-extensions",
    is_flag=True,
    help="Don't show file type distribution",
)
@click.option(
    "--no-largest",
    is_flag=True,
    help="Don't show largest files",
)
def analyze(
    path: str,
    depth: Optional[int],
    sort_by: str,
    exclude: tuple[str, ...],
    follow_symlinks: bool,
    include_hidden: bool,
    by_directory: bool,
    top: int,
    no_extensions: bool,
    no_largest: bool,
) -> None:
    """Analyze folder disk usage and statistics in PATH (default: current directory)."""
    try:
        # Convert exclude patterns to list
        exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = (
            list(exclude) if exclude else None
        )

        # Create options
        options = FolderAnalysisOptions(
            follow_symlinks=follow_symlinks,
            include_hidden=include_hidden,
            exclude_patterns=exclude_patterns,
            max_depth=depth,
            track_largest_n=top,
            sort_by=sort_by.lower(),
        )

        # Create analyzer
        analyzer = FolderAnalyzer(options)
        search_path = Path(path).resolve()

        click.echo(f"Analyzing folder: {search_path}")
        if depth is not None:
            click.echo(f"Maximum depth: {depth}")
        if exclude:
            click.echo(f"Excluding: {', '.join(exclude)}")
        click.echo("")

        if by_directory:
            # Directory-by-directory analysis
            dir_stats = analyzer.analyze_by_directory(search_path)
            output = format_directory_analysis(dir_stats, search_path, sort_by.lower())
            click.echo(output)
        else:
            # Overall analysis
            stats = analyzer.analyze(search_path)
            output = format_analysis_output(
                stats, show_extensions=not no_extensions, show_largest=not no_largest
            )
            click.echo(output)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except NotADirectoryError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\n\nAnalysis interrupted by user.", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        raise click.Abort()


@main.command()
def find_duplicates() -> None:
    """Find duplicate files based on content."""
    click.echo("Duplicate files search feature - Coming soon!")


@main.command()
def find_duplicate_folders() -> None:
    """Find duplicate folders with similar content."""
    click.echo("Duplicate folders search feature - Coming soon!")


@main.command(name="find-large-files")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--top",
    "-n",
    type=int,
    default=20,
    help="Number of largest files to show (default: 20)",
)
@click.option(
    "--min-size",
    type=str,
    default=None,
    help="Minimum file size (e.g., 10MB, 1GB)",
)
@click.option(
    "--extension",
    "-e",
    multiple=True,
    help="Filter by file extension (e.g., pdf, jpg). Can be specified multiple times.",
)
@click.option(
    "--modified-since",
    type=str,
    default=None,
    help="Only show files modified after this date (YYYY-MM-DD)",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Exclude patterns (glob style). Can be specified multiple times.",
)
@click.option(
    "--group-by",
    type=click.Choice(["dir", "ext"], case_sensitive=False),
    default=None,
    help="Group results by directory or extension",
)
@click.option(
    "--follow-symlinks",
    is_flag=True,
    help="Follow symbolic links",
)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Include hidden files and directories",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Maximum directory depth to traverse",
)
@click.option(
    "--relative",
    is_flag=True,
    help="Show paths relative to search directory",
)
def find_large_files(
    path: str,
    top: int,
    min_size: Optional[str],
    extension: tuple[str, ...],
    modified_since: Optional[str],
    exclude: tuple[str, ...],
    group_by: Optional[str],
    follow_symlinks: bool,
    include_hidden: bool,
    depth: Optional[int],
    relative: bool,
) -> None:
    """Find the largest files in PATH (default: current directory)."""
    try:
        # Parse min_size if provided
        min_size_bytes = 0
        if min_size:
            try:
                min_size_bytes = parse_size(min_size)
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                raise click.Abort()

        # Parse modified_since if provided
        modified_since_dt = None
        if modified_since:
            try:
                modified_since_dt = datetime.strptime(modified_since, "%Y-%m-%d")
            except ValueError:
                click.echo("Error: Invalid date format. Use YYYY-MM-DD", err=True)
                raise click.Abort()

        # Normalize extensions (remove dots, make lowercase)
        extensions_list = [ext.lower().lstrip(".") for ext in extension] if extension else None

        # Convert exclude patterns to list (type: ignore for Pattern compatibility)
        exclude_patterns: Optional[list[Union[str, Pattern[str]]]] = (
            list(exclude) if exclude else None
        )

        # Determine group_by enum
        group_by_enum = GroupBy.NONE
        if group_by:
            if group_by.lower() == "dir":
                group_by_enum = GroupBy.DIRECTORY
            elif group_by.lower() == "ext":
                group_by_enum = GroupBy.EXTENSION

        # Create options
        options = LargeFileSearchOptions(
            top_n=top,
            min_size=min_size_bytes,
            extensions=extensions_list,
            modified_since=modified_since_dt,
            follow_symlinks=follow_symlinks,
            include_hidden=include_hidden,
            exclude_patterns=exclude_patterns,
            group_by=group_by_enum,
            max_depth=depth,
        )

        # Create finder and search
        finder = LargeFileFinder(options)
        search_path = Path(path).resolve()

        click.echo(f"Searching for large files in: {search_path}")
        if min_size:
            click.echo(f"Minimum size: {min_size}")
        if extensions_list:
            click.echo(f"Extensions: {', '.join(extensions_list)}")
        if modified_since:
            click.echo(f"Modified since: {modified_since}")
        click.echo("")

        if group_by_enum != GroupBy.NONE:
            # Grouped search
            grouped_results = finder.find_grouped(search_path)
            output = format_grouped_output(grouped_results, show_paths=True)
        else:
            # Regular search
            results = finder.find(search_path)
            relative_to = search_path if relative else None
            output = format_large_files_output(results, show_paths=True, relative_to=relative_to)

        click.echo(output)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except NotADirectoryError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\n\nSearch interrupted by user.", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
