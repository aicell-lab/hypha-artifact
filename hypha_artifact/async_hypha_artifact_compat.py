"""Serves as a backward-compatibility layer for the AsyncHyphaArtifact class.

The AsyncHyphaArtifact class has been refactored into a module.
This file imports the class from the new module to ensure that existing code
that imports from this file continues to work.
"""

from .async_hypha_artifact import AsyncHyphaArtifact

__all__ = ["AsyncHyphaArtifact"]
