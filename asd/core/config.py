"""Configuration models for ASD.

Pydantic models for type-safe configuration handling.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class ParameterType(str, Enum):
    """Supported parameter types."""

    INTEGER = "integer"
    STRING = "string"
    BOOLEAN = "boolean"
    REAL = "real"


class Parameter(BaseModel):
    """Single parameter definition.

    Supports inline parameter set definitions - any extra field becomes
    a parameter set value. For example:
        default = 8
        wide = 16    # Creates/adds to parameter_sets.wide
        narrow = 4   # Creates/adds to parameter_sets.narrow
    """

    model_config = {"extra": "allow"}  # Allow extra fields for parameter sets

    default: Any
    type: Optional[ParameterType] = None  # Auto-inferred from default if not specified
    description: Optional[str] = None
    range: Optional[Tuple[int, int]] = None
    values: Optional[List[Any]] = None  # Allowed values
    expr: Optional[str] = None  # Expression for computed params
    env: Optional[str] = None  # Environment variable name

    def model_post_init(self, __context: Any) -> None:
        """Auto-infer type from default value if not specified."""
        if self.type is None:
            if isinstance(self.default, bool):
                self.type = ParameterType.BOOLEAN
            elif isinstance(self.default, int):
                self.type = ParameterType.INTEGER
            elif isinstance(self.default, float):
                self.type = ParameterType.REAL
            else:
                self.type = ParameterType.STRING

    def get_parameter_set_values(self) -> Dict[str, Any]:
        """Get all extra fields as parameter set values.

        Returns:
            Dictionary mapping parameter set name to value
        """
        # In Pydantic v2, extra fields are stored in __pydantic_extra__
        if hasattr(self, '__pydantic_extra__') and self.__pydantic_extra__:
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
    def validate_values(cls, v: Optional[List[Any]], info: Any) -> Optional[List[Any]]:
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


class ParameterSet(BaseModel):
    """Named parameter configuration."""

    name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    inherit: Optional[str] = None  # Inherit from another set
    description: Optional[str] = None


class ModuleSources(BaseModel):
    """Module source file definitions."""

    packages: List[str] = Field(default_factory=list)
    modules: List[str] = Field(default_factory=list)
    includes: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)


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

    path: Optional[str] = None
    git: Optional[str] = None
    tag: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None


class SimulatorConfig(BaseModel):
    """Simulator-specific configuration."""

    compile_args: List[str] = Field(default_factory=list)
    sim_args: List[str] = Field(default_factory=list)
    defines: Dict[str, Any] = Field(default_factory=dict)


class TestConfig(BaseModel):
    """Test configuration."""

    test_module: str
    timeout: int = 60
    parameters: Dict[str, Any] = Field(default_factory=dict)
    env: Dict[str, str] = Field(default_factory=dict)


class ToolConfig(BaseModel):
    """Tool-specific configuration."""

    parameter_set: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    defines: Dict[str, Any] = Field(default_factory=dict)


class SimulationConfig(ToolConfig):
    """Simulation tool configuration."""

    simulator: str = "verilator"
    tests: Dict[str, TestConfig] = Field(default_factory=dict)
    verilator: Optional[SimulatorConfig] = None
    modelsim: Optional[SimulatorConfig] = None


class LintConfig(ToolConfig):
    """Linting tool configuration."""

    tool: str = "verilator"
    fix: bool = False


class SynthesisConfig(ToolConfig):
    """Synthesis tool configuration."""

    tool: str = "vivado"
    part: Optional[str] = None
    strategy: Optional[str] = None


class ModuleConfig(BaseModel):
    """Complete module configuration."""

    # Module definition
    name: str
    top: str
    type: ModuleType = ModuleType.RTL
    language: Language = Language.SYSTEMVERILOG
    description: Optional[str] = None

    # Sources
    sources: ModuleSources = Field(default_factory=ModuleSources)

    # Parameters
    parameters: Dict[str, Parameter] = Field(default_factory=dict)
    parameter_sets: Dict[str, ParameterSet] = Field(default_factory=dict)

    # Dependencies
    dependencies: Dict[str, Dependency] = Field(default_factory=dict)

    # Tool configurations
    simulation: Optional[SimulationConfig] = None
    lint: Optional[LintConfig] = None
    synthesis: Optional[SynthesisConfig] = None

    def get_parameter_set(self, name: str) -> Optional[ParameterSet]:
        """Get parameter set by name.

        Args:
            name: Parameter set name

        Returns:
            Parameter set or None if not found
        """
        return self.parameter_sets.get(name)

    def get_all_sources(self) -> List[str]:
        """Get all source files.

        Returns:
            Combined list of all source files
        """
        sources = []
        sources.extend(self.sources.packages)
        sources.extend(self.sources.modules)
        return sources

    def get_includes(self) -> List[str]:
        """Get include directories.

        Returns:
            List of include directories
        """
        # Extract directories from include files
        from pathlib import Path

        dirs = set()
        for include in self.sources.includes:
            dirs.add(str(Path(include).parent))
        return list(dirs)


class ASDMetadata(BaseModel):
    """ASD file metadata."""

    version: str = "1.0"
    created_by: Optional[str] = None
    timestamp: Optional[str] = None
    generated: bool = False


class ASDConfig(BaseModel):
    """Complete ASD configuration file."""

    asd: ASDMetadata = Field(default_factory=ASDMetadata)
    module: ModuleConfig
    parameters: Dict[str, Parameter] = Field(default_factory=dict)
    parameter_sets: Dict[str, ParameterSet] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)