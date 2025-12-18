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
    from ..core.loader import TOMLLoader

logger = get_logger()


class SourceManager:
    """Manage HDL source files and include directories."""

    def __init__(self, repository: Repository, loader: TOMLLoader | None = None) -> None:
        """Initialize source manager.

        Args:
            repository: Repository instance for path resolution
            loader: Optional TOML loader for resolving tomls dependencies
        """
        self.repo = repository
        self.loader = loader
        self._lib_resolver: LibraryResolver | None = None
        self._visited_tomls: set[Path] = set()

    def _get_library_resolver(self) -> LibraryResolver | None:
        """Get library resolver if libraries are configured.

        Returns:
            LibraryResolver instance or None if no libraries
        """
        if self._lib_resolver is None and self.repo.has_libraries():
            from ..core.library import LibraryResolver

            self._lib_resolver = LibraryResolver(self.repo)
        return self._lib_resolver

    def _resolve_source_path(self, path: str) -> Path | None:
        """Resolve source path, handling library references.

        Args:
            path: Path string (local or @libname/path format)

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
            return self.repo.resolve_path(path)

    def prepare_sources(self, config: ModuleConfig, toml_path: Path | None = None) -> list[Path]:
        """Prepare source file paths from configuration.

        Handles both local paths and library paths (@libname/path).
        Recursively resolves TOML dependencies specified in sources.tomls.

        Args:
            config: Module configuration
            toml_path: Path to current TOML file (for cycle detection)

        Returns:
            List of resolved source paths in compilation order
        """
        sources: list[Path] = []
        missing_files: list[str] = []

        # Reset visited tracking for top-level calls (new configuration run)
        if toml_path is None:
            self._visited_tomls.clear()

        # Track current TOML to prevent circular dependencies
        if toml_path:
            resolved_toml = toml_path.resolve()
            if resolved_toml in self._visited_tomls:
                logger.debug(f"Skipping already processed TOML: {toml_path}")
                return []
            self._visited_tomls.add(resolved_toml)

        # Process TOML dependencies first (recursive)
        if self.loader and config.sources.tomls:
            for toml_ref in config.sources.tomls:
                dep_path = self._resolve_source_path(toml_ref)
                if dep_path and dep_path.exists():
                    try:
                        dep_config = self.loader.load(dep_path)
                        dep_sources = self.prepare_sources(dep_config, dep_path)
                        sources.extend(dep_sources)
                    except Exception as e:
                        logger.warning(f"Failed to load TOML dependency '{toml_ref}': {e}")
                else:
                    logger.warning(f"TOML dependency not found: {toml_ref}")

        # Add packages first (they often contain definitions needed by modules)
        for pkg in config.sources.packages:
            path = self._resolve_source_path(pkg)
            if path and path.exists():
                if path not in sources:  # Avoid duplicates
                    sources.append(path)
            else:
                missing_files.append(pkg)

        # Add modules
        for module in config.sources.modules:
            path = self._resolve_source_path(module)
            if path and path.exists():
                if path not in sources:  # Avoid duplicates
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

    def reset_visited(self) -> None:
        """Reset visited TOML tracking for new top-level call."""
        self._visited_tomls.clear()

    def get_include_dirs(self, config: ModuleConfig, toml_path: Path | None = None) -> list[Path]:
        """Get unique include directories from configuration.

        Handles both local paths and library paths (@libname/path).
        Auto-adds include directories from library sources and TOML dependencies.

        Args:
            config: Module configuration
            toml_path: Path to current TOML file (for cycle detection)

        Returns:
            List of unique include directory paths
        """
        includes: list[Path] = []
        seen: set[Path] = set()
        visited_tomls: set[Path] = set()

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

        # Track current TOML to prevent circular dependencies
        if toml_path:
            resolved_toml = toml_path.resolve()
            visited_tomls.add(resolved_toml)

        # Process TOML dependencies first (recursive)
        if self.loader and config.sources.tomls:
            for toml_ref in config.sources.tomls:
                dep_path = self._resolve_source_path(toml_ref)
                if dep_path and dep_path.exists():
                    resolved_dep = dep_path.resolve()
                    if resolved_dep not in visited_tomls:
                        visited_tomls.add(resolved_dep)
                        try:
                            dep_config = self.loader.load(dep_path)
                            dep_includes = self.get_include_dirs(dep_config, dep_path)
                            for inc in dep_includes:
                                if inc not in seen:
                                    includes.append(inc)
                                    seen.add(inc)
                        except Exception as e:
                            logger.warning(f"Failed to get includes from TOML '{toml_ref}': {e}")

        # Process explicit include files
        for include_file in config.sources.includes:
            path = self._resolve_source_path(include_file)
            add_include_dir(path)

        # Check for resources that might have include files
        for resource_file in config.sources.resources:
            path = self._resolve_source_path(resource_file)
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
