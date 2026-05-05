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

Tune defaults in `agent/config.yaml` (goal fallback, `required_final_checks`, bash block patterns).

## Queue / daemon

- Drop tasks as `inbox/*.txt`; `./agent/daemon.sh` runs `./repo-factory` and writes `outbox/*.report.txt`.
- macOS: copy `agent/repo-factory.plist.example`, replace paths, `launchctl load` the plist.

## Layout

- `CLAUDE.md` — autonomy instructions for the agent (generic).
- `.claude/skills/` — optional Skills (`repo-worker`, `autonomous-review`, `sdk-reader`).
- `agent/factory.py` — supervisor (`query()` + hooks + Task subagents).
