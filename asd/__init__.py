"""ASD - Automated System Design.

A TOML-based build system for HDL projects.
"""

__version__ = "0.1.0"
__author__ = "ASD Team"

from .core.repository import Repository
from .core.config import ModuleConfig, Parameter, ParameterSet

__all__ = ["Repository", "ModuleConfig", "Parameter", "ParameterSet"]