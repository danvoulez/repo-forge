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

Execution stays **on your Mac**; the phone only **opens an Issue** on GitHub.

1. Create a label once (desktop):  
   `gh label create repo-forge --repo OWNER/REPO --description "repo-forge remote queue"`
2. Prefer a **private** repo for this queue, or set **`GH_FORGE_ISSUE_ALLOWED_AUTHORS`** (comma-separated GitHub usernames). Anyone who can open an issue with that label can otherwise trigger your local agent.
3. On the Mac (logged in with `gh auth login`), run:

```bash
export GH_FORGE_ISSUE_REPO=OWNER/REPO
export GH_FORGE_ISSUE_ALLOWED_AUTHORS=yourusername
export REPO_FACTORY_CWD=/path/to/project/to/edit   # optional
./agent/gh_issue_daemon.sh
```

4. On the **GitHub app**: New issue → title livre → **body = o prompt completo** para o `repo-forge` → assign label **`repo-forge`** → submit.

The daemon polls every ~45s, runs `./repo-forge` with the issue body, posts the report as a comment (truncated if huge), and closes the issue.

## Layout

- `CLAUDE.md` — autonomy instructions for the agent (generic).
- `.claude/skills/` — optional Skills (`repo-worker`, `autonomous-review`, `sdk-reader`).
- `agent/factory.py` — supervisor (`query()` + hooks + Task subagents).
