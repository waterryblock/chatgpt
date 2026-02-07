#!/usr/bin/env python3
import argparse
import json
import os
import sys
import textwrap
from typing import Any, Dict, List

import requests
from playwright.sync_api import sync_playwright

DEFAULT_MODEL = "gpt-4.1-mini"


def build_prompt(instruction: str, page_context: Dict[str, str]) -> List[Dict[str, str]]:
    system = textwrap.dedent(
        """
        You are an automation planner for Chromium. Convert the user's instruction into a
        JSON object with an "actions" array. Each action must be one of:
        - {"type": "open", "url": "https://..."}
        - {"type": "click", "selector": "css selector"}
        - {"type": "type", "selector": "css selector", "text": "..."}
        - {"type": "wait", "ms": 1000}
        - {"type": "screenshot", "path": "screenshot.png"}
        - {"type": "info"}

        Only output JSON. No markdown.
        """
    ).strip()

    context_lines = [
        f"URL: {page_context.get('url', '')}",
        f"Title: {page_context.get('title', '')}",
        "Body (trimmed):",
        page_context.get("body", ""),
    ]
    user = "\n".join(context_lines) + "\n\nInstruction: " + instruction

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_openai(messages: List[Dict[str, str]], model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "input": messages,
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    output_text = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                output_text.append(content.get("text", ""))
    return "\n".join(output_text).strip()


def extract_actions(raw_text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model output was not valid JSON: {exc}\nRaw: {raw_text}") from exc

    actions = data.get("actions")
    if not isinstance(actions, list):
        raise ValueError("JSON must include an 'actions' array")
    return actions


def get_page_context(page) -> Dict[str, str]:
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        body_text = page.inner_text("body")
    except Exception:
        body_text = ""
    body_text = body_text.strip().replace("\r\n", "\n")
    if len(body_text) > 5000:
        body_text = body_text[:5000] + "\n..."
    return {
        "url": page.url,
        "title": title,
        "body": body_text,
    }


def run_actions(page, actions: List[Dict[str, Any]]) -> None:
    for action in actions:
        action_type = action.get("type")
        if action_type == "open":
            url = action.get("url")
            if not url:
                raise ValueError("open action requires url")
            page.goto(url)
        elif action_type == "click":
            selector = action.get("selector")
            if not selector:
                raise ValueError("click action requires selector")
            page.click(selector)
        elif action_type == "type":
            selector = action.get("selector")
            text = action.get("text", "")
            if not selector:
                raise ValueError("type action requires selector")
            page.fill(selector, text)
        elif action_type == "wait":
            ms = action.get("ms", 0)
            page.wait_for_timeout(ms)
        elif action_type == "screenshot":
            path = action.get("path", "screenshot.png")
            page.screenshot(path=path, full_page=True)
        elif action_type == "info":
            print(f"Title: {page.title()}")
            print(f"URL: {page.url}")
        else:
            raise ValueError(f"Unknown action type: {action_type}")


def handle_chat(page, instruction: str, model: str) -> None:
    context = get_page_context(page)
    messages = build_prompt(instruction, context)
    raw_text = call_openai(messages, model=model)
    actions = extract_actions(raw_text)
    run_actions(page, actions)


def parse_manual_command(line: str) -> Dict[str, Any]:
    parts = line.strip().split()
    if not parts:
        return {}
    cmd = parts[0]
    if cmd == "open" and len(parts) >= 2:
        return {"type": "open", "url": parts[1]}
    if cmd == "click" and len(parts) >= 2:
        selector = " ".join(parts[1:])
        return {"type": "click", "selector": selector}
    if cmd == "type" and len(parts) >= 3:
        selector = parts[1]
        text = " ".join(parts[2:])
        return {"type": "type", "selector": selector, "text": text}
    if cmd == "wait" and len(parts) >= 2:
        return {"type": "wait", "ms": int(parts[1])}
    if cmd == "screenshot" and len(parts) >= 2:
        return {"type": "screenshot", "path": parts[1]}
    if cmd == "info":
        return {"type": "info"}
    if cmd == "chat" and len(parts) >= 2:
        return {"type": "chat", "instruction": " ".join(parts[1:])}
    if cmd in {"quit", "exit"}:
        return {"type": "quit"}
    return {"type": "unknown", "raw": line}


def main() -> int:
    parser = argparse.ArgumentParser(description="ChatGPT-powered Chromium controller")
    parser.add_argument("--start-url", default="https://example.com")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        page.goto(args.start_url)

        print("Chrome controller ready. Type 'quit' to exit.")
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            command = parse_manual_command(line)
            if not command:
                continue
            if command.get("type") == "quit":
                break
            if command.get("type") == "chat":
                try:
                    handle_chat(page, command.get("instruction", ""), args.model)
                except Exception as exc:
                    print(f"Chat error: {exc}")
                continue
            if command.get("type") == "unknown":
                print("Unknown command. Try: open, click, type, wait, screenshot, info, chat, quit")
                continue
            try:
                run_actions(page, [command])
            except Exception as exc:
                print(f"Command error: {exc}")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
