# ChatGPT Chrome Controller

A small CLI program that lets ChatGPT translate natural-language instructions into Playwright actions for controlling Chromium.

## Features
- Launch Chromium (headed or headless).
- Manual command loop (open, click, type, wait, screenshot).
- Optional ChatGPT-powered action planning.

## Requirements
- Python 3.10+
- Playwright (and browser binaries)
- Optional: OpenAI API key for ChatGPT planning

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## Usage
```bash
python chatgpt_chrome.py --start-url https://example.com
```

### Commands
- `open <url>`
- `click <css selector>`
- `type <css selector> <text>`
- `wait <milliseconds>`
- `screenshot <path>`
- `info` (prints title + URL)
- `chat <instruction>` (uses ChatGPT to plan actions)
- `quit`

### ChatGPT integration
Set an API key:
```bash
export OPENAI_API_KEY="..."
```
Optionally override the model:
```bash
python chatgpt_chrome.py --model gpt-4.1-mini
```

The `chat` command sends the current page URL, title, and a trimmed body text excerpt to ChatGPT, then executes the returned actions.

## Notes
- This is a minimal example intended to be extended (tools, richer context, safety checks).
- Use with caution on sensitive pages.
