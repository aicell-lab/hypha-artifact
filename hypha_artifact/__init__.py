"""Hypha Artifact fsspec interface."""

from .async_hypha_artifact_compat import AsyncHyphaArtifact
from .hypha_artifact import HyphaArtifact

__all__ = ["AsyncHyphaArtifact", "HyphaArtifact"]
