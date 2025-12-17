"""ASD - Automated System Design.

A TOML-based build system for HDL projects.
"""

__version__ = "0.2.1"
__author__ = "Danilo Sijacic"

from .core.config import Configuration, Define, ModuleConfig, Parameter
from .core.repository import Repository

__all__ = ["Repository", "ModuleConfig", "Parameter", "Configuration", "Define"]
