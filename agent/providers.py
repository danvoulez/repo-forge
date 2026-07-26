#!/usr/bin/env python3
"""Provider registry for repo-forge.

The Claude Agent SDK stays the execution engine — only *where the model API
calls go* changes. Every provider resolves to environment variables that the
SDK / Claude Code CLI already understands:

- ``anthropic`` : first-party Anthropic API (default; historical behaviour)
- ``bedrock``   : Amazon Bedrock    (``CLAUDE_CODE_USE_BEDROCK=1``)
- ``vertex``    : Google Vertex AI  (``CLAUDE_CODE_USE_VERTEX=1``)
- ``gateway``   : any Anthropic-compatible endpoint via ``ANTHROPIC_BASE_URL``
                  (LiteLLM, OpenRouter, Kimi/GLM/DeepSeek proxies, self-hosted …)

This module deliberately has **no SDK imports** so preflight tooling
(``doctor.sh``) can use it too:

    python agent/providers.py --check     # exit 0 if the configured provider is usable
    python agent/providers.py --list      # show known providers
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


class ProviderError(RuntimeError):
    """Raised when the provider configuration is invalid or incomplete."""


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of a provider family."""

    description: str
    # Each inner tuple is a group: at least one variable of the group must be
    # present (in the process env, or set by config/env_set) for the provider
    # to be considered usable.
    required_any: tuple[tuple[str, ...], ...] = ()
    env_set: Mapping[str, str] = field(default_factory=dict)
    doctor_hint: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        description="First-party Anthropic API",
        required_any=(("ANTHROPIC_API_KEY",),),
        doctor_hint="export ANTHROPIC_API_KEY=sk-ant-...",
    ),
    "bedrock": ProviderSpec(
        description="Amazon Bedrock",
        env_set={"CLAUDE_CODE_USE_BEDROCK": "1"},
        required_any=(
            ("AWS_BEARER_TOKEN_BEDROCK", "AWS_PROFILE", "AWS_ACCESS_KEY_ID"),
        ),
        doctor_hint=(
            "configure AWS credentials (AWS_PROFILE, or "
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or AWS_BEARER_TOKEN_BEDROCK)"
        ),
    ),
    "vertex": ProviderSpec(
        description="Google Vertex AI",
        env_set={"CLAUDE_CODE_USE_VERTEX": "1"},
        required_any=(
            ("ANTHROPIC_VERTEX_PROJECT_ID",),
            ("CLOUD_ML_REGION",),
        ),
        doctor_hint=(
            "export ANTHROPIC_VERTEX_PROJECT_ID and CLOUD_ML_REGION "
            "(plus GOOGLE_APPLICATION_CREDENTIALS or gcloud auth)"
        ),
    ),
    "gateway": ProviderSpec(
        description=(
            "Any Anthropic-compatible gateway (LiteLLM, OpenRouter, Kimi, GLM, "
            "self-hosted proxy, …) via ANTHROPIC_BASE_URL"
        ),
        # base_url may come from config, so it is validated in resolve_provider.
        required_any=(),
        doctor_hint=(
            "set provider.base_url in agent/config.yaml or export ANTHROPIC_BASE_URL"
        ),
    ),
}

# Config keys (under `provider:` in config.yaml) mapped onto SDK env vars.
_CONFIG_ENV_MAP = {
    "model": "ANTHROPIC_MODEL",
    "small_fast_model": "ANTHROPIC_SMALL_FAST_MODEL",
    "base_url": "ANTHROPIC_BASE_URL",
}

_KNOWN_CONFIG_KEYS = frozenset(
    {"name", "api_key_env", "extra_env", *_CONFIG_ENV_MAP}
)


@dataclass(frozen=True)
class ResolvedProvider:
    name: str
    description: str
    env: Mapping[str, str]  # variables the caller must apply via os.environ.update
    model: str | None


def resolve_provider(cfg: Mapping | None, env: Mapping[str, str]) -> ResolvedProvider:
    """Validate provider config against the environment and return env to apply.

    ``cfg`` is the ``provider:`` section of agent/config.yaml (may be empty —
    defaults to first-party Anthropic, which is the historical behaviour).
    Raises ProviderError with an actionable message on any problem.
    """
    cfg = dict(cfg or {})
    name = str(cfg.get("name") or "anthropic").strip().lower()

    if name not in PROVIDERS:
        valid = ", ".join(sorted(PROVIDERS))
        raise ProviderError(
            f"unknown provider {name!r} in agent/config.yaml — valid names: {valid}"
        )

    unknown = sorted(set(cfg) - _KNOWN_CONFIG_KEYS)
    if unknown:
        raise ProviderError(
            f"unknown provider config key(s): {', '.join(unknown)} "
            f"(allowed: {', '.join(sorted(_KNOWN_CONFIG_KEYS))})"
        )

    spec = PROVIDERS[name]
    env_set: dict[str, str] = dict(spec.env_set)

    # Config scalar keys -> env vars.
    for key, var in _CONFIG_ENV_MAP.items():
        value = cfg.get(key)
        if value is not None and str(value).strip():
            env_set[var] = str(value).strip()

    # Free-form extras, e.g. provider-specific tuning.
    extra_env = cfg.get("extra_env") or {}
    if not isinstance(extra_env, dict):
        raise ProviderError("provider.extra_env must be a mapping of VAR: value")
    for var, value in extra_env.items():
        env_set[str(var)] = str(value)

    # Gateway: the key may live in a provider-specific env var (e.g.
    # OPENROUTER_API_KEY); forward it to the var the SDK reads.
    if name == "gateway":
        merged = {**env, **env_set}
        if not merged.get("ANTHROPIC_BASE_URL"):
            raise ProviderError(
                "provider 'gateway' needs a base URL: set provider.base_url in "
                "agent/config.yaml or export ANTHROPIC_BASE_URL"
            )
        key_var = str(cfg.get("api_key_env") or "").strip()
        if key_var:
            key_val = env.get(key_var, "").strip()
            if not key_val:
                raise ProviderError(
                    f"provider.api_key_env points at {key_var}, but it is not set — "
                    f"export {key_var}=..."
                )
            env_set["ANTHROPIC_AUTH_TOKEN"] = key_val
        elif not (env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")):
            raise ProviderError(
                "gateway has no credential: set provider.api_key_env, or export "
                "ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY"
            )

    # Validate required groups against the merged view (existing env wins,
    # config-provided values count too).
    merged = {**env, **env_set}
    missing: list[str] = []
    for group in spec.required_any:
        if not any(merged.get(var, "").strip() for var in group):
            missing.append("/".join(group))
    if missing:
        raise ProviderError(
            f"provider {name!r} is missing required environment: "
            f"{', '.join(missing)}\nhint: {spec.doctor_hint}"
        )

    model = env_set.get("ANTHROPIC_MODEL") or env.get("ANTHROPIC_MODEL") or None
    return ResolvedProvider(
        name=name, description=spec.description, env=env_set, model=model
    )


def _main(argv: list[str]) -> int:
    import yaml

    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    if "--list" in argv:
        for pname, pspec in sorted(PROVIDERS.items()):
            print(f"{pname:10s} {pspec.description}")
        return 0

    try:
        rp = resolve_provider(cfg.get("provider"), os.environ)
    except ProviderError as exc:
        print(f"provider check FAILED ({cfg_path}):\n{exc}", file=sys.stderr)
        return 1

    print(f"provider check OK: {rp.name} — {rp.description}")
    if rp.model:
        print(f"model: {rp.model}")
    applied = sorted(rp.env)
    if applied:
        print("env applied: " + ", ".join(applied))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
