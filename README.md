# repo-forge

Local autonomous runner built on the **Claude Agent SDK** (Claude Code CLI). Same workflow on any repository: you give a goal; it maps the tree, edits, runs checks, and prints one final report. The SDK stays the engine, but the API endpoint is **provider-agnostic** (Anthropic, Bedrock, Vertex, or any Anthropic-compatible gateway).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Claude Code CLI on PATH (`claude`) + credentials for your provider (see below)
export ANTHROPIC_API_KEY="..."
```

Optional: `npm install` if you want the TS SDK mirrored locally.

## Providers (where the API calls go)

The Claude Agent SDK remains the execution engine; the `provider:` section of
`agent/config.yaml` only decides **where model API calls are sent**. Switching
providers is config + env only — no code changes, same hooks, same reviewers.

| Provider | `provider.name` | Required environment |
|---|---|---|
| Anthropic (default) | `anthropic` | `ANTHROPIC_API_KEY` |
| Amazon Bedrock | `bedrock` | `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or `AWS_BEARER_TOKEN_BEDROCK` |
| Google Vertex AI | `vertex` | `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION` (+ GCP auth) |
| Any Anthropic-compatible gateway | `gateway` | `provider.base_url` in config + a key (`provider.api_key_env`, or `ANTHROPIC_AUTH_TOKEN`) |

`gateway` covers LiteLLM, OpenRouter, Kimi/GLM/DeepSeek proxies, and
self-hosted endpoints — anything that speaks the Anthropic Messages API. Example:

```yaml
provider:
  name: gateway
  base_url: https://your-gateway.example.com
  api_key_env: MY_GATEWAY_KEY   # env var holding the gateway key
  model: some-model-name
```

Optional keys for any provider: `model` (→ `ANTHROPIC_MODEL`),
`small_fast_model`, and free-form `extra_env`.

Preflight validates the configured provider and fails loud with what is missing:

```bash
.venv/bin/python agent/providers.py --check   # or just run ./agent/doctor.sh
.venv/bin/python agent/providers.py --list
```

## Run

```bash
./repo-factory "your goal in natural language"
```

Optional: point the agent at another checkout (edit/build there; config still loads from repo-forge):

```bash
export REPO_FACTORY_CWD=/path/to/other/repo
./repo-factory "…"
```

Tune defaults in `agent/config.yaml` (goal fallback, `required_final_checks`, bash block patterns).

## Queue / daemon

- Drop tasks as `inbox/*.txt`; `./agent/daemon.sh` runs `./repo-factory` and writes `outbox/*.report.txt`.
- macOS: copy `agent/repo-factory.plist.example`, replace paths, `launchctl load` the plist.

## PR loop (open PRs → cycle → drift)

When `gh` is installed and authenticated, `./agent/pr_steward_loop.sh` keeps running: if there are open PRs (or `PR_STEWARD_FORCE=1`), it invokes `repo-factory` with a stewardship goal, then sleeps (`PR_STEWARD_INTERVAL`, default 120s).

Work in another repo:

```bash
export PR_STEWARD_ROOT=/path/to/your/git/checkout
# optional: export REPO_FORGE_BIN=/path/to/repo-forge/repo-factory
./agent/pr_steward_loop.sh
```

LogLine **minimal conditions** for this behaviour (pocket-aligned) live in the minilab tree:

- `logline canon/v0.1/pocket/source/pr_stewardship.loop.v0.1.logline`
- `logline canon/v0.1/pocket/source/pr_stewardship.loop.v0.1.json`
- `logline canon/v0.1/pocket/notes/pr_stewardship.md`

## GitHub mobile app (iPhone)

Execution stays **on your Mac**; the phone only opens an **Issue** on GitHub.

### One-time on this repo (`danvoulez/repo-forge`)

- Label **`repo-forge`** is already created.
- Issue form **“Repo Forge command”** (`.github/ISSUE_TEMPLATE/repo-forge-command.yml`) applies that label when you use “New issue” → choose the template.

### Mac (leave it running)

```bash
cd /path/to/repo-forge
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
export ANTHROPIC_API_KEY="sk-ant-..."   # every shell, or put in launchd plist / login shell

cp agent/github-queue.env.example agent/github-queue.env
# edit github-queue.env — at minimum GH_FORGE_ISSUE_REPO and GH_FORGE_ISSUE_ALLOWED_AUTHORS

./agent/doctor.sh          # preflight: venv, claude, gh, API key
./agent/start_github_queue.sh   # polls Issues → runs repo-forge → comment → close
```

Optional macOS background: edit **`agent/gh-issue-queue.plist.example`** (paths + `ANTHROPIC_API_KEY`), copy to `~/Library/LaunchAgents/`, `launchctl load …`.

### iPhone (GitHub app)

**New issue** → select template **Repo Forge command** → fill **Prompt** → submit.  
Within ~45s (poll interval) the Mac picks it up, runs the agent, replies on the issue, then closes it.

**Security:** keep the queue repo private or always set **`GH_FORGE_ISSUE_ALLOWED_AUTHORS`** (comma-separated handles).

Legacy manual flow (no template): new issue + label **`repo-forge`** + body = prompt; still works with `./agent/gh_issue_daemon.sh`.

## Layout

- `CLAUDE.md` — autonomy instructions for the agent (generic).
- `.claude/skills/` — optional Skills (`repo-worker`, `autonomous-review`, `sdk-reader`).
- `agent/factory.py` — supervisor (`query()` + hooks + Task subagents).
- `agent/providers.py` — provider registry: config → SDK env vars, fail-loud preflight (`--check` / `--list`).
