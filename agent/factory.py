#!/usr/bin/env python3
"""Generic repository factory supervisor.

Execution engine: Claude Agent SDK + Claude Code CLI (unchanged).
API endpoint:   provider-agnostic — see agent/providers.py and the
                `provider:` section of agent/config.yaml.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import anyio
import yaml

FORGE_ROOT = Path(__file__).resolve().parents[1]

# --- Resolve the provider BEFORE importing the SDK -------------------------
# The SDK / Claude Code CLI reads provider env vars (ANTHROPIC_BASE_URL,
# CLAUDE_CODE_USE_BEDROCK, …) when it starts, so they must be in place first.
from providers import ProviderError, resolve_provider  # noqa: E402


def _load_config() -> dict:
    path = FORGE_ROOT / "agent" / "config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(cfg, dict):
        print(f"repo-forge: {path} must be a YAML mapping", file=sys.stderr)
        sys.exit(2)
    known = {
        "project_name",
        "goal",
        "max_turns",
        "permission_mode",
        "setting_sources",
        "allowed_tools",
        "blocked_bash_patterns",
        "required_final_checks",
        "provider",
    }
    for key in sorted(set(cfg) - known):
        print(f"repo-forge: warning: unknown config key {key!r} in {path}", file=sys.stderr)
    return cfg


CONFIG = _load_config()

try:
    PROVIDER = resolve_provider(CONFIG.get("provider"), os.environ)
except ProviderError as exc:
    print(f"repo-forge: provider configuration error:\n{exc}", file=sys.stderr)
    sys.exit(2)
os.environ.update(PROVIDER.env)

print(
    f"repo-forge: provider={PROVIDER.name} ({PROVIDER.description})"
    + (f" model={PROVIDER.model}" if PROVIDER.model else ""),
    file=sys.stderr,
)

try:
    from claude_agent_sdk import ClaudeAgentOptions, query
    from claude_agent_sdk.types import (
        AgentDefinition,
        HookContext,
        HookInput,
        HookJSONOutput,
        HookMatcher,
        ResultMessage,
    )
except ImportError:
    print(
        "repo-forge: claude-agent-sdk is not installed — run:\n"
        "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)


def _target_root() -> Path:
    """Working copy to edit; defaults to repo-forge install dir."""
    raw = os.environ.get("REPO_FACTORY_CWD", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return FORGE_ROOT


def _audit_log_path(target: Path) -> Path:
    log_dir = target / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "repo-forge-audit.log"


def _compile_bash_blockers(patterns: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            out.append(re.compile(p))
        except re.error:
            out.append(re.compile(re.escape(p)))
    return out


_BASH_BLOCKERS = _compile_bash_blockers(CONFIG.get("blocked_bash_patterns", []))


def _make_audit_hook(target: Path):
    audit_log = _audit_log_path(target)

    async def audit_file_change(
        input: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> HookJSONOutput:
        if input.get("hook_event_name") != "PostToolUse":
            return {"continue_": True}

        tool_name = input.get("tool_name", "")
        if tool_name not in {"Write", "Edit"}:
            return {"continue_": True}

        tool_input = input.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("path") or "unknown"

        with audit_log.open("a", encoding="utf-8") as fh:
            fh.write(f"{tool_use_id or '?'}: {tool_name} {file_path}\n")

        return {"continue_": True}

    return audit_file_change


async def bash_guard(
    input: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    if input.get("hook_event_name") != "PreToolUse":
        return {"continue_": True}
    if input.get("tool_name") != "Bash":
        return {"continue_": True}

    command = (input.get("tool_input") or {}).get("command", "") or ""
    for rx in _BASH_BLOCKERS:
        if rx.search(command):
            return {
                "continue_": False,
                "stopReason": "Blocked by factory bash safety rule",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Command matched blocked pattern: {rx.pattern!r}"
                    ),
                },
            }

    return {"continue_": True}


def _agents() -> dict[str, AgentDefinition]:
    return {
        "code-reviewer": AgentDefinition(
            description="Independent reviewer for general code changes.",
            prompt=(
                "You are a strict code reviewer for this repository. Inspect changes for "
                "correctness, maintainability, missing tests, and latent bugs. "
                "Do not edit files; reply with concrete findings only."
            ),
            tools=["Read", "Glob", "Grep", "Bash"],
        ),
        "security-reviewer": AgentDefinition(
            description="Independent security reviewer.",
            prompt=(
                "You are a security reviewer. Look for unsafe shell usage, secret leaks, "
                "path traversal, injection risks, auth/authz mistakes, and destructive "
                "filesystem operations. Do not edit; concrete findings only."
            ),
            tools=["Read", "Glob", "Grep", "Bash"],
        ),
        "sdk-verifier": AgentDefinition(
            description="Verifier for Claude Agent SDK / Claude Code integration.",
            prompt=(
                "Verify Claude Agent SDK usage: imports, ClaudeAgentOptions fields, hooks, "
                "subagent Task spawning, permission modes, and tool names. Use docs or "
                "the installed package source when uncertain. Do not edit; findings only."
            ),
            tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Bash"],
        ),
    }


def _final_checks_block(checks: list[str]) -> str:
    if not checks:
        return ""
    lines = "\n".join(f"- `{c}`" for c in checks)
    return (
        "\nBefore your final answer, run these repository checks when a Makefile (or "
        "equivalent) exists; if a command is missing, say so explicitly instead of "
        "skipping silently:\n"
        f"{lines}\n"
    )


async def main() -> int:
    target = _target_root()
    user_goal = " ".join(sys.argv[1:]).strip()
    if not user_goal:
        user_goal = str(CONFIG.get("goal", "")).strip()

    checks = CONFIG.get("required_final_checks") or []
    checks_txt = _final_checks_block(checks)

    system_prompt = f"""You are Repository Factory, an autonomous local engineering agent.

Repository root (working copy): {target}
Tooling / config loaded from repo-forge install: {FORGE_ROOT}

Mission:
{CONFIG.get("goal")}

Operating rules:
- Never ask the human questions or request approval.
- Do not use AskUserQuestion or equivalent.
- If CLAUDE.md exists in the repo root, read it; otherwise infer conventions from the tree.
- Map the repo before editing; prefer minimal vertical slices with real verification.
- Use the Task tool to spawn fresh subagents when helpful: code-reviewer, security-reviewer, sdk-verifier.
- Apply reviewer findings when they are correct; re-run checks after fixes.

{checks_txt}

Finish with one consolidated report matching CLAUDE.md when present, otherwise use the same sections: DONE/FAILED, changes, commands, tests, artifacts, blockers.
"""

    prompt = f"""Goal from the operator:
{user_goal}

Execute end-to-end without questions. When finished, output only the final report."""

    hooks = {
        "PreToolUse": [
            HookMatcher(matcher="Bash", hooks=[bash_guard], timeout=30.0),
        ],
        "PostToolUse": [
            HookMatcher(
                matcher="Write|Edit",
                hooks=[_make_audit_hook(target)],
                timeout=15.0,
            ),
        ],
    }

    options_kwargs: dict = dict(
        cwd=str(target),
        system_prompt=system_prompt,
        max_turns=int(CONFIG.get("max_turns", 80)),
        permission_mode=str(CONFIG.get("permission_mode", "acceptEdits")),
        allowed_tools=list(CONFIG.get("allowed_tools", [])),
        setting_sources=list(CONFIG.get("setting_sources", ["project"])),
        agents=_agents(),
        hooks=hooks,
    )
    if PROVIDER.model:
        options_kwargs["model"] = PROVIDER.model
    options = ClaudeAgentOptions(**options_kwargs)

    final_text: str | None = None
    exit_error: str | None = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            exit_error = (
                "; ".join(message.errors)
                if message.errors
                else ("error" if message.is_error else None)
            )
            final_text = message.result

    print("\n================ REPOSITORY FACTORY FINAL ================\n")
    if exit_error and not final_text:
        print(f"FAILED ({exit_error})\n")
    print(final_text or "No final result returned (see Claude Code transcript / stderr).")
    return 1 if exit_error else 0


if __name__ == "__main__":
    try:
        raise SystemExit(anyio.run(main))
    except KeyboardInterrupt:
        print("\nrepo-forge: interrupted by operator", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:  # SDK / CLI startup or transport failures
        print(
            f"\nrepo-forge: FAILED — agent run aborted: {type(exc).__name__}: {exc}\n"
            "check provider credentials/endpoint (./agent/doctor.sh) and the "
            "Claude Code CLI installation.",
            file=sys.stderr,
        )
        raise SystemExit(1)
