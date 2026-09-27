# Setup and troubleshooting

## Requirements

- **uv** runs the scripts with pinned dependencies (`scripts/wiki.py.lock`) and downloads a
  suitable Python by itself when needed. Check with `uv --version`.
- **Internet access** to `wikimedia.org`, `www.wikidata.org`, `meta.wikimedia.org` and
  `*.wikipedia.org`.

## If uv is missing

Ask the user before installing anything. The official instructions are at
https://docs.astral.sh/uv/getting-started/installation/ (for example `pip install uv`, or
`brew install uv` on macOS).

## In Codex (or another sandboxed agent)

Codex's default sandbox (`workspace-write`) has **network off**, and it can write only to the
workspace and `/tmp`. This skill needs the network (Wikimedia APIs, and uv's first download).
uv also keeps its cache in `~/.cache/uv`. Either:

- approve Codex's prompt when a `uv run` command needs network or the uv cache, or
- start Codex with network enabled and uv's cache under `/tmp`:
  `UV_CACHE_DIR=/tmp/uv-cache codex -c 'sandbox_workspace_write.network_access=true'`

The skill's own pageview cache falls back to a folder in the system temp dir when
`~/.cache/wiki-signal` isn't writable, and run outputs go to `./wiki-signal-runs/` in the
workspace.

## Running without uv

With Python 3.11 or newer, create a virtual environment and install the same pinned versions,
checked by hash:

```
python3 -m venv ~/.venvs/wiki-signal
~/.venvs/wiki-signal/bin/python -m pip install --require-hashes -r SKILL_DIR/requirements.txt
~/.venvs/wiki-signal/bin/python SKILL_DIR/scripts/wiki.py --version
```

Then run every command with that Python instead of `uv run`. The `Re-run:` and `Next:` lines
still print `uv run ...`: replace `uv run` with `~/.venvs/wiki-signal/bin/python` when you
copy them.

## Cache and environment variables

| Variable | Effect |
|---|---|
| `WIKI_SIGNAL_CACHE_DIR` | Where API responses are cached. Default: `$XDG_CACHE_HOME/wiki-signal` or `~/.cache/wiki-signal`. Safe to delete. |
| `WIKI_SIGNAL_CONTACT` | Contact shown in the User-Agent sent to Wikimedia, which its API policy requires. |

Pageview histories are cached for a day and Wikidata lookups for a week, so repeated and
follow-up runs make few or no network requests. Run outputs go to `./wiki-signal-runs/`
unless `analyze --out` says otherwise.

## Common errors

| Message | What to do |
|---|---|
| `Unknown Wikipedia edition 'cz'` | Use the suggested code (`cs`). |
| `... is rate-limiting requests (HTTP 429)` | Wait a minute and re-run the same command. |
| `Could not read a response from ...` | Check the connection, then re-run. |
| `internal error in wiki-signal` | Tell the user and quote the error; the log path is in the message. |
