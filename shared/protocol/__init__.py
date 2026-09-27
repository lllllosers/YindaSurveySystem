"""Pure protocol and identity rules shared by every Yinda client.

Modules in this package must stay independent from PySide6, FastAPI and any
database implementation. Desktop and Web adapters may import this package;
the package must never import those adapters in return.
"""

from .constants import (
    CURRENT_TASK_SCHEMA_VERSION,
    LEGACY_TASK_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    SUPPORTED_RESULT_SCHEMA_VERSIONS,
    SUPPORTED_TASK_SCHEMA_VERSIONS,
    SURVEY_RESULT_EXTENSION,
    SURVEY_RESULT_PACKAGE_KIND,
    SURVEY_TASK_EXTENSION,
    SURVEY_TASK_PACKAGE_KIND,
)

__all__ = [
    "CURRENT_TASK_SCHEMA_VERSION",
    "LEGACY_TASK_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "SUPPORTED_RESULT_SCHEMA_VERSIONS",
    "SUPPORTED_TASK_SCHEMA_VERSIONS",
    "SURVEY_RESULT_EXTENSION",
    "SURVEY_RESULT_PACKAGE_KIND",
    "SURVEY_TASK_EXTENSION",
    "SURVEY_TASK_PACKAGE_KIND",
]
