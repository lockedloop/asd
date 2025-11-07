"""TOML loader with composition support.

Handles loading, inheritance, and parameter composition.
"""

from pathlib import Path
from typing import Any

import tomli
import tomli_w

from ..utils.expression import SafeExpressionEvaluator
from ..utils.validation import ParameterValidator
from .config import (
    Configuration,
    Define,
    Dependency,
    LintConfig,
    ModuleConfig,
    ModuleSources,
    ModuleType,
    Parameter,
    SimulationConfig,
    SynthesisConfig,
    TestConfig,
    ToolConfig,
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
        configuration_name: str | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compose final parameters and defines for a tool configuration.

        Args:
            config: Module configuration
            tool_name: Tool to compose for (simulation, lint, synthesis)
            configuration_name: Specific configuration to use
            cli_overrides: Command-line parameter overrides

        Returns:
            Dict with 'parameters', 'defines', and 'tool_config'
        """
        cli_overrides = cli_overrides or {}

        # 1. Start with parameter and define defaults
        params = {name: p.default for name, p in config.parameters.items()}
        defines = {name: d.default for name, d in config.defines.items()}

        # 2. Get tool configuration
        tool_config: ToolConfig | None = None
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
                "defines": defines,
                "tool_config": {},
            }

        # 3. Apply configuration if specified
        if configuration_name and configuration_name != "default":
            configuration = config.configurations.get(configuration_name)
            if configuration:
                params, defines = self._apply_configuration(
                    params, defines, configuration, config.configurations
                )

        # 4. Apply tool-specific overrides
        if tool_config.parameters:
            params.update(tool_config.parameters)
        if tool_config.defines:
            defines.update(tool_config.defines)

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

        return {
            "parameters": params,
            "defines": defines,
            "tool_config": tool_config.model_dump() if tool_config else {},
        }

    def _apply_configuration(
        self,
        base_params: dict[str, Any],
        base_defines: dict[str, Any],
        configuration: Configuration,
        all_configs: dict[str, Configuration],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Apply configuration with inheritance.

        Args:
            base_params: Base parameters to start with
            base_defines: Base defines to start with
            configuration: Configuration to apply
            all_configs: All available configurations

        Returns:
            Tuple of (updated parameters, updated defines)
        """
        params = base_params.copy()
        defines = base_defines.copy()

        # Handle inheritance
        if configuration.inherit and configuration.inherit in all_configs:
            parent = all_configs[configuration.inherit]
            params, defines = self._apply_configuration(params, defines, parent, all_configs)

        # Apply this configuration's parameters and defines
        params.update(configuration.parameters)
        defines.update(configuration.defines)

        return params, defines

    def _evaluate_all_expressions(
        self, params: dict[str, Any], definitions: dict[str, Parameter]
    ) -> dict[str, Any]:
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
        self._cache: dict[Path, ModuleConfig] = {}
        self._loading_stack: list[Path] = []
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

    def _compose_config(self, data: dict[str, Any], base_path: Path) -> ModuleConfig:
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

        # Process parameters and defines
        parameters = self._process_parameters(data.get("parameters", {}))
        defines = self._process_defines(data.get("defines", {}))

        # Extract inline configurations from both parameters and defines
        inline_configs = self._extract_inline_configurations(parameters, defines)

        # Process explicit configurations with inheritance
        explicit_configs = self._process_configurations(data.get("configurations", {}))

        # Merge inline and explicit configurations (explicit wins on conflict)
        configurations = self._merge_configurations(inline_configs, explicit_configs)

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
            description=module_data.get("description"),
            sources=sources,
            parameters=parameters,
            defines=defines,
            configurations=configurations,
            dependencies=dependencies,
            simulation=simulation,
            lint=lint,
            synthesis=synthesis,
        )

        return config

    def _process_parameters(self, params_data: dict[str, Any]) -> dict[str, Parameter]:
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

    def _process_defines(self, defines_data: dict[str, Any]) -> dict[str, Define]:
        """Process define definitions.

        Args:
            defines_data: Raw define data

        Returns:
            Processed defines
        """
        defines = {}
        for name, define_data in defines_data.items():
            if isinstance(define_data, dict):
                defines[name] = Define(**define_data)
            else:
                # Simple value
                defines[name] = Define(default=define_data)
        return defines

    def _extract_inline_configurations(
        self, parameters: dict[str, Parameter], defines: dict[str, Define]
    ) -> dict[str, Configuration]:
        """Extract configurations from inline parameter and define definitions.

        Args:
            parameters: Processed parameters with potential inline config values
            defines: Processed defines with potential inline config values

        Returns:
            Dictionary of configurations extracted from inline values
        """
        # Collect all configuration names from both parameters and defines
        config_names: set[str] = set()
        for param in parameters.values():
            config_names.update(param.get_configuration_values().keys())
        for define in defines.values():
            config_names.update(define.get_configuration_values().keys())

        # Build configurations
        configurations = {}
        for config_name in config_names:
            config_params = {}
            config_defines = {}

            # Extract parameter values for this configuration
            for param_name, param in parameters.items():
                param_values = param.get_configuration_values()
                if config_name in param_values:
                    config_params[param_name] = param_values[config_name]

            # Extract define values for this configuration
            for define_name, define in defines.items():
                define_values = define.get_configuration_values()
                if config_name in define_values:
                    config_defines[define_name] = define_values[config_name]

            configurations[config_name] = Configuration(
                name=config_name,
                parameters=config_params,
                defines=config_defines,
                description="Auto-generated from inline definitions",
            )

        return configurations

    def _merge_configurations(
        self, inline: dict[str, Configuration], explicit: dict[str, Configuration]
    ) -> dict[str, Configuration]:
        """Merge inline and explicit configurations.

        Args:
            inline: Configurations extracted from inline definitions
            explicit: Explicitly defined configurations

        Returns:
            Merged configurations (explicit wins on conflict)
        """
        # Start with inline configurations
        merged = inline.copy()

        # Merge explicit configurations (they take precedence)
        for name, explicit_config in explicit.items():
            if name in merged:
                # Merge parameters and defines: explicit wins
                inline_params = merged[name].parameters.copy()
                inline_params.update(explicit_config.parameters)
                inline_defines = merged[name].defines.copy()
                inline_defines.update(explicit_config.defines)

                merged[name] = Configuration(
                    name=name,
                    parameters=inline_params,
                    defines=inline_defines,
                    inherit=explicit_config.inherit,  # Use explicit inherit
                    description=explicit_config.description or merged[name].description,
                )
            else:
                merged[name] = explicit_config

        return merged

    def _process_configurations(self, configs_data: dict[str, Any]) -> dict[str, Configuration]:
        """Process configuration definitions.

        Args:
            configs_data: Raw configuration data

        Returns:
            Processed configurations
        """
        configurations = {}
        for name, config_data in configs_data.items():
            if isinstance(config_data, dict):
                configurations[name] = Configuration(
                    name=name,
                    parameters=config_data.get("parameters", {}),
                    defines=config_data.get("defines", {}),
                    inherit=config_data.get("inherit"),
                    description=config_data.get("description"),
                )
            else:
                # Empty configuration
                configurations[name] = Configuration(name=name)
        return configurations

    def _process_dependencies(self, deps_data: dict[str, Any]) -> dict[str, Dependency]:
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

    def _process_simulation_config(self, sim_data: dict[str, Any]) -> SimulationConfig | None:
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
            tests_data = sim_data["tests"]
            if isinstance(tests_data, dict):
                # Dict format: {"test_name": {test_module: "...", ...}}
                for test_name, test_data in tests_data.items():
                    tests[test_name] = TestConfig(**test_data)
            elif isinstance(tests_data, list):
                # List format: ["path/to/test.py", ...]
                # Auto-generate test names from file paths
                for test_path in tests_data:
                    test_name = Path(test_path).stem  # Use filename without extension
                    tests[test_name] = TestConfig(test_module=test_path)

        return SimulationConfig(
            configurations=sim_data.get("configurations"),
            parameters=sim_data.get("parameters", {}),
            defines=sim_data.get("defines", {}),
            tests=tests,
        )

    def _process_lint_config(self, lint_data: dict[str, Any]) -> LintConfig | None:
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
            configurations=lint_data.get("configurations"),
            parameters=lint_data.get("parameters", {}),
            defines=lint_data.get("defines", {}),
            fix=lint_data.get("fix", False),
        )

    def _process_synthesis_config(self, synth_data: dict[str, Any]) -> SynthesisConfig | None:
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
            configurations=synth_data.get("configurations"),
            parameters=synth_data.get("parameters", {}),
            defines=synth_data.get("defines", {}),
            part=synth_data.get("part"),
            strategy=synth_data.get("strategy"),
        )

    def evaluate_expression(self, expr: str, context: dict[str, Any]) -> Any:
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

        # Add defines
        if config.defines:
            data["defines"] = {
                name: define.model_dump(exclude_none=True)
                for name, define in config.defines.items()
            }

        # Add configurations
        if config.configurations:
            data["configurations"] = {
                name: cfg.model_dump(exclude={"name"}, exclude_none=True)
                for name, cfg in config.configurations.items()
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
