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

## Running without uv

With Python 3.11 or newer, create a virtual environment and install the same pinned versions,
checked by hash:

```
python3 -m venv ~/.venvs/wiki-interest
~/.venvs/wiki-interest/bin/python -m pip install --require-hashes -r SKILL_DIR/requirements.txt
~/.venvs/wiki-interest/bin/python SKILL_DIR/scripts/wiki.py --version
```

Then run every command with that Python instead of `uv run`. The `Re-run:` and `Next:` lines
still print `uv run ...`: replace `uv run` with `~/.venvs/wiki-interest/bin/python` when you
copy them.

## Cache and environment variables

| Variable | Effect |
|---|---|
| `WIKI_INTEREST_CACHE_DIR` | Where API responses are cached. Default: `$XDG_CACHE_HOME/wiki-interest` or `~/.cache/wiki-interest`. Safe to delete. |
| `WIKI_INTEREST_CONTACT` | Contact shown in the User-Agent sent to Wikimedia, which its API policy requires. |

Pageview histories are cached for a day and Wikidata lookups for a week, so repeated and
follow-up runs make few or no network requests. Run outputs go to `./wiki-interest-runs/`
unless `analyze --out` says otherwise.

## Common errors

| Message | What to do |
|---|---|
| `Unknown Wikipedia edition 'cz'` | Use the suggested code (`cs`). |
| `... is rate-limiting requests (HTTP 429)` | Wait a minute and re-run the same command. |
| `Could not read a response from ...` | Check the connection, then re-run. |
| `internal error in wiki-interest` | Tell the user and quote the error; the log path is in the message. |
