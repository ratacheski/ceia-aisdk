"""Public registry API for resolving and caching cataloged model aliases.

This module is the programmatic surface for later inference features. It is
not imported by ``ceia_aisdk.__init__``, so ``import ceia_aisdk`` does not
load PyYAML or ``httpx``.
"""

from __future__ import annotations

from ceia_aisdk.registry.cache import ensure_local
from ceia_aisdk.registry.catalog import (
    PublicModelMetadata,
    ResolvedAlias,
    get_public_metadata,
    resolve,
)

__all__ = [
    "PublicModelMetadata",
    "ResolvedAlias",
    "ensure_local",
    "get_public_metadata",
    "resolve",
]
