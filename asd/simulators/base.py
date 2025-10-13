"""Base simulator interface for ASD."""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class SimulatorBase(ABC):
    """Abstract base class for simulator interfaces."""

    def __init__(self, name: str, build_dir: Optional[Path] = None) -> None:
        """Initialize simulator with name and build directory.

        Args:
            name: Simulator name
            build_dir: Build directory path (defaults to build/<name>)
        """
        self.name = name
        self.build_dir = build_dir or Path("build") / name
        self.build_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def compile(
        self,
        sources: List[Path],
        parameters: Dict[str, Any],
        defines: Dict[str, Any],
        **kwargs: Any,
    ) -> int:
        """Compile HDL sources.

        Args:
            sources: List of source file paths
            parameters: Module parameters
            defines: Preprocessor defines
            **kwargs: Additional simulator-specific options

        Returns:
            Return code (0 for success)
        """
        pass

    @abstractmethod
    def elaborate(
        self, top_module: str, parameters: Dict[str, Any], **kwargs: Any
    ) -> int:
        """Elaborate design.

        Args:
            top_module: Top module name
            parameters: Module parameters
            **kwargs: Additional simulator-specific options

        Returns:
            Return code (0 for success)
        """
        pass

    @abstractmethod
    def simulate(
        self,
        top_module: str,
        test_module: Optional[str] = None,
        **kwargs: Any,
    ) -> int:
        """Run simulation.

        Args:
            top_module: Top module name
            test_module: Test module for cocotb (optional)
            **kwargs: Additional simulator-specific options

        Returns:
            Return code (0 for success)
        """
        pass

    def clean(self) -> None:
        """Clean build artifacts."""
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)

    def get_build_path(self, filename: str) -> Path:
        """Get path for build artifact.

        Args:
            filename: Artifact filename

        Returns:
            Full path in build directory
        """
        return self.build_dir / filename

    def is_available(self) -> bool:
        """Check if simulator is available on system.

        Returns:
            True if simulator can be used
        """
        import shutil

        # Override in subclasses for specific checks
        return True