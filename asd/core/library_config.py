"""Pydantic models for library configuration.

Models for library manifest and specifications.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class LibrarySpec(BaseModel):
    """Library specification in libraries.toml.

    Represents a single library dependency with its git URL and version.
    Exactly one of tag, branch, or commit must be specified.

    Example:
        [libraries.mylib]
        git = "https://github.com/user/mylib.git"
        tag = "v1.0.0"
    """

    git: str
    tag: str | None = None
    branch: str | None = None
    commit: str | None = None

    @model_validator(mode="after")
    def validate_version_specifier(self) -> "LibrarySpec":
        """Validate that exactly one version specifier is set."""
        versions = [self.tag, self.branch, self.commit]
        count = sum(1 for v in versions if v is not None)
        if count == 0:
            raise ValueError("One of 'tag', 'branch', or 'commit' must be specified for library")
        if count > 1:
            raise ValueError("Only one of 'tag', 'branch', or 'commit' can be specified")
        return self

    @property
    def version_type(self) -> str:
        """Get the type of version specifier used.

        Returns:
            One of 'tag', 'branch', or 'commit'
        """
        if self.tag is not None:
            return "tag"
        if self.branch is not None:
            return "branch"
        return "commit"

    @property
    def version(self) -> str:
        """Get the version value.

        Returns:
            The tag, branch, or commit value
        """
        if self.tag is not None:
            return self.tag
        if self.branch is not None:
            return self.branch
        if self.commit is not None:
            return self.commit
        raise ValueError("No version specifier set")


class ASDManifestMeta(BaseModel):
    """ASD manifest metadata section."""

    version: str = "1.0"


class LibraryManifest(BaseModel):
    """Complete libraries.toml structure.

    Example:
        [asd]
        version = "1.0"

        [libraries.mylib]
        git = "https://github.com/user/mylib.git"
        tag = "v1.0.0"

        [libraries.otherlib]
        git = "git@github.com:user/otherlib.git"
        branch = "main"
    """

    asd: ASDManifestMeta = Field(default_factory=ASDManifestMeta)
    libraries: dict[str, LibrarySpec] = Field(default_factory=dict)

    def to_toml_dict(self) -> dict[str, Any]:
        """Convert to TOML-serializable dictionary.

        Returns:
            Dictionary suitable for tomli_w.dump()
        """
        result: dict[str, Any] = {
            "asd": {"version": self.asd.version},
            "libraries": {},
        }

        for name, spec in self.libraries.items():
            lib_dict: dict[str, str] = {"git": spec.git}
            if spec.tag is not None:
                lib_dict["tag"] = spec.tag
            elif spec.branch is not None:
                lib_dict["branch"] = spec.branch
            elif spec.commit is not None:
                lib_dict["commit"] = spec.commit
            result["libraries"][name] = lib_dict

        return result
