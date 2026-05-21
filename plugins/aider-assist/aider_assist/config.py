from __future__ import annotations

import os

SAFE_MODEL_ENV = {
    "AIDER_MODEL": "main_model",
    "AIDER_WEAK_MODEL": "weak_model",
    "AIDER_EDITOR_MODEL": "editor_model",
    "AIDER_REASONING_EFFORT": "reasoning_effort",
    "AIDER_EDIT_FORMAT": "edit_format",
}

SAFE_PROVIDER_ENV = {
    "OPENAI_API_BASE": "openai_api_base",
    "ANTHROPIC_API_BASE": "anthropic_api_base",
    "AIDER_PROVIDER": "provider",
}

SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def safe_model_metadata() -> dict[str, str]:
    """Return bounded non-secret Aider/provider metadata for provenance.

    API key, token, password, and secret values are intentionally excluded even
    if present in the process environment.
    """

    metadata: dict[str, str] = {}
    for env_name, output_name in SAFE_MODEL_ENV.items():
        value = os.environ.get(env_name)
        if value:
            metadata[output_name] = value
    for env_name, output_name in SAFE_PROVIDER_ENV.items():
        if any(marker in env_name for marker in SECRET_MARKERS):
            continue
        value = os.environ.get(env_name)
        if value:
            metadata[output_name] = value
    return metadata
