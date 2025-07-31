"""Hypha Artifact fsspec interface."""

from .hypha_artifact import HyphaArtifact
from .async_hypha_artifact_compat import AsyncHyphaArtifact

__all__ = ["HyphaArtifact", "AsyncHyphaArtifact"]
