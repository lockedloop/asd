"""Validation utilities for ASD.

Provides parameter and configuration validation.
"""

from typing import Any, Dict, List, Optional

from ..core.config import Parameter, ParameterType


class ParameterValidator:
    """Validate parameter values against their definitions."""

    def validate(
        self, parameters: Dict[str, Any], definitions: Dict[str, Parameter]
    ) -> List[str]:
        """Validate parameter values against definitions.

        Args:
            parameters: Parameter values to validate
            definitions: Parameter definitions with constraints

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors = []

        for name, value in parameters.items():
            # Check if parameter is defined
            if name not in definitions:
                # Warning only - unknown parameters are allowed
                continue

            definition = definitions[name]

            # Validate type
            type_error = self._validate_type(name, value, definition.type)
            if type_error:
                errors.append(type_error)
                continue  # Skip further validation if type is wrong

            # Validate range
            if definition.range:
                range_error = self._validate_range(name, value, definition.range)
                if range_error:
                    errors.append(range_error)

            # Validate allowed values
            if definition.values:
                values_error = self._validate_values(name, value, definition.values)
                if values_error:
                    errors.append(values_error)

        return errors

    def _validate_type(
        self, name: str, value: Any, expected_type: ParameterType
    ) -> Optional[str]:
        """Validate parameter type.

        Args:
            name: Parameter name
            value: Parameter value
            expected_type: Expected parameter type

        Returns:
            Error message or None if valid
        """
        if expected_type == ParameterType.INTEGER:
            if not isinstance(value, int) and not isinstance(value, bool):
                try:
                    int(value)
                except (ValueError, TypeError):
                    return f"Parameter '{name}' must be an integer, got {type(value).__name__}"

        elif expected_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                if value not in [0, 1, "true", "false", "True", "False"]:
                    return f"Parameter '{name}' must be a boolean, got {value}"

        elif expected_type == ParameterType.REAL:
            if not isinstance(value, (int, float)):
                try:
                    float(value)
                except (ValueError, TypeError):
                    return f"Parameter '{name}' must be a number, got {type(value).__name__}"

        elif expected_type == ParameterType.STRING:
            if not isinstance(value, str):
                return f"Parameter '{name}' must be a string, got {type(value).__name__}"

        return None

    def _validate_range(
        self, name: str, value: Any, value_range: tuple
    ) -> Optional[str]:
        """Validate parameter is within range.

        Args:
            name: Parameter name
            value: Parameter value
            value_range: (min, max) tuple

        Returns:
            Error message or None if valid
        """
        if len(value_range) != 2:
            return None  # Invalid range definition, skip

        min_val, max_val = value_range

        # Convert to numeric for comparison
        try:
            numeric_value = float(value) if isinstance(value, (int, float)) else float(value)
        except (ValueError, TypeError):
            return None  # Can't validate range for non-numeric

        if numeric_value < min_val or numeric_value > max_val:
            return f"Parameter '{name}' value {value} is outside range [{min_val}, {max_val}]"

        return None

    def _validate_values(
        self, name: str, value: Any, allowed_values: List[Any]
    ) -> Optional[str]:
        """Validate parameter is in allowed values list.

        Args:
            name: Parameter name
            value: Parameter value
            allowed_values: List of allowed values

        Returns:
            Error message or None if valid
        """
        if value not in allowed_values:
            # Format allowed values nicely
            if len(allowed_values) <= 5:
                values_str = ", ".join(str(v) for v in allowed_values)
            else:
                first_three = ", ".join(str(v) for v in allowed_values[:3])
                values_str = f"{first_three}, ... ({len(allowed_values)} values)"

            return f"Parameter '{name}' value {value} not in allowed values: {values_str}"

        return None


class ConfigValidator:
    """Validate module configuration."""

    def __init__(self):
        """Initialize configuration validator."""
        self.param_validator = ParameterValidator()

    def validate_config(self, config: Any) -> List[str]:
        """Validate a module configuration.

        Args:
            config: ModuleConfig object to validate

        Returns:
            List of validation error messages
        """
        errors = []

        # Check required fields
        if not config.name:
            errors.append("Module name is required")

        if not config.top:
            errors.append("Top module name is required")

        # Check for at least one source file
        if not config.sources.modules and not config.sources.packages:
            errors.append("At least one source file is required")

        # Validate parameter sets
        for set_name, param_set in config.parameter_sets.items():
            # Check inheritance
            if param_set.inherit and param_set.inherit not in config.parameter_sets:
                errors.append(
                    f"Parameter set '{set_name}' inherits from unknown set '{param_set.inherit}'"
                )

            # Validate parameter values in set
            set_errors = self.param_validator.validate(
                param_set.parameters, config.parameters
            )
            for error in set_errors:
                errors.append(f"In parameter set '{set_name}': {error}")

        # Validate tool configurations
        if config.simulation and config.simulation.parameter_set:
            if config.simulation.parameter_set not in config.parameter_sets:
                errors.append(
                    f"Simulation uses unknown parameter set '{config.simulation.parameter_set}'"
                )

        if config.lint and config.lint.parameter_set:
            if config.lint.parameter_set not in config.parameter_sets:
                errors.append(f"Lint uses unknown parameter set '{config.lint.parameter_set}'")

        if config.synthesis and config.synthesis.parameter_set:
            if config.synthesis.parameter_set not in config.parameter_sets:
                errors.append(
                    f"Synthesis uses unknown parameter set '{config.synthesis.parameter_set}'"
                )

        return errors


def validate_parameters(
    parameters: Dict[str, Any], definitions: Dict[str, Parameter]
) -> List[str]:
    """Convenience function to validate parameters.

    Args:
        parameters: Parameter values
        definitions: Parameter definitions

    Returns:
        List of error messages
    """
    validator = ParameterValidator()
    return validator.validate(parameters, definitions)