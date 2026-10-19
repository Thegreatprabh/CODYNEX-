# 🧬 CODYNEX Engine — Connect ANY AI Agent (Complete Setup Guide)

> One install. Every agent. If a connection fails, 99% of the time it's **the
> python path** — see [The Golden Rule](#-the-golden-rule-read-this-first).

## Step 0 — Install DNA (one command, every OS)

```bash
pip install git+https://github.com/Thegreatprabh/codynex-engine
```

Windows (if `pip` and `python` are different installs — very common):

```powershell
python -m pip install git+https://github.com/Thegreatprabh/codynex-engine
```

Verify the install:

```bash
python -m dna --help
# → should list: init, map, impact, risks, verify, decisions, watch, plan, mcp
```

Then build your first DNA:

```bash
cd /path/to/your-project
dna init .
```

---

## 🔑 The Golden Rule (read this first)

**GUI apps do NOT see your terminal's `python`.** Codex Desktop, ChatGPT Desktop,
Claude Desktop, Cursor — they launch with a minimal `PATH`, so a bare `python`
command fails silently and the server shows "Enabled" but never works in chat.

**Always use the FULL python path.** Find yours:

```bash
python -c "import sys; print(sys.executable)"
```

Examples of what it prints:

| OS      | Example full path                                              |
|---------|----------------------------------------------------------------|
| Windows | `C:\Users\YOU\AppData\Local\Programs\Python\Python314\python.exe` |
| macOS   | `/opt/homebrew/bin/python3`                                    |
| Linux   | `/usr/bin/python3`                                             |

Copy the **entire** line, `C:` to `python.exe`. That value goes in every
`command` field below.

---

## 🛠️ Manual setup — every famous agent

The DNA MCP server runs as: `<FULL PYTHON PATH> -m dna mcp`
(4 tools: `dna_map`, `dna_impact`, `dna_plan`, `dna_decisions`)

### 1. Claude Code

```bash
claude mcp add dna -- <FULL PYTHON PATH> -m dna mcp
```

or manually in `~/.claude.json`:

```json
{
  "mcpServers": {
    "dna": {
      "command": "<FULL PYTHON PATH>",
      "args": ["-m", "dna", "mcp"]
    }
  }
}
```

Restart Claude Code → `/mcp` to verify → ask *"what's the blast radius of
changing auth.py?"*

### 2. Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dna": {
      "command": "<FULL PYTHON PATH>",
      "args": ["-m", "dna", "mcp"]
    }
  }
}
```

Save → restart Claude Desktop.

### 3. Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "dna": {
      "command": "<FULL PYTHON PATH>",
      "args": ["-m", "dna", "mcp"]
    }
  }
}
```

Restart Cursor → Settings → MCP → `dna` enabled.

### 4. Codex Desktop (Windows / Mac)

1. Open **Settings → MCP servers → Add server**
2. Fill exactly:
   - **Name:** `dna`
   - **Type:** `STDIO` (not Streamable HTTP)
   - **Command:** your **full python path** from the Golden Rule above
   - **Arguments:** `-m dna mcp`
3. **Save → Quit the app fully → reopen**
4. In the composer type `/mcp` → `dna` with 4 tools should appear

### 5. Codex CLI (terminal)

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.dna]
command = "<FULL PYTHON PATH>"
args = ["-m", "dna", "mcp"]
```

Verify: `codex mcp list`, then `/mcp` inside a session.

### 6. ChatGPT Desktop App

Same flow as Codex Desktop — the ChatGPT desktop app shares the Codex MCP
config (`~/.codex/config.toml`):

1. **Settings → MCP servers → Add server → STDIO**
2. **Command:** full python path · **Arguments:** `-m dna mcp`
3. Save → full restart → `/mcp`

> ⚠️ **chatgpt.com (web) cannot run local servers.** It only connects to
> *remote* MCP servers over HTTPS. The desktop app works because it launches
> the local process on your machine.

### 7. Gemini CLI

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "dna": {
      "command": "<FULL PYTHON PATH>",
      "args": ["-m", "dna", "mcp"]
    }
  }
}
```

Restart your terminal session.

### 8. Antigravity (Google's AI IDE)

1. Open the **Agent panel** (right side) → click **`...`** → **MCP Servers**
2. Click **Manage MCP Servers → View raw config** (opens `mcp_config.json`)
3. Add:

```json
{
  "mcpServers": {
    "dna": {
      "command": "<FULL PYTHON PATH>",
      "args": ["-m", "dna", "mcp"]
    }
  }
}
```

4. Save → back in **Manage MCP Servers** click **Refresh** → restart Antigravity

### 9. Termux (Android)

```bash
pkg install python git
pip install git+https://github.com/Thegreatprabh/codynex-engine
cd /path/to/project && dna init .
```

Then use Gemini CLI in Termux — DNA is stdlib-only, Termux-native.

---

## ✅ Verify (any agent)

Ask your agent:

> *"Use dna_map to show me this project's architecture."*

Then:

> *"Use dna_plan to predict what happens if I change the login system."*

If it answers with real components from YOUR project — you're connected. 🧬

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| Server shows "Enabled" but tools don't appear in chat | **Full python path** (Golden Rule). Quit the app fully and reopen. |
| `spawn python ENOENT` | Same — the app can't find `python` on PATH. Use the absolute path. |
| Tools appear but return "no DNA found" | Run `dna init` in the project first — the agent needs a DNA to query. |
| `ModuleNotFoundError: No module named 'dna'` | Reinstall: `python -m pip install git+https://github.com/Thegreatprabh/codynex-engine` with the SAME python as the full path. |
| Works in terminal, not in the GUI app | Terminal and GUI apps have different PATHs — this is normal. Full path fixes it. |

---

MIT © 2026 Prabhjot Singh
