# Demo GIF — Design Spec

**Date:** 2026-03-15
**Goal:** Replace the `docs/demo.gif` placeholder with a real animated ClawLite demo.

---

## What will be shown

A single scene: `clawlite run "what can you do?"` with a concise streaming response inside a macOS-style window.

**Sequence of states:**

1. The prompt appears: `❯ clawlite run "what can you do?"`
2. The cursor blinks briefly
3. `⠸ thinking...` appears in gray
4. The response arrives line by line with a streaming effect:
   - `I can help with quite a lot. Here is the short version:`
   - `🧠 Memory — I remember what we discuss across sessions`
   - `🔍 Search — I can research the web in real time`
   - `💻 Code — I write, review, and run scripts`
   - `📂 Files — I read, create, and edit local files`
   - `📡 Channels — I reply on Telegram and Discord`
   - `Use clawlite skills list to see the full catalog.`
5. A final 3-second pause plays before the loop restarts

---

## Technical approach: Playwright + Pillow

No new dependencies are required. Playwright is already listed in `pyproject.toml`, and Pillow is already installed.

**Flow of the `scripts/make_demo_gif.py` script:**

1. Verify or install Chromium with `playwright install chromium`
2. Render terminal-window HTML through headless Playwright
3. For each state, inject content with JavaScript and capture a PNG screenshot at 720×400 px
4. Use Pillow to assemble the PNGs into an animated GIF with per-frame delays
5. Save the output to `docs/demo.gif` and clean up temporary frames

---

## Visual specification

| Parameter | Value |
|-----------|-------|
| Dimensions | 720 × 400 px |
| Theme | Catppuccin Mocha |
| Window background | `#1e1e2e` |
| Title bar | `#2a2a3e` |
| Main text | `#cdd6f4` |
| Green prompt | `#a6e3a1` |
| Blue command | `#89b4fa` |
| Cyan argument | `#89dceb` |
| Spinner/footer | `#6c7086` |
| Font | system monospace (fallback: Courier New) |
| Loop | infinite |
| Total duration | ~15 seconds |

---

## Per-frame delays

| State | Delay |
|--------|-------|
| Prompt typing (per character) | 80ms |
| Blinking cursor | 400ms × 2 |
| Spinner | 800ms |
| First response line | 600ms |
| Each subsequent line | 500ms |
| Last line + footer | 800ms |
| Final pause | 3000ms |

---

## Generated file

`docs/demo.gif` — replaces the current placeholder (847 KB, empty window).

---

## Out of scope

- Gateway/dashboard web UI
- Multi-scene demos (memory list, skills list)
- Real provider configuration (the demo is scripted)
