"""Shared configuration validation logic for tools (simulation, lint, synthesis)."""

from typing import Protocol

from ..core.config import ModuleConfig


class ToolConfig(Protocol):
    """Protocol for tool configurations with configurations list."""

    configurations: list[str] | None


def validate_tool_configuration(
    config: ModuleConfig,
    requested_config: str,
    tool_config: ToolConfig | None,
    tool_name: str,
) -> tuple[bool, str]:
    """Validate that requested configuration is allowed by tool configuration.

    This function centralizes the validation logic used by all tools (simulation,
    lint, synthesis) to check if a requested configuration is supported.

    Args:
        config: Module configuration
        requested_config: Configuration name requested via CLI
        tool_config: Tool-specific configuration (simulation/lint/synthesis)
        tool_name: Name of the tool for error messages

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty string.

    Examples:
        >>> # Check if "fast" config is valid for simulation
        >>> is_valid, error = validate_tool_configuration(
        ...     config=module_config,
        ...     requested_config="fast",
        ...     tool_config=module_config.simulation,
        ...     tool_name="simulation"
        ... )
    """
    # Check if configuration exists in module
    if requested_config != "all" and requested_config not in config.configurations:
        return (
            False,
            f"Configuration '{requested_config}' not found. "
            f"Available: {', '.join(config.configurations.keys())}",
        )

    # If no tool config, allow all configurations
    if not tool_config:
        return (True, "")

    # If tool.configurations is None or empty, allow all
    if not tool_config.configurations:
        return (True, "")

    # If tool.configurations contains "all", allow any configuration
    if "all" in tool_config.configurations:
        return (True, "")

    # Otherwise, requested config must be in the allowed list
    if requested_config == "all":
        # "all" means run all configurations that the tool supports
        # This is always valid - expansion will use tool's config list
        return (True, "")
    else:
        # Single config must be in allowed list
        if requested_config not in tool_config.configurations:
            return (
                False,
                f"Configuration '{requested_config}' not supported by {tool_name} tool. "
                f"Tool supports: {', '.join(tool_config.configurations)}",
            )
        return (True, "")
