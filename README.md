# repo-forge

Local autonomous runner built on the **Claude Agent SDK** (Claude Code CLI). Same workflow on any repository: you give a goal; it maps the tree, edits, runs checks, and prints one final report.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Claude Code CLI on PATH (`claude`) + ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY="..."
```

Optional: `npm install` if you want the TS SDK mirrored locally.

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
