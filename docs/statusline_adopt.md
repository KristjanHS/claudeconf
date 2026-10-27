# Statusline: adopt

Needs `bash`, `jq`, `git`.

## 1. Install

```sh
cp .claude/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

## 2. Wire into `~/.claude/settings.json`

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh", "padding": 0 }
```

## 3. Set your budget

The thresholds are fixed token counts. Changing `WINDOW` does **not** move them, so edit them all together:

| Line | Default | Controls |
|---|---|---|
| `WINDOW=300000` | 300k | 100% of the bar and the % shown |
| `STOP_PCT=75` | 225k | stop point the warning counts down to |
| `-ge 200000` | 200k | bar turns amber |
| `-ge 240000` | 240k | bar turns red |
| `-le 30000` | 195k | `← /clear soon` appears (30k before stop) |

If you use the budget governor (`impag-budget-check.py`), keep its 200k hard stop equal to the amber mark.

## 4. Check

Start a session. The line should show model, bar, %, tokens, repo[branch], cost, and 5h/7d limits.
Blank line → `jq`/`git` not on `PATH`, or wrong `statusLine` path.
