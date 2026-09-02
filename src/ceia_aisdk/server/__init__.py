"""OpenAI-compatible local HTTP server for the CEIA AI SDK.

Importing this package requires the ``[server]`` extra (FastAPI and uvicorn).
``import ceia_aisdk`` must not import this module.
"""

from __future__ import annotations

from ceia_aisdk.server.app import create_app

__all__ = ["create_app"]
