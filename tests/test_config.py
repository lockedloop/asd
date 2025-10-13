"""Unit tests for configuration models."""

import pytest
from pydantic import ValidationError

from asd.core.config import (
    Language,
    ModuleConfig,
    ModuleSources,
    ModuleType,
    Parameter,
    ParameterSet,
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
    param = Parameter(
        default=8, type=ParameterType.INTEGER, values=[4, 8, 16, 32]
    )
    assert 8 in param.values


def test_parameter_set():
    """Test parameter set model."""
    pset = ParameterSet(
        name="test",
        parameters={"WIDTH": 16, "DEPTH": 32},
        inherit="default",
        description="Test configuration",
    )

    assert pset.name == "test"
    assert pset.parameters["WIDTH"] == 16
    assert pset.inherit == "default"


def test_module_config():
    """Test module configuration model."""
    config = ModuleConfig(
        name="uart",
        top="uart_top",
        type=ModuleType.RTL,
        language=Language.SYSTEMVERILOG,
        sources=ModuleSources(
            modules=["src/uart.sv"],
            packages=["src/uart_pkg.sv"],
        ),
        parameters={
            "WIDTH": Parameter(default=8, type=ParameterType.INTEGER),
        },
        parameter_sets={
            "default": ParameterSet(name="default", parameters={}),
            "test": ParameterSet(name="test", parameters={"WIDTH": 4}),
        },
    )

    assert config.name == "uart"
    assert config.top == "uart_top"
    assert config.type == ModuleType.RTL
    assert len(config.sources.modules) == 1
    assert len(config.parameters) == 1
    assert len(config.parameter_sets) == 2


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


def test_get_parameter_set():
    """Test getting parameter set by name."""
    config = ModuleConfig(
        name="test",
        top="test_top",
        parameter_sets={
            "default": ParameterSet(name="default"),
            "test": ParameterSet(name="test", parameters={"WIDTH": 4}),
        },
    )

    pset = config.get_parameter_set("test")
    assert pset is not None
    assert pset.parameters["WIDTH"] == 4

    pset = config.get_parameter_set("nonexistent")
    assert pset is None