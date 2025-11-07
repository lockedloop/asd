"""Unit tests for configuration models."""

from asd.core.config import (
    Configuration,
    ModuleConfig,
    ModuleSources,
    ModuleType,
    Parameter,
    ParameterType,
)


def test_parameter_validation():
    """Test parameter model validation."""
    # Integer parameter
    param = Parameter(default=10, type=ParameterType.INTEGER)
    assert param.default == 10
    assert param.type == ParameterType.INTEGER

    # String parameter
    param = Parameter(default="test", type=ParameterType.STRING)
    assert param.default == "test"

    # Boolean parameter
    param = Parameter(default=True, type=ParameterType.BOOLEAN)
    assert param.default is True

    # With range
    param = Parameter(default=5, type=ParameterType.INTEGER, range=(1, 10))
    assert param.range == (1, 10)

    # With allowed values
    param = Parameter(default=8, type=ParameterType.INTEGER, values=[4, 8, 16, 32])
    assert 8 in param.values


def test_configuration():
    """Test configuration model."""
    config = Configuration(
        name="test",
        parameters={"WIDTH": 16, "DEPTH": 32},
        defines={},
        inherit="default",
        description="Test configuration",
    )

    assert config.name == "test"
    assert config.parameters["WIDTH"] == 16
    assert config.inherit == "default"


def test_module_config():
    """Test module configuration model."""
    config = ModuleConfig(
        name="uart",
        top="uart_top",
        type=ModuleType.RTL,
        sources=ModuleSources(
            modules=["src/uart.sv"],
            packages=["src/uart_pkg.sv"],
        ),
        parameters={
            "WIDTH": Parameter(default=8, type=ParameterType.INTEGER),
        },
        configurations={
            "default": Configuration(name="default", parameters={}, defines={}),
            "test": Configuration(name="test", parameters={"WIDTH": 4}, defines={}),
        },
    )

    assert config.name == "uart"
    assert config.top == "uart_top"
    assert config.type == ModuleType.RTL
    assert len(config.sources.modules) == 1
    assert len(config.parameters) == 1
    assert len(config.configurations) == 2


def test_get_all_sources():
    """Test getting all source files."""
    config = ModuleConfig(
        name="test",
        top="test_top",
        sources=ModuleSources(
            packages=["pkg1.sv", "pkg2.sv"],
            modules=["mod1.sv", "mod2.sv", "mod3.sv"],
        ),
    )

    sources = config.get_all_sources()
    assert len(sources) == 5
    assert "pkg1.sv" in sources
    assert "mod3.sv" in sources


def test_get_configuration():
    """Test getting configuration by name."""
    config = ModuleConfig(
        name="test",
        top="test_top",
        configurations={
            "default": Configuration(name="default", parameters={}, defines={}),
            "test": Configuration(name="test", parameters={"WIDTH": 4}, defines={}),
        },
    )

    cfg = config.get_configuration("test")
    assert cfg is not None
    assert cfg.parameters["WIDTH"] == 4

    cfg = config.get_configuration("nonexistent")
    assert cfg is None
