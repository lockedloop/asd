"""Source file utilities for ASD.

Common functionality for preparing and managing HDL source files.
"""

import os
from pathlib import Path

from ..core.config import ModuleConfig
from ..core.repository import Repository


class SourceManager:
    """Manage HDL source files and include directories."""

    def __init__(self, repository: Repository):
        """Initialize source manager.

        Args:
            repository: Repository instance for path resolution
        """
        self.repo = repository

    def prepare_sources(self, config: ModuleConfig) -> list[Path]:
        """Prepare source file paths from configuration.

        Args:
            config: Module configuration

        Returns:
            List of resolved source paths in compilation order
        """
        sources = []
        missing_files = []

        # Add packages first (they often contain definitions needed by modules)
        for pkg in config.sources.packages:
            path = self.repo.resolve_path(pkg)
            if path.exists():
                sources.append(path)
            else:
                missing_files.append(pkg)

        # Add modules
        for module in config.sources.modules:
            path = self.repo.resolve_path(module)
            if path.exists():
                sources.append(path)
            else:
                missing_files.append(module)

        # Report missing files if any
        if missing_files:
            print(f"Warning: {len(missing_files)} source file(s) not found:")
            for file in missing_files[:5]:  # Show first 5 missing files
                print(f"  - {file}")
            if len(missing_files) > 5:
                print(f"  ... and {len(missing_files) - 5} more")

        return sources

    def get_include_dirs(self, config: ModuleConfig) -> list[Path]:
        """Get unique include directories from configuration.

        Args:
            config: Module configuration

        Returns:
            List of unique include directory paths
        """
        includes = []
        seen: set[Path] = set()

        for include_file in config.sources.includes:
            path = self.repo.resolve_path(include_file)

            # Check if it's a directory or file
            if path.is_dir():
                # It's already a directory
                inc_dir = path
            else:
                # It's a file, get its parent directory
                inc_dir = path.parent

            # Add only if not seen before
            if inc_dir not in seen:
                includes.append(inc_dir)
                seen.add(inc_dir)

        # Also check for resources that might have include files
        for resource_file in config.sources.resources:
            path = self.repo.resolve_path(resource_file)
            if path.suffix in [".vh", ".svh", ".h"]:
                inc_dir = path.parent
                if inc_dir not in seen:
                    includes.append(inc_dir)
                    seen.add(inc_dir)

        return includes

    def find_dependencies(self, source_file: Path, search_dirs: list[Path]) -> list[Path]:
        """Find dependencies for a source file.

        Args:
            source_file: Source file to analyze
            search_dirs: Directories to search for dependencies

        Returns:
            List of dependency file paths
        """
        dependencies: list[Path] = []

        # This could be enhanced with actual parsing
        # For now, it's a placeholder for future dependency resolution

        return dependencies

    def get_compilation_order(self, sources: list[Path]) -> list[Path]:
        """Determine optimal compilation order for source files.

        Args:
            sources: List of source files

        Returns:
            Ordered list of source files for compilation
        """
        # Simple heuristic: packages first, then modules
        packages = []
        modules = []
        others = []

        for source in sources:
            name_lower = source.name.lower()
            if "pkg" in name_lower or "package" in name_lower:
                packages.append(source)
            elif source.suffix in [".v", ".sv", ".vhdl", ".vhd"]:
                modules.append(source)
            else:
                others.append(source)

        # Return packages first, then others, then modules
        return packages + others + modules

    def validate_sources(self, sources: list[Path]) -> bool:
        """Validate that source files are readable.

        Args:
            sources: List of source files to validate

        Returns:
            True if all sources are valid
        """
        all_valid = True

        for source in sources:
            if not source.exists():
                print(f"Error: Source file does not exist: {source}")
                all_valid = False
            elif not source.is_file():
                print(f"Error: Source path is not a file: {source}")
                all_valid = False
            elif not os.access(source, os.R_OK):
                print(f"Error: Source file is not readable: {source}")
                all_valid = False

        return all_valid
