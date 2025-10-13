"""TOML loader with composition support.

Handles loading, inheritance, and parameter composition.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import tomli
import tomli_w

from ..utils.expression import SafeExpressionEvaluator
from ..utils.validation import ParameterValidator
from .config import (
    ASDConfig,
    ASDMetadata,
    Dependency,
    LintConfig,
    ModuleConfig,
    ModuleSources,
    ModuleType,
    Parameter,
    ParameterSet,
    SimulationConfig,
    SynthesisConfig,
    TestConfig,
)
from .repository import Repository


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""

    pass


class ConfigComposer:
    """Compose final configuration for a specific tool."""

    def __init__(self, loader: "TOMLLoader") -> None:
        """Initialize composer with loader reference.

        Args:
            loader: TOMLLoader instance for expression evaluation
        """
        self.loader = loader
        self.param_validator = ParameterValidator()

    def compose(
        self,
        config: ModuleConfig,
        tool_name: str,
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compose final parameters for a tool.

        Args:
            config: Module configuration
            tool_name: Tool to compose for (simulation, lint, synthesis)
            cli_overrides: Command-line parameter overrides

        Returns:
            Dict with 'parameters', 'defines', and 'tool_config'
        """
        cli_overrides = cli_overrides or {}

        # 1. Start with parameter defaults
        params = {name: p.default for name, p in config.parameters.items()}

        # 2. Get tool configuration
        tool_config = None
        if tool_name == "simulation" and config.simulation:
            tool_config = config.simulation
        elif tool_name == "lint" and config.lint:
            tool_config = config.lint
        elif tool_name == "synthesis" and config.synthesis:
            tool_config = config.synthesis

        if not tool_config:
            # Return defaults if no tool config
            return {
                "parameters": params,
                "defines": {},
                "tool_config": {},
            }

        # 3. Apply parameter set if specified
        if tool_config.parameter_set:
            param_set = config.parameter_sets.get(tool_config.parameter_set)
            if param_set:
                params = self._apply_parameter_set(params, param_set, config.parameter_sets)

        # 4. Apply tool-specific overrides
        if tool_config.parameters:
            params.update(tool_config.parameters)

        # 5. Apply CLI overrides
        params.update(cli_overrides)

        # 6. Evaluate expressions
        params = self._evaluate_all_expressions(params, config.parameters)

        # 7. Validate parameters
        validation_errors = self.param_validator.validate(params, config.parameters)
        if validation_errors:
            print("Warning: Parameter validation errors:")
            for error in validation_errors:
                print(f"  - {error}")

        # 8. Get defines
        defines = tool_config.defines if tool_config else {}

        return {
            "parameters": params,
            "defines": defines,
            "tool_config": tool_config.model_dump() if tool_config else {},
        }

    def _apply_parameter_set(
        self,
        base_params: Dict[str, Any],
        param_set: ParameterSet,
        all_sets: Dict[str, ParameterSet],
    ) -> Dict[str, Any]:
        """Apply parameter set with inheritance.

        Args:
            base_params: Base parameters to start with
            param_set: Parameter set to apply
            all_sets: All available parameter sets

        Returns:
            Updated parameters
        """
        result = base_params.copy()

        # Handle inheritance
        if param_set.inherit and param_set.inherit in all_sets:
            parent = all_sets[param_set.inherit]
            result = self._apply_parameter_set(result, parent, all_sets)

        # Apply this set's parameters
        result.update(param_set.parameters)

        return result

    def _evaluate_all_expressions(
        self, params: Dict[str, Any], definitions: Dict[str, Parameter]
    ) -> Dict[str, Any]:
        """Evaluate all parameter expressions.

        Args:
            params: Current parameter values
            definitions: Parameter definitions with expressions

        Returns:
            Parameters with expressions evaluated
        """
        result = params.copy()

        # Find parameters with expressions
        for name, definition in definitions.items():
            if definition.expr and name in result:
                try:
                    result[name] = self.loader.evaluate_expression(definition.expr, result)
                except Exception as e:
                    print(f"Warning: Failed to evaluate expression for {name}: {e}")

        return result


class TOMLLoader:
    """Load and compose TOML configurations."""

    def __init__(self, repository: Repository) -> None:
        """Initialize loader with repository.

        Args:
            repository: Repository instance for path resolution
        """
        self.repo = repository
        self._cache: Dict[Path, ModuleConfig] = {}
        self._loading_stack: List[Path] = []
        self.composer = ConfigComposer(self)

    def load(self, path: Path | str) -> ModuleConfig:
        """Load TOML with full composition.

        Args:
            path: Path to TOML file

        Returns:
            Composed module configuration

        Raises:
            CircularDependencyError: If circular dependencies detected
        """
        path = self.repo.resolve_path(path)

        # Check cache
        if path in self._cache:
            return self._cache[path]

        # Check circular dependencies
        if path in self._loading_stack:
            cycle_path = " -> ".join(str(p) for p in self._loading_stack + [path])
            raise CircularDependencyError(f"Circular dependency: {cycle_path}")

        self._loading_stack.append(path)
        try:
            with open(path, "rb") as f:
                data = tomli.load(f)

            config = self._compose_config(data, path)
            self._cache[path] = config
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"TOML file not found: {path}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading TOML file: {path}")
        except tomli.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML syntax in {path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading TOML file {path}: {e}")
        finally:
            self._loading_stack.pop()

    def _compose_config(self, data: Dict[str, Any], base_path: Path) -> ModuleConfig:
        """Compose configuration with inheritance and overlays.

        Args:
            data: Raw TOML data
            base_path: Path to TOML file for relative resolution

        Returns:
            Composed module configuration
        """
        # Extract module section
        module_data = data.get("module", {})

        # Build sources
        sources_data = module_data.get("sources", {})
        sources = ModuleSources(
            packages=sources_data.get("packages", []),
            modules=sources_data.get("modules", []),
            includes=sources_data.get("includes", []),
            resources=sources_data.get("resources", []),
        )

        # Process parameters
        parameters = self._process_parameters(data.get("parameters", {}))

        # Extract inline parameter sets from parameters
        inline_param_sets = self._extract_inline_parameter_sets(parameters)

        # Process explicit parameter sets with inheritance
        explicit_param_sets = self._process_parameter_sets(data.get("parameter_sets", {}))

        # Merge inline and explicit parameter sets (explicit wins on conflict)
        param_sets = self._merge_parameter_sets(inline_param_sets, explicit_param_sets)

        # Process dependencies
        dependencies = self._process_dependencies(module_data.get("dependencies", {}))

        # Process tool configurations
        tools = data.get("tools", {})
        simulation = self._process_simulation_config(tools.get("simulation", {}))
        lint = self._process_lint_config(tools.get("lint", {}))
        synthesis = self._process_synthesis_config(tools.get("synthesis", {}))

        # Build module config
        config = ModuleConfig(
            name=module_data.get("name", "unknown"),
            top=module_data.get("top", "top"),
            type=ModuleType(module_data.get("type", "rtl")),
            language=module_data.get("language", "systemverilog"),
            description=module_data.get("description"),
            sources=sources,
            parameters=parameters,
            parameter_sets=param_sets,
            dependencies=dependencies,
            simulation=simulation,
            lint=lint,
            synthesis=synthesis,
        )

        return config

    def _process_parameters(self, params_data: Dict[str, Any]) -> Dict[str, Parameter]:
        """Process parameter definitions.

        Args:
            params_data: Raw parameter data

        Returns:
            Processed parameters
        """
        parameters = {}
        for name, param_data in params_data.items():
            if isinstance(param_data, dict):
                parameters[name] = Parameter(**param_data)
            else:
                # Simple value, assume integer parameter
                parameters[name] = Parameter(default=param_data)
        return parameters

    def _extract_inline_parameter_sets(
        self, parameters: Dict[str, Parameter]
    ) -> Dict[str, ParameterSet]:
        """Extract parameter sets from inline parameter definitions.

        Args:
            parameters: Processed parameters with potential inline set values

        Returns:
            Dictionary of parameter sets extracted from inline values
        """
        # Collect all parameter set names
        param_set_names: Set[str] = set()
        for param in parameters.values():
            param_set_names.update(param.get_parameter_set_values().keys())

        # Build parameter sets
        param_sets = {}
        for set_name in param_set_names:
            set_params = {}
            for param_name, param in parameters.items():
                set_values = param.get_parameter_set_values()
                if set_name in set_values:
                    set_params[param_name] = set_values[set_name]

            param_sets[set_name] = ParameterSet(
                name=set_name,
                parameters=set_params,
                description=f"Auto-generated from inline parameter definitions",
            )

        return param_sets

    def _merge_parameter_sets(
        self, inline: Dict[str, ParameterSet], explicit: Dict[str, ParameterSet]
    ) -> Dict[str, ParameterSet]:
        """Merge inline and explicit parameter sets.

        Args:
            inline: Parameter sets extracted from inline definitions
            explicit: Explicitly defined parameter sets

        Returns:
            Merged parameter sets (explicit wins on conflict)
        """
        # Start with inline sets
        merged = inline.copy()

        # Merge explicit sets (they take precedence)
        for name, explicit_set in explicit.items():
            if name in merged:
                # Merge parameters: explicit wins
                inline_params = merged[name].parameters.copy()
                inline_params.update(explicit_set.parameters)

                merged[name] = ParameterSet(
                    name=name,
                    parameters=inline_params,
                    inherit=explicit_set.inherit,  # Use explicit inherit
                    description=explicit_set.description or merged[name].description,
                )
            else:
                merged[name] = explicit_set

        return merged

    def _process_parameter_sets(self, sets_data: Dict[str, Any]) -> Dict[str, ParameterSet]:
        """Process parameter set definitions.

        Args:
            sets_data: Raw parameter sets data

        Returns:
            Processed parameter sets
        """
        param_sets = {}
        for name, set_data in sets_data.items():
            if isinstance(set_data, dict):
                param_sets[name] = ParameterSet(
                    name=name,
                    parameters=set_data.get("parameters", set_data),
                    inherit=set_data.get("inherit"),
                    description=set_data.get("description"),
                )
            else:
                param_sets[name] = ParameterSet(name=name)
        return param_sets

    def _process_dependencies(self, deps_data: Dict[str, Any]) -> Dict[str, Dependency]:
        """Process module dependencies.

        Args:
            deps_data: Raw dependencies data

        Returns:
            Processed dependencies
        """
        dependencies = {}
        for name, dep_data in deps_data.items():
            if isinstance(dep_data, dict):
                dependencies[name] = Dependency(**dep_data)
            else:
                dependencies[name] = Dependency(path=str(dep_data))
        return dependencies

    def _process_simulation_config(self, sim_data: Dict[str, Any]) -> Optional[SimulationConfig]:
        """Process simulation configuration.

        Args:
            sim_data: Raw simulation config data

        Returns:
            Simulation configuration or None
        """
        if not sim_data:
            return None

        # Process tests
        tests = {}
        if "tests" in sim_data:
            for test_name, test_data in sim_data["tests"].items():
                tests[test_name] = TestConfig(**test_data)

        return SimulationConfig(
            simulator=sim_data.get("simulator", "verilator"),
            parameter_set=sim_data.get("parameter_set"),
            parameters=sim_data.get("parameters", {}),
            defines=sim_data.get("defines", {}),
            tests=tests,
        )

    def _process_lint_config(self, lint_data: Dict[str, Any]) -> Optional[LintConfig]:
        """Process lint configuration.

        Args:
            lint_data: Raw lint config data

        Returns:
            Lint configuration or None
        """
        if not lint_data:
            return None

        return LintConfig(
            tool=lint_data.get("tool", "verilator"),
            parameter_set=lint_data.get("parameter_set"),
            parameters=lint_data.get("parameters", {}),
            defines=lint_data.get("defines", {}),
            fix=lint_data.get("fix", False),
        )

    def _process_synthesis_config(self, synth_data: Dict[str, Any]) -> Optional[SynthesisConfig]:
        """Process synthesis configuration.

        Args:
            synth_data: Raw synthesis config data

        Returns:
            Synthesis configuration or None
        """
        if not synth_data:
            return None

        return SynthesisConfig(
            tool=synth_data.get("tool", "vivado"),
            parameter_set=synth_data.get("parameter_set"),
            parameters=synth_data.get("parameters", {}),
            defines=synth_data.get("defines", {}),
            part=synth_data.get("part"),
            strategy=synth_data.get("strategy"),
        )

    def evaluate_expression(self, expr: str, context: Dict[str, Any]) -> Any:
        """Evaluate parameter expressions safely.

        Args:
            expr: Expression to evaluate
            context: Context with parameter values

        Returns:
            Evaluated expression result
        """
        evaluator = SafeExpressionEvaluator(context)
        return evaluator.evaluate(expr)

    def save(self, config: ModuleConfig, path: Path | str) -> None:
        """Save configuration to TOML file.

        Args:
            config: Module configuration to save
            path: Output file path
        """
        path = self.repo.resolve_path(path)

        # Convert to dict for TOML serialization
        data = {
            "asd": {"version": "1.0", "generated": True},
            "module": {
                "name": config.name,
                "top": config.top,
                "type": config.type.value,
                "language": config.language.value,
                "sources": {
                    "packages": config.sources.packages,
                    "modules": config.sources.modules,
                    "includes": config.sources.includes,
                    "resources": config.sources.resources,
                },
            },
        }

        # Add parameters
        if config.parameters:
            data["parameters"] = {
                name: param.model_dump(exclude_none=True)
                for name, param in config.parameters.items()
            }

        # Add parameter sets
        if config.parameter_sets:
            data["parameter_sets"] = {
                name: pset.model_dump(exclude={"name"}, exclude_none=True)
                for name, pset in config.parameter_sets.items()
            }

        # Add tool configurations
        tools = {}
        if config.simulation:
            tools["simulation"] = config.simulation.model_dump(exclude_none=True)
        if config.lint:
            tools["lint"] = config.lint.model_dump(exclude_none=True)
        if config.synthesis:
            tools["synthesis"] = config.synthesis.model_dump(exclude_none=True)

        if tools:
            data["tools"] = tools

        # Write TOML file
        with open(path, "wb") as f:
            tomli_w.dump(data, f)