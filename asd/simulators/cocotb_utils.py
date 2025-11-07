"""Cocotb utilities for accessing ASD configuration in tests.

These utilities help test files access parameters, defines, and configuration
information passed from the ASD runner through environment variables.
"""

import json
import os
from typing import Any


def get_test_arg(name: str, default: Any = None) -> Any:
    """Get test argument from environment variables.

    Arguments are JSON-encoded and passed via COCOTB_TEST_VAR_<NAME> environment
    variables by the ASD runner.

    Args:
        name: Argument name
        default: Default value if not found

    Returns:
        Decoded argument value or default
    """
    env_name = f"COCOTB_TEST_VAR_{name.upper()}"
    value_str = os.environ.get(env_name)

    if value_str is None:
        return default

    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        # If not valid JSON, return as string
        return value_str


def get_parameters() -> dict[str, Any]:
    """Get all module parameters for this test run.

    Returns:
        Dictionary of parameter name to value
    """
    result = get_test_arg("PARAMETERS", {})
    return result if isinstance(result, dict) else {}


def get_defines() -> dict[str, Any]:
    """Get all preprocessor defines for this test run.

    Returns:
        Dictionary of define name to value
    """
    result = get_test_arg("DEFINES", {})
    return result if isinstance(result, dict) else {}


def get_config_name() -> str:
    """Get the configuration name being used.

    Returns:
        Configuration name (e.g., "default", "wide", etc.)
    """
    result = get_test_arg("CONFIG_NAME", "default")
    return str(result)


def log_config() -> None:
    """Print configuration information for debugging.

    Prints the current configuration name, parameters, defines, and seed.
    The seed is accessed via cocotb.RANDOM_SEED which is automatically
    set by cocotb from the COCOTB_RANDOM_SEED environment variable.
    """
    import cocotb

    config_name = get_config_name()
    parameters = get_parameters()
    defines = get_defines()

    cocotb.log.info("=" * 60)
    cocotb.log.info(f"ASD Configuration: {config_name}")
    cocotb.log.info("=" * 60)

    # Access cocotb's native random seed
    seed = cocotb.RANDOM_SEED
    cocotb.log.info(f"Random Seed: 0x{seed:08X} ({seed})")

    if parameters:
        cocotb.log.info("Parameters:")
        for name, value in parameters.items():
            cocotb.log.info(f"  {name} = {value}")

    if defines:
        cocotb.log.info("Defines:")
        for name, value in defines.items():
            cocotb.log.info(f"  {name} = {value}")

    cocotb.log.info("=" * 60)
