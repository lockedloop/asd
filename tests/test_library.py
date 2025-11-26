"""Unit tests for library management."""

from pathlib import Path

import pytest

from asd.core.library import (
    CircularLibraryDependencyError,
    DependencyResolver,
    LibraryManager,
    LibraryNotFoundError,
    LibraryResolver,
    ResolvedLibrary,
)
from asd.core.library_config import LibraryManifest, LibrarySpec
from asd.core.repository import Repository


class TestLibrarySpec:
    """Tests for LibrarySpec model."""

    def test_valid_tag_spec(self) -> None:
        """Test valid library spec with tag."""
        spec = LibrarySpec(git="https://github.com/user/lib.git", tag="v1.0.0")
        assert spec.version_type == "tag"
        assert spec.version == "v1.0.0"

    def test_valid_branch_spec(self) -> None:
        """Test valid library spec with branch."""
        spec = LibrarySpec(git="git@github.com:user/lib.git", branch="main")
        assert spec.version_type == "branch"
        assert spec.version == "main"

    def test_valid_commit_spec(self) -> None:
        """Test valid library spec with commit."""
        spec = LibrarySpec(git="https://github.com/user/lib.git", commit="abc123")
        assert spec.version_type == "commit"
        assert spec.version == "abc123"

    def test_missing_version_raises(self) -> None:
        """Test that missing version specifier raises error."""
        with pytest.raises(ValueError, match="One of 'tag', 'branch', or 'commit'"):
            LibrarySpec(git="https://github.com/user/lib.git")

    def test_multiple_versions_raises(self) -> None:
        """Test that multiple version specifiers raise error."""
        with pytest.raises(ValueError, match="Only one of"):
            LibrarySpec(git="https://github.com/user/lib.git", tag="v1.0", branch="main")


class TestLibraryManifest:
    """Tests for LibraryManifest model."""

    def test_empty_manifest(self) -> None:
        """Test empty manifest."""
        manifest = LibraryManifest()
        assert manifest.asd.version == "1.0"
        assert manifest.libraries == {}

    def test_manifest_with_libraries(self) -> None:
        """Test manifest with libraries."""
        manifest = LibraryManifest(
            libraries={
                "mylib": LibrarySpec(git="https://github.com/user/mylib.git", tag="v1.0"),
            }
        )
        assert "mylib" in manifest.libraries

    def test_to_toml_dict(self) -> None:
        """Test TOML serialization."""
        manifest = LibraryManifest(
            libraries={
                "mylib": LibrarySpec(git="https://github.com/user/mylib.git", tag="v1.0"),
            }
        )
        data = manifest.to_toml_dict()
        assert data["asd"]["version"] == "1.0"
        assert data["libraries"]["mylib"]["git"] == "https://github.com/user/mylib.git"
        assert data["libraries"]["mylib"]["tag"] == "v1.0"


class TestLibraryResolver:
    """Tests for LibraryResolver."""

    def test_is_library_path(self, tmp_path: Path) -> None:
        """Test library path detection."""
        repo = Repository(root=tmp_path)
        resolver = LibraryResolver(repo)

        assert resolver.is_library_path("@mylib/rtl/counter.sv")
        assert resolver.is_library_path("@lib-name/src/file.v")
        assert not resolver.is_library_path("rtl/counter.sv")
        assert not resolver.is_library_path("@nopath")

    def test_parse_library_path(self, tmp_path: Path) -> None:
        """Test library path parsing."""
        repo = Repository(root=tmp_path)
        resolver = LibraryResolver(repo)

        result = resolver.parse_library_path("@mylib/rtl/counter.sv")
        assert result == ("mylib", "rtl/counter.sv")

        result = resolver.parse_library_path("@lib-name/src/deep/file.v")
        assert result == ("lib-name", "src/deep/file.v")

        result = resolver.parse_library_path("rtl/counter.sv")
        assert result is None

    def test_get_library_name(self, tmp_path: Path) -> None:
        """Test library name extraction."""
        repo = Repository(root=tmp_path)
        resolver = LibraryResolver(repo)

        assert resolver.get_library_name("@mylib/rtl/counter.sv") == "mylib"
        assert resolver.get_library_name("rtl/counter.sv") is None

    def test_resolve_path_library_not_installed(self, tmp_path: Path) -> None:
        """Test resolving path when library not installed."""
        repo = Repository(root=tmp_path)
        resolver = LibraryResolver(repo)

        with pytest.raises(LibraryNotFoundError):
            resolver.resolve_path("@mylib/rtl/counter.sv")

    def test_resolve_path_success(self, tmp_path: Path) -> None:
        """Test successful path resolution."""
        # Setup library directory
        libs_dir = tmp_path / ".asd" / "libs"
        libs_dir.mkdir(parents=True)
        lib_dir = libs_dir / "mylib"
        lib_dir.mkdir()
        (lib_dir / "rtl").mkdir()
        (lib_dir / "rtl" / "counter.sv").touch()

        repo = Repository(root=tmp_path)
        resolver = LibraryResolver(repo)

        resolved = resolver.resolve_path("@mylib/rtl/counter.sv")
        assert resolved == lib_dir / "rtl" / "counter.sv"


class TestLibraryManager:
    """Tests for LibraryManager."""

    def test_derive_name_from_https_url(self, tmp_path: Path) -> None:
        """Test name derivation from HTTPS URL."""
        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        assert manager.derive_name_from_url("https://github.com/user/mylib.git") == "mylib"
        assert manager.derive_name_from_url("https://github.com/user/my-lib.git") == "my-lib"
        assert manager.derive_name_from_url("https://gitlab.com/user/lib/") == "lib"

    def test_derive_name_from_ssh_url(self, tmp_path: Path) -> None:
        """Test name derivation from SSH URL."""
        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        assert manager.derive_name_from_url("git@github.com:user/mylib.git") == "mylib"
        assert manager.derive_name_from_url("git@gitlab.com:user/my-lib.git") == "my-lib"

    def test_load_empty_manifest(self, tmp_path: Path) -> None:
        """Test loading when no manifest exists."""
        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        manifest = manager.load_manifest()
        assert manifest.libraries == {}

    def test_save_and_load_manifest(self, tmp_path: Path) -> None:
        """Test saving and loading manifest."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        # Create and save manifest
        manifest = LibraryManifest(
            libraries={
                "mylib": LibrarySpec(git="https://github.com/user/mylib.git", tag="v1.0"),
            }
        )
        manager.save_manifest(manifest)

        # Load and verify
        loaded = manager.load_manifest()
        assert "mylib" in loaded.libraries
        assert loaded.libraries["mylib"].tag == "v1.0"

    def test_add_library(self, tmp_path: Path) -> None:
        """Test adding a library to manifest."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        name = manager.add_library(
            git_url="https://github.com/user/counter.git",
            tag="v1.0.0",
        )

        assert name == "counter"
        manifest = manager.load_manifest()
        assert "counter" in manifest.libraries
        assert manifest.libraries["counter"].tag == "v1.0.0"

    def test_add_library_with_custom_name(self, tmp_path: Path) -> None:
        """Test adding a library with custom name."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        name = manager.add_library(
            git_url="https://github.com/user/lib.git",
            branch="main",
            name="mycustomlib",
        )

        assert name == "mycustomlib"
        manifest = manager.load_manifest()
        assert "mycustomlib" in manifest.libraries

    def test_add_duplicate_library_raises(self, tmp_path: Path) -> None:
        """Test that adding duplicate library raises error."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        manager.add_library(git_url="https://github.com/user/lib.git", tag="v1.0")

        with pytest.raises(ValueError, match="already exists"):
            manager.add_library(git_url="https://github.com/user/other.git", tag="v2.0", name="lib")

    def test_remove_library(self, tmp_path: Path) -> None:
        """Test removing a library."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()
        libs_dir = asd_dir / "libs"
        libs_dir.mkdir()
        lib_dir = libs_dir / "mylib"
        lib_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        # Add library
        manager.add_library(git_url="https://github.com/user/mylib.git", tag="v1.0")

        # Remove library
        manager.remove_library("mylib")

        manifest = manager.load_manifest()
        assert "mylib" not in manifest.libraries
        assert not lib_dir.exists()

    def test_remove_nonexistent_library_raises(self, tmp_path: Path) -> None:
        """Test removing nonexistent library raises error."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        with pytest.raises(ValueError, match="not found"):
            manager.remove_library("nonexistent")

    def test_list_libraries(self, tmp_path: Path) -> None:
        """Test listing libraries."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        manager.add_library(git_url="https://github.com/user/lib1.git", tag="v1.0")
        manager.add_library(git_url="https://github.com/user/lib2.git", branch="main")

        libraries = manager.list_libraries()
        assert len(libraries) == 2
        assert "lib1" in libraries
        assert "lib2" in libraries


class TestDependencyResolver:
    """Tests for DependencyResolver."""

    def test_resolve_empty(self, tmp_path: Path) -> None:
        """Test resolving with no libraries."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)
        resolver = DependencyResolver(manager)

        deps = resolver.resolve_all()
        assert deps == []

    def test_resolve_simple(self, tmp_path: Path) -> None:
        """Test resolving simple library list."""
        asd_dir = tmp_path / ".asd"
        asd_dir.mkdir()
        libs_dir = asd_dir / "libs"
        libs_dir.mkdir()

        # Create installed library directories
        (libs_dir / "lib1").mkdir()
        (libs_dir / "lib2").mkdir()

        repo = Repository(root=tmp_path)
        manager = LibraryManager(repo)

        manager.add_library(git_url="https://github.com/user/lib1.git", tag="v1.0")
        manager.add_library(git_url="https://github.com/user/lib2.git", tag="v2.0")

        resolver = DependencyResolver(manager)
        deps = resolver.resolve_all()

        assert len(deps) == 2
        assert {d.name for d in deps} == {"lib1", "lib2"}
