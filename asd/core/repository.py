"""Repository management for ASD.

Handles repository root detection and path resolution.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional


class Repository:
    """Manages repository root detection and path resolution."""

    def __init__(self, root: Optional[Path] = None) -> None:
        """Initialize repository with optional explicit root.

        Args:
            root: Explicit repository root path. If None, will auto-detect.
        """
        self.root = self._find_root(root)
        self._cache: Dict[str, Path] = {}

    def _find_root(self, explicit_root: Optional[Path] = None) -> Path:
        """Find repository root using .asd-root marker.

        Strategy order:
        1. Explicit root parameter (--root flag)
        2. Environment variable ASD_ROOT
        3. Search upwards for .asd-root marker file

        Args:
            explicit_root: Explicitly provided root path

        Returns:
            Resolved repository root path

        Raises:
            FileNotFoundError: If .asd-root marker is not found

        Note:
            The .asd-root file is created by 'asd init' and is the
            authoritative marker for ASD repositories. Run 'asd init'
            in your project root to initialize.
        """
        if explicit_root:
            if not explicit_root.exists():
                raise FileNotFoundError(f"Specified root does not exist: {explicit_root}")
            return explicit_root.resolve()

        # Check environment variable
        if env_root := os.getenv("ASD_ROOT"):
            env_path = Path(env_root)
            if not env_path.exists():
                raise FileNotFoundError(f"ASD_ROOT path does not exist: {env_root}")
            return env_path.resolve()

        # Search upwards for .asd-root marker
        current = Path.cwd()
        while current != current.parent:
            if (current / ".asd-root").exists():
                return current
            current = current.parent

        # No .asd-root found - fail with helpful error
        raise FileNotFoundError(
            "ASD repository not initialized. No .asd-root marker found.\n"
            "Run 'asd init' in your project root to initialize the repository."
        )

    def resolve_path(self, path: str | Path) -> Path:
        """Convert relative path to absolute based on repo root.

        Args:
            path: Path to resolve (string or Path object)

        Returns:
            Absolute resolved path
        """
        path = Path(path)
        if path.is_absolute():
            return path
        return (self.root / path).resolve()

    def relative_path(self, path: Path) -> Path:
        """Convert absolute path to repo-relative.

        Args:
            path: Absolute path to convert

        Returns:
            Repository-relative path, or original if outside repo
        """
        try:
            return path.relative_to(self.root)
        except ValueError:
            # Path is outside repository
            return path

    def find_files(self, pattern: str, directory: Optional[Path] = None) -> List[Path]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "**/*.sv")
            directory: Directory to search in (defaults to repo root)

        Returns:
            List of matching file paths
        """
        search_dir = self.resolve_path(directory) if directory else self.root
        return sorted(search_dir.glob(pattern))

    def exists(self, path: str | Path) -> bool:
        """Check if a path exists relative to repository root.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        return self.resolve_path(path).exists()

    def is_file(self, path: str | Path) -> bool:
        """Check if path is a file.

        Args:
            path: Path to check

        Returns:
            True if path is a file
        """
        resolved = self.resolve_path(path)
        return resolved.exists() and resolved.is_file()

    def is_dir(self, path: str | Path) -> bool:
        """Check if path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory
        """
        resolved = self.resolve_path(path)
        return resolved.exists() and resolved.is_dir()

    def __str__(self) -> str:
        """String representation of repository."""
        return f"Repository(root={self.root})"

    def __repr__(self) -> str:
        """Developer representation of repository."""
        return f"Repository(root={self.root!r})"