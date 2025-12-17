"""TOML loader with composition support.

Handles loading, inheritance, and parameter composition.
"""

from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import ValidationError

from ..utils.expression import SafeExpressionEvaluator
from ..utils.logging import get_logger
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

logger = get_logger()


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

        # 3. Apply configuration if specified (even without tool_config)
        if configuration_name and configuration_name != "default":
            configuration = config.configurations.get(configuration_name)
            if configuration:
                params, defines = self._apply_configuration(
                    params, defines, configuration, config.configurations
                )

        # 4. Apply tool-specific overrides (if tool config exists)
        if tool_config:
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
            logger.warning("Parameter validation errors:")
            for error in validation_errors:
                logger.warning(f"  - {error}")

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
                    logger.warning(f"Failed to evaluate expression for {name}: {e}")

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
        except FileNotFoundError as e:
            raise FileNotFoundError(f"TOML file not found: {path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied reading TOML file: {path}") from e
        except tomli.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML syntax in {path}: {e}") from e
        except OSError as e:
            raise RuntimeError(f"Error loading TOML file {path}: {e}") from e
        finally:
            self._loading_stack.pop()

    def _compose_config(self, data: dict[str, Any], base_path: Path) -> ModuleConfig:
        """Compose configuration with inheritance and overlays.

        Args:
            data: Raw TOML data
            base_path: Path to TOML file for relative resolution

        Returns:
            Composed module configuration

        Raises:
            ValueError: If required fields are missing
        """
        # Validate schema - check for required fields
        self._validate_schema(data, base_path)

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

        # Extract and validate default_configuration
        default_configuration = module_data.get("default_configuration")
        if default_configuration and default_configuration not in configurations:
            available = ", ".join(sorted(configurations.keys()))
            raise ValueError(
                f"default_configuration '{default_configuration}' not found. "
                f"Available configurations: {available}"
            )

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
            default_configuration=default_configuration,
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

    def _validate_schema(self, data: dict[str, Any], base_path: Path) -> None:
        """Validate TOML schema has required fields.

        Args:
            data: Raw TOML data
            base_path: Path to TOML file for error messages

        Raises:
            ValueError: If required fields are missing
        """
        errors: list[str] = []

        # Check for [module] section
        if "module" not in data:
            # Check for common wrong keys to give helpful hints
            wrong_keys = {"project", "rtl", "design"}
            found_wrong = wrong_keys.intersection(data.keys())
            if found_wrong:
                errors.append(
                    f"Missing required [module] section. "
                    f"Found [{', '.join(found_wrong)}] instead - "
                    f"did you mean [module]?"
                )
            else:
                errors.append("Missing required [module] section")

        module_data = data.get("module", {})

        # Check for required module fields
        if "name" not in module_data:
            errors.append("Missing required field: module.name")

        if "top" not in module_data:
            errors.append("Missing required field: module.top")

        # Check for sources
        sources_data = module_data.get("sources", {})
        if not sources_data:
            # Check for common wrong keys
            if "rtl" in data and "files" in data.get("rtl", {}):
                errors.append(
                    "Missing [module.sources] section. "
                    "Found [rtl].files instead - use [module.sources].modules"
                )
            else:
                errors.append("Missing [module.sources] section")
        else:
            has_sources = sources_data.get("modules") or sources_data.get("packages")
            if not has_sources:
                errors.append(
                    "No source files defined. "
                    "Add files to [module.sources].modules or [module.sources].packages"
                )

        if errors:
            file_name = base_path.name
            error_msg = f"Invalid TOML schema in {file_name}:\n  - " + "\n  - ".join(errors)
            raise ValueError(error_msg)

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

        Always ensures a "default" configuration exists, even if no inline
        configuration values are specified. This allows users to always run
        with the default configuration.

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

        # Always ensure "default" configuration exists
        if config_names and "default" not in config_names:
            config_names.add("default")

        # If no inline configs at all, create just "default"
        if not config_names:
            config_names.add("default")

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
            Simulation configuration or None (only None if sim_data is None)

        Raises:
            ValueError: If configuration is invalid
        """
        if sim_data is None:
            return None

        try:
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
                vars=sim_data.get("vars", {}),
            )
        except ValidationError as e:
            errors = [f"  - {err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise ValueError(
                "Invalid [tools.simulation] configuration:\n" + "\n".join(errors)
            ) from None

    def _process_lint_config(self, lint_data: dict[str, Any]) -> LintConfig | None:
        """Process lint configuration.

        Args:
            lint_data: Raw lint config data

        Returns:
            Lint configuration or None (only None if lint_data is None)

        Raises:
            ValueError: If configuration is invalid
        """
        if lint_data is None:
            return None

        try:
            # Empty dict {} should return default LintConfig (allows [tools.lint] with no options)
            return LintConfig(
                tool=lint_data.get("tool", "verilator"),
                configurations=lint_data.get("configurations"),
                parameters=lint_data.get("parameters", {}),
                defines=lint_data.get("defines", {}),
                fix=lint_data.get("fix", False),
            )
        except ValidationError as e:
            errors = [f"  - {err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise ValueError("Invalid [tools.lint] configuration:\n" + "\n".join(errors)) from None

    def _process_synthesis_config(self, synth_data: dict[str, Any]) -> SynthesisConfig | None:
        """Process synthesis configuration.

        Args:
            synth_data: Raw synthesis config data

        Returns:
            Synthesis configuration or None (only None if synth_data is None)

        Raises:
            ValueError: If configuration is invalid
        """
        if synth_data is None:
            return None

        try:
            return SynthesisConfig(
                tool=synth_data.get("tool", "vivado"),
                configurations=synth_data.get("configurations"),
                parameters=synth_data.get("parameters", {}),
                defines=synth_data.get("defines", {}),
                part=synth_data.get("part"),
                strategy=synth_data.get("strategy"),
            )
        except ValidationError as e:
            errors = [f"  - {err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise ValueError(
                "Invalid [tools.synthesis] configuration:\n" + "\n".join(errors)
            ) from None

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
