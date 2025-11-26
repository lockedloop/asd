"""Configuration models for ASD.

Pydantic models for type-safe configuration handling.
"""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ParameterType(str, Enum):
    """Supported parameter types."""

    INTEGER = "integer"
    STRING = "string"
    BOOLEAN = "boolean"
    REAL = "real"


def infer_parameter_type(value: Any) -> ParameterType:
    """Infer parameter type from default value using pattern matching.

    Args:
        value: Default value to infer type from

    Returns:
        Inferred ParameterType

    Examples:
        >>> infer_parameter_type(True)
        ParameterType.BOOLEAN
        >>> infer_parameter_type(42)
        ParameterType.INTEGER
        >>> infer_parameter_type(3.14)
        ParameterType.REAL
        >>> infer_parameter_type("hello")
        ParameterType.STRING
    """
    match value:
        case bool():
            return ParameterType.BOOLEAN
        case int():
            return ParameterType.INTEGER
        case float():
            return ParameterType.REAL
        case _:
            return ParameterType.STRING


class Parameter(BaseModel):
    """Single parameter definition.

    Supports inline configuration definitions - any extra field becomes
    a configuration value. For example:
        default = 8
        wide = 16    # Creates/adds to configurations.wide
        narrow = 4   # Creates/adds to configurations.narrow
    """

    model_config = {"extra": "allow"}  # Allow extra fields for configurations

    default: Any = None  # Optional - can be set by named configurations instead
    type: ParameterType | None = None  # Auto-inferred from default if not specified
    description: str | None = None
    range: tuple[int, int] | None = None
    values: list[Any] | None = None  # Allowed values
    expr: str | None = None  # Expression for computed params
    env: str | None = None  # Environment variable name

    def model_post_init(self, __context: Any) -> None:
        """Auto-infer type from default value if not specified."""
        if self.type is None:
            self.type = infer_parameter_type(self.default)

    def get_configuration_values(self) -> dict[str, Any]:
        """Get all extra fields as configuration values.

        Returns:
            Dictionary mapping configuration name to value
        """
        # In Pydantic v2, extra fields are stored in __pydantic_extra__
        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            return dict(self.__pydantic_extra__)
        return {}

    @field_validator("default")
    @classmethod
    def validate_default(cls, v: Any, info: Any) -> Any:
        """Ensure default value matches type."""
        if "type" not in info.data or info.data["type"] is None:
            return v

        param_type = info.data["type"]
        if param_type == ParameterType.INTEGER:
            return int(v)
        elif param_type == ParameterType.BOOLEAN:
            return bool(v)
        elif param_type == ParameterType.REAL:
            return float(v)
        return v

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: list[Any] | None, info: Any) -> list[Any] | None:
        """Validate allowed values match parameter type."""
        if v is None:
            return v

        param_type = info.data.get("type")
        if param_type is None:
            return v

        if param_type == ParameterType.INTEGER:
            return [int(x) for x in v]
        elif param_type == ParameterType.BOOLEAN:
            return [bool(x) for x in v]
        elif param_type == ParameterType.REAL:
            return [float(x) for x in v]
        return v


class Define(BaseModel):
    """Define definition with inline configuration support.

    Supports inline configuration definitions - any extra field becomes
    a configuration value. For example:
        default = false
        wide = true    # Creates/adds to configurations.wide
        debug = true   # Creates/adds to configurations.debug
    """

    model_config = {"extra": "allow"}  # Allow extra fields for configurations

    default: Any
    type: ParameterType | None = None  # Auto-inferred from default if not specified
    description: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Auto-infer type from default value if not specified."""
        if self.type is None:
            self.type = infer_parameter_type(self.default)

    def get_configuration_values(self) -> dict[str, Any]:
        """Get all extra fields as configuration values.

        Returns:
            Dictionary mapping configuration name to value
        """
        # In Pydantic v2, extra fields are stored in __pydantic_extra__
        if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__:
            return dict(self.__pydantic_extra__)
        return {}


class Configuration(BaseModel):
    """Named configuration with parameter and define overrides."""

    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    defines: dict[str, Any] = Field(default_factory=dict)
    inherit: str | None = None  # Inherit from another configuration
    description: str | None = None


class ModuleSources(BaseModel):
    """Module source file definitions."""

    packages: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class ModuleType(str, Enum):
    """Module type classification."""

    RTL = "rtl"
    TESTBENCH = "testbench"
    IP = "ip"
    PRIMITIVE = "primitive"


class Language(str, Enum):
    """Supported HDL languages."""

    VERILOG = "verilog"
    SYSTEMVERILOG = "systemverilog"
    VHDL = "vhdl"


class Dependency(BaseModel):
    """Module dependency specification."""

    path: str | None = None
    git: str | None = None
    tag: str | None = None
    branch: str | None = None
    commit: str | None = None


class SimulatorConfig(BaseModel):
    """Simulator-specific configuration."""

    compile_args: list[str] = Field(default_factory=list)
    sim_args: list[str] = Field(default_factory=list)
    defines: dict[str, Any] = Field(default_factory=dict)


class TestConfig(BaseModel):
    """Test configuration."""

    test_module: str
    timeout: int = 60
    parameters: dict[str, Any] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)


class ToolConfig(BaseModel):
    """Tool-specific configuration."""

    configurations: list[str] | None = None  # List of configuration names to use
    parameters: dict[str, Any] = Field(default_factory=dict)
    defines: dict[str, Any] = Field(default_factory=dict)


class SimulationConfig(ToolConfig):
    """Simulation tool configuration.

    Note: Simulator is specified via CLI --simulator flag, not in TOML.
    """

    tests: dict[str, TestConfig] = Field(default_factory=dict)
    vars: dict[str, Any] = Field(default_factory=dict)
    verilator: SimulatorConfig | None = None
    modelsim: SimulatorConfig | None = None


class LintConfig(ToolConfig):
    """Linting tool configuration."""

    tool: str = "verilator"
    fix: bool = False


class SynthesisConfig(ToolConfig):
    """Synthesis tool configuration."""

    tool: str = "vivado"
    part: str | None = None
    strategy: str | None = None


class ModuleConfig(BaseModel):
    """Complete module configuration."""

    # Module definition
    name: str
    top: str
    type: ModuleType = ModuleType.RTL
    description: str | None = None
    default_configuration: str | None = None  # Alias for "default" config

    # Sources
    sources: ModuleSources = Field(default_factory=ModuleSources)

    # Parameters and Defines
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    defines: dict[str, Define] = Field(default_factory=dict)
    configurations: dict[str, Configuration] = Field(default_factory=dict)

    # Dependencies
    dependencies: dict[str, Dependency] = Field(default_factory=dict)

    # Tool configurations
    simulation: SimulationConfig | None = None
    lint: LintConfig | None = None
    synthesis: SynthesisConfig | None = None

    def get_configuration(self, name: str) -> Configuration | None:
        """Get configuration by name.

        Args:
            name: Configuration name

        Returns:
            Configuration or None if not found
        """
        return self.configurations.get(name)

    def get_all_sources(self) -> list[str]:
        """Get all source files.

        Returns:
            Combined list of all source files
        """
        sources = []
        sources.extend(self.sources.packages)
        sources.extend(self.sources.modules)
        return sources

    def get_includes(self) -> list[str]:
        """Get include directories.

        Returns:
            List of include directories
        """
        # Extract directories from include files

        dirs = set()
        for include in self.sources.includes:
            dirs.add(str(Path(include).parent))
        return list(dirs)


class ASDMetadata(BaseModel):
    """ASD file metadata."""

    version: str = "1.0"
    created_by: str | None = None
    timestamp: str | None = None
    generated: bool = False


class ASDConfig(BaseModel):
    """Complete ASD configuration file."""

    asd: ASDMetadata = Field(default_factory=ASDMetadata)
    module: ModuleConfig
    parameters: dict[str, Parameter] = Field(default_factory=dict)
    defines: dict[str, Define] = Field(default_factory=dict)
    configurations: dict[str, Configuration] = Field(default_factory=dict)
    tools: dict[str, Any] = Field(default_factory=dict)
