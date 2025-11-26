"""Source file utilities for ASD.

Common functionality for preparing and managing HDL source files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.config import ModuleConfig
from ..core.repository import Repository
from .logging import get_logger

if TYPE_CHECKING:
    from ..core.library import LibraryResolver

logger = get_logger()


class SourceManager:
    """Manage HDL source files and include directories."""

    def __init__(self, repository: Repository):
        """Initialize source manager.

        Args:
            repository: Repository instance for path resolution
        """
        self.repo = repository
        self._lib_resolver: LibraryResolver | None = None

    def _get_library_resolver(self) -> LibraryResolver | None:
        """Get library resolver if libraries are configured.

        Returns:
            LibraryResolver instance or None if no libraries
        """
        if self._lib_resolver is None and self.repo.has_libraries():
            from ..core.library import LibraryResolver

            self._lib_resolver = LibraryResolver(self.repo)
        return self._lib_resolver

    def _resolve_source_path(self, path: str, base_path: Path | None = None) -> Path | None:
        """Resolve source path, handling library references.

        Args:
            path: Path string (local or @libname/path format)
            base_path: Base directory for resolving relative paths (e.g., TOML file's directory)

        Returns:
            Resolved Path or None if not found
        """
        lib_resolver = self._get_library_resolver()

        if lib_resolver and lib_resolver.is_library_path(path):
            try:
                return lib_resolver.resolve_path(path)
            except Exception as e:
                logger.warning(f"Failed to resolve library path '{path}': {e}")
                return None
        else:
            # Resolve relative paths against base_path (TOML directory) if provided
            p = Path(path)
            if not p.is_absolute() and base_path is not None:
                return (base_path / path).resolve()
            return self.repo.resolve_path(path)

    def prepare_sources(self, config: ModuleConfig) -> list[Path]:
        """Prepare source file paths from configuration.

        Handles both local paths and library paths (@libname/path).

        Args:
            config: Module configuration

        Returns:
            List of resolved source paths in compilation order
        """
        sources = []
        missing_files = []
        base_path = config.base_path

        # Add packages first (they often contain definitions needed by modules)
        for pkg in config.sources.packages:
            path = self._resolve_source_path(pkg, base_path)
            if path and path.exists():
                sources.append(path)
            else:
                missing_files.append(pkg)

        # Add modules
        for module in config.sources.modules:
            path = self._resolve_source_path(module, base_path)
            if path and path.exists():
                sources.append(path)
            else:
                missing_files.append(module)

        # Report missing files if any
        if missing_files:
            logger.warning(f"{len(missing_files)} source file(s) not found:")
            for file in missing_files[:5]:  # Show first 5 missing files
                logger.warning(f"  - {file}")
            if len(missing_files) > 5:
                logger.warning(f"  ... and {len(missing_files) - 5} more")

        return sources

    def get_include_dirs(self, config: ModuleConfig) -> list[Path]:
        """Get unique include directories from configuration.

        Handles both local paths and library paths (@libname/path).
        Auto-adds include directories from library sources.

        Args:
            config: Module configuration

        Returns:
            List of unique include directory paths
        """
        includes: list[Path] = []
        seen: set[Path] = set()
        base_path = config.base_path

        def add_include_dir(path: Path | None) -> None:
            """Add include directory if valid and not seen."""
            if path is None:
                return

            # Check if it's a directory or file
            if path.exists():
                if path.is_dir():
                    inc_dir = path
                else:
                    inc_dir = path.parent
            else:
                # File doesn't exist yet, use parent anyway
                inc_dir = path.parent

            if inc_dir not in seen and inc_dir.exists():
                includes.append(inc_dir)
                seen.add(inc_dir)

        # Process explicit include files
        for include_file in config.sources.includes:
            path = self._resolve_source_path(include_file, base_path)
            add_include_dir(path)

        # Check for resources that might have include files
        for resource_file in config.sources.resources:
            path = self._resolve_source_path(resource_file, base_path)
            if path and path.suffix in [".vh", ".svh", ".h"]:
                add_include_dir(path)

        # Auto-add include directories from library sources
        lib_resolver = self._get_library_resolver()
        if lib_resolver:
            # Collect library names from source paths
            lib_names: set[str] = set()
            all_sources = config.sources.packages + config.sources.modules + config.sources.includes
            for src in all_sources:
                if lib_resolver.is_library_path(src):
                    lib_name = lib_resolver.get_library_name(src)
                    if lib_name:
                        lib_names.add(lib_name)

            # Add include directories from each library
            for lib_name in lib_names:
                try:
                    lib_root = lib_resolver.get_library_root(lib_name)
                    # Add common include directory patterns from libraries
                    for inc_pattern in ["include", "inc", "rtl", "src"]:
                        inc_dir = lib_root / inc_pattern
                        if inc_dir.is_dir() and inc_dir not in seen:
                            includes.append(inc_dir)
                            seen.add(inc_dir)
                except Exception:
                    pass  # Library not installed, skip

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
                logger.error(f"Source file does not exist: {source}")
                all_valid = False
            elif not source.is_file():
                logger.error(f"Source path is not a file: {source}")
                all_valid = False
            elif not os.access(source, os.R_OK):
                logger.error(f"Source file is not readable: {source}")
                all_valid = False

        return all_valid
