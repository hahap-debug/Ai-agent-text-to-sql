"""
Prompts Package: Master System Prompts, Tool Definitions, and Narrative Templates.
"""

import sys
import importlib
from . import templates

# Ensure submodule is always fresh during hot reloads
if "src.prompts.templates" in sys.modules:
    importlib.reload(templates)

from src.prompts.templates import (
    GEMINI_SYSTEM_PROMPT,
    NVIDIA_SYSTEM_PROMPT,
    OLLAMA_SYSTEM_PROMPT,
    MASTER_SYSTEM_PROMPT,
    DATABASE_CATALOG_PROMPT,
    SCOPE_ROUTING_PROMPT,
    TOOL_DEFINITIONS,
    NARRATIVE_SYSTEM_PROMPT,
    build_narrative_prompt,
)

__all__ = [
    "GEMINI_SYSTEM_PROMPT",
    "NVIDIA_SYSTEM_PROMPT",
    "OLLAMA_SYSTEM_PROMPT",
    "MASTER_SYSTEM_PROMPT",
    "DATABASE_CATALOG_PROMPT",
    "SCOPE_ROUTING_PROMPT",
    "TOOL_DEFINITIONS",
    "NARRATIVE_SYSTEM_PROMPT",
    "build_narrative_prompt",
]
