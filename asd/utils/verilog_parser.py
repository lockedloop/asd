"""Verilog and SystemVerilog parser for ASD.

Extracts module interfaces, parameters, and dependencies.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set


@dataclass
class Parameter:
    """Verilog parameter definition."""

    name: str
    default: Any
    type: str = "integer"


@dataclass
class Port:
    """Module port definition."""

    name: str
    direction: str  # input, output, inout
    type: str  # logic, wire, reg
    width: Optional[str] = None


@dataclass
class Module:
    """Verilog module representation."""

    name: str
    parameters: List[Parameter] = field(default_factory=list)
    ports: List[Port] = field(default_factory=list)
    instances: List[str] = field(default_factory=list)  # Module instantiations
    packages: List[str] = field(default_factory=list)  # Package imports
    includes: List[str] = field(default_factory=list)  # Include files


class VerilogParser:
    """Parse Verilog/SystemVerilog files."""

    def __init__(self) -> None:
        """Initialize parser with regex patterns."""
        # Module declaration pattern
        self.module_pattern = re.compile(
            r"module\s+(\w+)\s*(?:#\s*\((.*?)\))?\s*\((.*?)\);", re.DOTALL
        )

        # Parameter patterns
        self.param_pattern = re.compile(r"parameter\s+(?:\w+\s+)?(\w+)\s*=\s*([^,;]+)")
        self.localparam_pattern = re.compile(r"localparam\s+(?:\w+\s+)?(\w+)\s*=\s*([^,;]+)")

        # Port patterns - more comprehensive
        self.port_pattern = re.compile(
            r"(input|output|inout)\s+(?:(logic|wire|reg)\s+)?(?:\[([^\]]+)\])?\s*(\w+)"
        )

        # Import pattern for SystemVerilog
        self.import_pattern = re.compile(r"import\s+(\w+)::\*;")

        # Include pattern
        self.include_pattern = re.compile(r'`include\s+"([^"]+)"')

        # Instance pattern - matches module instantiation
        self.instance_pattern = re.compile(
            r"(\w+)\s+(?:#\s*\(.*?\))?\s*\w+\s*\(", re.DOTALL
        )

        # Keywords to exclude from instances
        self.keywords = {
            "always",
            "always_ff",
            "always_comb",
            "always_latch",
            "initial",
            "if",
            "else",
            "for",
            "while",
            "case",
            "casex",
            "casez",
            "function",
            "task",
            "begin",
            "end",
            "generate",
            "genvar",
            "assign",
            "assert",
            "assume",
            "cover",
            "property",
            "sequence",
        }

    def parse_file(self, path: Path) -> Module:
        """Parse a single Verilog/SystemVerilog file.

        Args:
            path: Path to Verilog file

        Returns:
            Parsed module representation

        Raises:
            ValueError: If no module found in file
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
        """
        if not path.exists():
            raise FileNotFoundError(f"Verilog file not found: {path}")

        try:
            content = path.read_text()
        except PermissionError:
            raise PermissionError(f"Permission denied reading file: {path}")
        except UnicodeDecodeError:
            raise ValueError(f"File is not a text file or has encoding issues: {path}")

        # Remove comments
        content = self._remove_comments(content)

        # Find module declaration
        module_match = self.module_pattern.search(content)
        if not module_match:
            raise ValueError(f"No module found in {path}")

        module_name = module_match.group(1)
        param_block = module_match.group(2) or ""
        port_block = module_match.group(3) or ""

        # Parse parameters
        parameters = self._parse_parameters(param_block, content)

        # Parse ports
        ports = self._parse_ports(port_block, content)

        # Find package imports
        packages = self.import_pattern.findall(content)

        # Find includes
        includes = self.include_pattern.findall(content)

        # Find module instances
        instances = self._find_instances(content)

        return Module(
            name=module_name,
            parameters=parameters,
            ports=ports,
            instances=instances,
            packages=packages,
            includes=includes,
        )

    def _remove_comments(self, content: str) -> str:
        """Remove Verilog comments from content.

        Args:
            content: File content

        Returns:
            Content with comments removed
        """
        # Remove single-line comments
        content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        return content

    def _parse_parameters(self, param_block: str, full_content: str) -> List[Parameter]:
        """Parse parameter definitions.

        Args:
            param_block: Parameter block from module declaration
            full_content: Full file content for additional parameters

        Returns:
            List of parameters
        """
        parameters = []

        # Parse parameters from module declaration
        for match in self.param_pattern.finditer(param_block):
            name = match.group(1)
            default = match.group(2).strip()
            param_type = self._determine_param_type(default)
            parameters.append(Parameter(name, default, param_type))

        # Also look for localparams in the module body
        for match in self.localparam_pattern.finditer(full_content):
            name = match.group(1)
            default = match.group(2).strip()
            # Skip if already found
            if not any(p.name == name for p in parameters):
                param_type = self._determine_param_type(default)
                parameters.append(Parameter(name, default, param_type))

        return parameters

    def _determine_param_type(self, default: str) -> str:
        """Determine parameter type from default value.

        Args:
            default: Default value string

        Returns:
            Parameter type string
        """
        if default.startswith('"'):
            return "string"
        elif default in ["1'b0", "1'b1", "true", "false"]:
            return "boolean"
        elif "." in default:
            return "real"
        else:
            return "integer"

    def _parse_ports(self, port_block: str, full_content: str) -> List[Port]:
        """Parse module ports.

        Args:
            port_block: Port block from module declaration
            full_content: Full file content for detailed port info

        Returns:
            List of ports
        """
        ports = []

        # First try to parse from port block
        for match in self.port_pattern.finditer(port_block):
            direction = match.group(1)
            port_type = match.group(2) or "logic"
            width = match.group(3)
            name = match.group(4)
            ports.append(Port(name, direction, port_type, width))

        # If no ports found, try ANSI-style ports
        if not ports:
            # Look for port declarations in the module body
            # Find the module body
            module_end = full_content.find("endmodule")
            if module_end > 0:
                module_body = full_content[:module_end]
                for match in self.port_pattern.finditer(module_body):
                    direction = match.group(1)
                    port_type = match.group(2) or "logic"
                    width = match.group(3)
                    name = match.group(4)
                    # Avoid duplicates
                    if not any(p.name == name for p in ports):
                        ports.append(Port(name, direction, port_type, width))

        return ports

    def _find_instances(self, content: str) -> List[str]:
        """Find module instantiations.

        Args:
            content: File content

        Returns:
            List of instantiated module names
        """
        instances = []
        seen: Set[str] = set()

        for match in self.instance_pattern.finditer(content):
            module_name = match.group(1)

            # Skip keywords and already seen modules
            if module_name not in self.keywords and module_name not in seen:
                # Basic heuristic: if it starts with uppercase, likely a module
                # or if it contains underscore and doesn't start with $
                if (
                    module_name[0].isupper()
                    or ("_" in module_name and not module_name.startswith("$"))
                ):
                    instances.append(module_name)
                    seen.add(module_name)

        return instances

    def parse_default_value(self, value: str) -> Any:
        """Parse Verilog default value to Python.

        Args:
            value: Verilog value string

        Returns:
            Python representation of the value
        """
        value = value.strip()

        # String
        if value.startswith('"'):
            return value.strip('"')

        # Binary
        if "'b" in value:
            # Extract binary part
            parts = value.split("'b")
            if len(parts) == 2:
                return int(parts[1], 2)

        # Hexadecimal
        if "'h" in value:
            parts = value.split("'h")
            if len(parts) == 2:
                return int(parts[1], 16)

        # Decimal
        if "'d" in value:
            parts = value.split("'d")
            if len(parts) == 2:
                return int(parts[1])

        # Try direct integer conversion
        try:
            return int(value)
        except ValueError:
            pass

        # Try float conversion
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string if all else fails
        return value

    def extract_dependencies(self, path: Path) -> List[str]:
        """Extract all dependencies from a file.

        Args:
            path: Path to Verilog file

        Returns:
            List of dependency module names
        """
        try:
            module = self.parse_file(path)
            deps = []

            # Add instantiated modules
            deps.extend(module.instances)

            # Add packages (without ::*)
            for pkg in module.packages:
                if "::" in pkg:
                    deps.append(pkg.split("::")[0])
                else:
                    deps.append(pkg)

            return deps
        except Exception:
            return []