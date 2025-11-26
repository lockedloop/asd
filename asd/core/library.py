"""Library management for ASD.

Handles library resolution, Git operations, and transitive dependencies.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tomli
import tomli_w

from ..utils.logging import get_logger
from .library_config import LibraryManifest, LibrarySpec
from .repository import Repository

logger = get_logger()


class LibraryError(Exception):
    """Base exception for library operations."""

    pass


class CircularLibraryDependencyError(LibraryError):
    """Raised when circular library dependencies are detected."""

    pass


class LibraryNotFoundError(LibraryError):
    """Raised when a referenced library is not found."""

    pass


@dataclass
class ResolvedLibrary:
    """Represents a resolved library with its local path."""

    name: str
    git_url: str
    version_type: str  # 'tag', 'branch', or 'commit'
    version: str
    path: Path  # Local path in .asd/libs/


class LibraryResolver:
    """Resolves @libname/path to absolute paths."""

    # Pattern to match @libname/path syntax
    LIBRARY_PATH_PATTERN = re.compile(r"^@([a-zA-Z0-9_-]+)/(.+)$")

    def __init__(self, repository: Repository) -> None:
        """Initialize resolver with repository.

        Args:
            repository: Repository instance for path resolution
        """
        self.repo = repository

    def is_library_path(self, path: str) -> bool:
        """Check if path uses @libname/ syntax.

        Args:
            path: Path string to check

        Returns:
            True if path starts with @libname/
        """
        return path.startswith("@") and "/" in path

    def parse_library_path(self, path: str) -> tuple[str, str] | None:
        """Parse @libname/relative/path into (library_name, relative_path).

        Args:
            path: Path string like "@mylib/rtl/counter.sv"

        Returns:
            Tuple of (library_name, relative_path) or None if not a library path
        """
        match = self.LIBRARY_PATH_PATTERN.match(path)
        if match:
            return match.group(1), match.group(2)
        return None

    def get_library_name(self, path: str) -> str | None:
        """Extract library name from @libname/path.

        Args:
            path: Path string like "@mylib/rtl/counter.sv"

        Returns:
            Library name or None if not a library path
        """
        parsed = self.parse_library_path(path)
        return parsed[0] if parsed else None

    def resolve_path(self, lib_path: str) -> Path:
        """Resolve @libname/path to absolute path.

        Args:
            lib_path: Path like "@mylib/rtl/counter.sv"

        Returns:
            Absolute path to the file

        Raises:
            LibraryNotFoundError: If library is not installed
            ValueError: If path format is invalid
        """
        parsed = self.parse_library_path(lib_path)
        if not parsed:
            raise ValueError(f"Invalid library path format: {lib_path}")

        lib_name, relative_path = parsed
        lib_dir = self.repo.libs_dir / lib_name

        if not lib_dir.exists():
            raise LibraryNotFoundError(
                f"Library '{lib_name}' not found. Run 'asd lib install' to install libraries."
            )

        return lib_dir / relative_path

    def get_library_root(self, lib_name: str) -> Path:
        """Get the root directory of an installed library.

        Args:
            lib_name: Library name

        Returns:
            Path to the library root directory

        Raises:
            LibraryNotFoundError: If library is not installed
        """
        lib_dir = self.repo.libs_dir / lib_name
        if not lib_dir.exists():
            raise LibraryNotFoundError(
                f"Library '{lib_name}' not found. Run 'asd lib install' to install libraries."
            )
        return lib_dir


class LibraryManager:
    """Manages library installation and updates."""

    def __init__(self, repository: Repository) -> None:
        """Initialize manager with repository.

        Args:
            repository: Repository instance
        """
        self.repo = repository
        self.resolver = LibraryResolver(repository)

    def load_manifest(self) -> LibraryManifest:
        """Load libraries.toml manifest.

        Returns:
            LibraryManifest instance

        Raises:
            FileNotFoundError: If manifest doesn't exist
        """
        if not self.repo.manifest_path.exists():
            return LibraryManifest()

        with open(self.repo.manifest_path, "rb") as f:
            data = tomli.load(f)

        # Parse libraries
        libraries: dict[str, LibrarySpec] = {}
        for name, lib_data in data.get("libraries", {}).items():
            libraries[name] = LibrarySpec(**lib_data)

        return LibraryManifest(libraries=libraries)

    def save_manifest(self, manifest: LibraryManifest) -> None:
        """Save libraries.toml manifest.

        Args:
            manifest: LibraryManifest to save
        """
        # Ensure .asd directory exists
        self.repo.asd_dir.mkdir(parents=True, exist_ok=True)

        with open(self.repo.manifest_path, "wb") as f:
            tomli_w.dump(manifest.to_toml_dict(), f)

    def derive_name_from_url(self, git_url: str) -> str:
        """Derive library name from git URL.

        Examples:
            https://github.com/user/mylib.git -> mylib
            git@github.com:user/mylib.git -> mylib
            https://gitlab.com/user/my-lib.git -> my-lib

        Args:
            git_url: Git repository URL

        Returns:
            Derived library name
        """
        url = git_url.rstrip("/")

        # Remove .git suffix
        if url.endswith(".git"):
            url = url[:-4]

        # Handle SSH format: git@github.com:user/repo
        if ":" in url and not url.startswith("http"):
            name = url.split(":")[-1].split("/")[-1]
        else:
            # HTTPS format
            name = url.split("/")[-1]

        return name

    def add_library(
        self,
        git_url: str,
        tag: str | None = None,
        branch: str | None = None,
        commit: str | None = None,
        name: str | None = None,
    ) -> str:
        """Add a library to the manifest.

        Args:
            git_url: Git repository URL
            tag: Git tag to checkout
            branch: Git branch to checkout
            commit: Git commit to checkout
            name: Override library name (derived from URL if not provided)

        Returns:
            Library name

        Raises:
            ValueError: If library already exists or invalid arguments
        """
        # Derive name if not provided
        if not name:
            name = self.derive_name_from_url(git_url)

        # Load existing manifest
        manifest = self.load_manifest()

        # Check if library already exists
        if name in manifest.libraries:
            raise ValueError(f"Library '{name}' already exists in manifest")

        # Create library spec
        spec = LibrarySpec(git=git_url, tag=tag, branch=branch, commit=commit)

        # Add to manifest
        manifest.libraries[name] = spec
        self.save_manifest(manifest)

        logger.info(f"Added library '{name}' to manifest")
        return name

    def remove_library(self, name: str) -> None:
        """Remove a library from manifest and disk.

        Args:
            name: Library name to remove

        Raises:
            ValueError: If library doesn't exist
        """
        manifest = self.load_manifest()

        if name not in manifest.libraries:
            raise ValueError(f"Library '{name}' not found in manifest")

        # Remove from manifest
        del manifest.libraries[name]
        self.save_manifest(manifest)

        # Remove from disk if exists
        lib_dir = self.repo.libs_dir / name
        if lib_dir.exists():
            shutil.rmtree(lib_dir)
            logger.info(f"Removed library '{name}' from disk")

        logger.info(f"Removed library '{name}' from manifest")

    def update_library(self, name: str | None = None) -> list[str]:
        """Update library/libraries to latest version.

        For branches, fetches latest. For tags/commits, re-checkouts.

        Args:
            name: Specific library to update, or None for all

        Returns:
            List of updated library names
        """
        manifest = self.load_manifest()
        updated: list[str] = []

        libraries_to_update = (
            {name: manifest.libraries[name]}
            if name
            else manifest.libraries
        )

        for lib_name, spec in libraries_to_update.items():
            lib_dir = self.repo.libs_dir / lib_name
            if not lib_dir.exists():
                # Library not installed, skip
                continue

            try:
                # Fetch updates
                self._git_fetch(lib_dir)

                # Checkout version
                self._checkout_version(lib_dir, spec)

                updated.append(lib_name)
                logger.info(f"Updated library '{lib_name}'")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to update library '{lib_name}': {e}")

        return updated

    def install_all(self) -> list[ResolvedLibrary]:
        """Install all libraries from manifest.

        Returns:
            List of installed libraries
        """
        manifest = self.load_manifest()
        installed: list[ResolvedLibrary] = []

        # Ensure libs directory exists
        self.repo.libs_dir.mkdir(parents=True, exist_ok=True)

        for name, spec in manifest.libraries.items():
            try:
                lib = self._install_library(name, spec)
                installed.append(lib)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install library '{name}': {e}")
                raise LibraryError(f"Failed to install library '{name}'") from e

        return installed

    def install_library(self, name: str) -> ResolvedLibrary:
        """Install a single library.

        Args:
            name: Library name from manifest

        Returns:
            Resolved library info

        Raises:
            ValueError: If library not in manifest
        """
        manifest = self.load_manifest()

        if name not in manifest.libraries:
            raise ValueError(f"Library '{name}' not found in manifest")

        # Ensure libs directory exists
        self.repo.libs_dir.mkdir(parents=True, exist_ok=True)

        return self._install_library(name, manifest.libraries[name])

    def _install_library(self, name: str, spec: LibrarySpec) -> ResolvedLibrary:
        """Install a library from spec.

        Args:
            name: Library name
            spec: Library specification

        Returns:
            Resolved library info
        """
        lib_dir = self.repo.libs_dir / name

        # Clone if not exists
        if not lib_dir.exists():
            self._git_clone(spec.git, lib_dir)

        # Checkout version
        self._checkout_version(lib_dir, spec)

        return ResolvedLibrary(
            name=name,
            git_url=spec.git,
            version_type=spec.version_type,
            version=spec.version,
            path=lib_dir,
        )

    def _git_clone(self, url: str, target: Path) -> None:
        """Clone a git repository.

        Args:
            url: Git URL to clone
            target: Target directory
        """
        logger.info(f"Cloning {url} to {target}")
        subprocess.run(
            ["git", "clone", "--quiet", url, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )

    def _git_fetch(self, repo_dir: Path) -> None:
        """Fetch updates for a repository.

        Args:
            repo_dir: Repository directory
        """
        subprocess.run(
            ["git", "fetch", "--quiet", "--all", "--tags"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def _checkout_version(self, repo_dir: Path, spec: LibrarySpec) -> None:
        """Checkout the specified version.

        Args:
            repo_dir: Repository directory
            spec: Library specification with version info
        """
        if spec.tag is not None:
            ref = f"tags/{spec.tag}"
        elif spec.branch is not None:
            ref = f"origin/{spec.branch}"
        else:
            ref = spec.commit

        subprocess.run(
            ["git", "checkout", "--quiet", ref],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def list_libraries(self) -> dict[str, LibrarySpec]:
        """List all libraries in manifest.

        Returns:
            Dictionary of library name to spec
        """
        manifest = self.load_manifest()
        return manifest.libraries

    def get_installed_libraries(self) -> list[ResolvedLibrary]:
        """Get list of installed libraries.

        Returns:
            List of resolved libraries that are actually installed
        """
        manifest = self.load_manifest()
        installed: list[ResolvedLibrary] = []

        for name, spec in manifest.libraries.items():
            lib_dir = self.repo.libs_dir / name
            if lib_dir.exists():
                installed.append(
                    ResolvedLibrary(
                        name=name,
                        git_url=spec.git,
                        version_type=spec.version_type,
                        version=spec.version,
                        path=lib_dir,
                    )
                )

        return installed


class DependencyResolver:
    """Resolves transitive library dependencies with cycle detection."""

    def __init__(self, manager: LibraryManager) -> None:
        """Initialize with library manager.

        Args:
            manager: LibraryManager instance
        """
        self.manager = manager

    def resolve_all(self) -> list[ResolvedLibrary]:
        """Resolve all dependencies in topological order.

        Handles transitive dependencies by checking each library's
        own .asd/libraries.toml manifest.

        Returns:
            List of libraries in dependency order (dependencies first)

        Raises:
            CircularLibraryDependencyError: If circular dependencies detected
        """
        manifest = self.manager.load_manifest()
        resolved: list[ResolvedLibrary] = []
        in_progress: set[str] = set()
        completed: set[str] = set()

        for name, spec in manifest.libraries.items():
            if name not in completed:
                self._resolve_recursive(name, spec, resolved, in_progress, completed)

        return resolved

    def _resolve_recursive(
        self,
        name: str,
        spec: LibrarySpec,
        resolved: list[ResolvedLibrary],
        in_progress: set[str],
        completed: set[str],
    ) -> None:
        """Recursively resolve dependencies with cycle detection.

        Args:
            name: Library name
            spec: Library specification
            resolved: List to append resolved libraries to
            in_progress: Set of libraries currently being resolved
            completed: Set of already resolved libraries
        """
        if name in completed:
            return

        if name in in_progress:
            raise CircularLibraryDependencyError(
                f"Circular dependency detected involving library '{name}'"
            )

        in_progress.add(name)

        # Check if library is installed and has its own dependencies
        lib_dir = self.manager.repo.libs_dir / name
        lib_manifest = lib_dir / ".asd" / "libraries.toml"

        if lib_dir.exists() and lib_manifest.exists():
            # Load library's dependencies
            with open(lib_manifest, "rb") as f:
                lib_data = tomli.load(f)

            for dep_name, dep_data in lib_data.get("libraries", {}).items():
                if dep_name not in completed:
                    dep_spec = LibrarySpec(**dep_data)
                    self._resolve_recursive(
                        dep_name, dep_spec, resolved, in_progress, completed
                    )

        in_progress.remove(name)
        completed.add(name)

        # Add this library after its dependencies
        resolved.append(
            ResolvedLibrary(
                name=name,
                git_url=spec.git,
                version_type=spec.version_type,
                version=spec.version,
                path=lib_dir,
            )
        )
