"""Unit tests for Repository class."""

from pathlib import Path

from asd.core.repository import Repository


def test_find_root_with_marker(tmp_path):
    """Test repository root detection with .asd-root marker."""
    marker = tmp_path / ".asd-root"
    marker.touch()

    repo = Repository(root=tmp_path)
    assert repo.root == tmp_path


def test_find_root_with_explicit_path(tmp_path):
    """Test repository with explicit root path."""
    repo = Repository(root=tmp_path)
    assert repo.root == tmp_path


def test_find_root_with_env_var(tmp_path, monkeypatch):
    """Test repository root detection from environment variable."""
    monkeypatch.setenv("ASD_ROOT", str(tmp_path))
    repo = Repository()
    assert repo.root == tmp_path


def test_resolve_path(tmp_path):
    """Test path resolution."""
    repo = Repository(root=tmp_path)

    # Relative path
    resolved = repo.resolve_path("src/module.sv")
    assert resolved == tmp_path / "src/module.sv"

    # Absolute path
    resolved = repo.resolve_path("/abs/path.sv")
    assert resolved == Path("/abs/path.sv")


def test_relative_path(tmp_path):
    """Test converting absolute to relative path."""
    repo = Repository(root=tmp_path)

    # Path inside repository
    relative = repo.relative_path(tmp_path / "src/module.sv")
    assert relative == Path("src/module.sv")

    # Path outside repository
    relative = repo.relative_path(Path("/other/path.sv"))
    assert relative == Path("/other/path.sv")


def test_exists(tmp_path):
    """Test path existence checking."""
    repo = Repository(root=tmp_path)

    # Create a file
    test_file = tmp_path / "test.sv"
    test_file.touch()

    assert repo.exists("test.sv")
    assert not repo.exists("nonexistent.sv")


def test_is_file_and_is_dir(tmp_path):
    """Test file and directory checking."""
    repo = Repository(root=tmp_path)

    # Create file and directory
    test_file = tmp_path / "test.sv"
    test_file.touch()
    test_dir = tmp_path / "src"
    test_dir.mkdir()

    assert repo.is_file("test.sv")
    assert not repo.is_file("src")
    assert repo.is_dir("src")
    assert not repo.is_dir("test.sv")


def test_find_files(tmp_path):
    """Test file pattern matching."""
    repo = Repository(root=tmp_path)

    # Create test files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "module1.sv").touch()
    (src_dir / "module2.sv").touch()
    (src_dir / "package.sv").touch()
    (tmp_path / "top.sv").touch()

    # Find all .sv files
    sv_files = repo.find_files("**/*.sv")
    assert len(sv_files) == 4

    # Find files in src directory
    src_files = repo.find_files("*.sv", src_dir)
    assert len(src_files) == 3
