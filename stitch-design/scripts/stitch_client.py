#!/usr/bin/env python3
"""
Direct Google Stitch Client via remote MCP API.
Allows listing projects, creating projects, generating screens, and fetching assets.

Setup:
  Set the STITCH_API_KEY environment variable (or put it in stitch-design/.env).
  You can get a Stitch API key from https://aistudio.google.com/apikey
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── API key resolution ────────────────────────────────────────────────────────
# Priority: CLI --api-key flag > STITCH_API_KEY env var > stitch-design/.env
def _load_dotenv():
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()

DEFAULT_API_KEY = os.environ.get("STITCH_API_KEY", "")
API_URL = "https://stitch.googleapis.com/mcp"


def _get_key(api_key=None):
    key = api_key or DEFAULT_API_KEY
    if not key:
        sys.exit(
            "\nERROR: No Stitch API key found.\n"
            "  Set the STITCH_API_KEY environment variable:\n"
            "    Windows:  set STITCH_API_KEY=your_key_here\n"
            "    Mac/Linux: export STITCH_API_KEY=your_key_here\n"
            "  Or put it in stitch-design/.env:\n"
            "    STITCH_API_KEY=your_key_here\n"
            "\n  Get a key at: https://aistudio.google.com/apikey\n"
        )
    return key


def call_stitch_mcp(method_name: str, params: dict, api_key: str = None) -> dict:
    key = _get_key(api_key)
    headers = {
        "X-Goog-Api-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "stitch-design/stitch-client",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": method_name,
            "arguments": params,
        },
    }

    req = urllib.request.Request(
        API_URL,
        headers=headers,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"Stitch API Error: {data['error']}")

            result = data.get("result", {})
            content = result.get("content", [])
            if content and isinstance(content, list) and "text" in content[0]:
                try:
                    return json.loads(content[0]["text"])
                except Exception:
                    return {"text": content[0]["text"]}
            return result
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from Stitch API: {err_body}")


def list_projects(api_key=None):
    res = call_stitch_mcp("list_projects", {}, api_key=api_key)
    projects = res.get("projects", [])
    print(f"\nFound {len(projects)} Stitch project(s):")
    for p in projects:
        name = p.get("name", "")
        title = p.get("title", "(untitled)")
        dev = p.get("deviceType", "DESKTOP")
        print(f" - [{dev}] {title} (ID: {name})")
    return projects


def create_project(title: str, api_key=None):
    res = call_stitch_mcp("create_project", {"title": title}, api_key=api_key)
    print(f"Created project: {title}")
    print(json.dumps(res, indent=2))
    return res


def list_screens(project_id: str, api_key=None):
    res = call_stitch_mcp("list_screens", {"projectId": project_id}, api_key=api_key)
    screens = res.get("screens", [])
    print(f"\nFound {len(screens)} screen(s) in {project_id}:")
    for s in screens:
        sid = s.get("name", s.get("id", ""))
        title = s.get("title", s.get("name", ""))
        print(f" - {title} ({sid})")
    return screens


def generate_screen(project_id: str, prompt: str, device: str = "DESKTOP", api_key=None):
    print(f"Submitting screen generation to project {project_id} ({device})...")
    params = {
        "projectId": project_id,
        "prompt": prompt,
        "deviceType": device.upper(),
    }
    res = call_stitch_mcp("generate_screen_from_text", params, api_key=api_key)
    print("Generation complete!")
    return res


def main():
    parser = argparse.ArgumentParser(
        description="Google Stitch CLI Bridge — set STITCH_API_KEY env var before use"
    )
    parser.add_argument("--api-key", help="Stitch API key (overrides env var)")
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="List all Stitch projects")

    # create
    p_create = subparsers.add_parser("create", help="Create a new Stitch project")
    p_create.add_argument("--title", "-t", required=True, help="Project title")

    # screens
    p_screens = subparsers.add_parser("screens", help="List screens in a project")
    p_screens.add_argument("--project-id", "-p", required=True, help="Project ID")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate a screen from text")
    p_gen.add_argument("--project-id", "-p", required=True, help="Project ID")
    p_gen.add_argument("--prompt", required=True, help="Prompt text")
    p_gen.add_argument(
        "--device", default="DESKTOP", choices=["DESKTOP", "MOBILE"], help="Target device"
    )

    args = parser.parse_args()
    key = args.api_key if hasattr(args, "api_key") else None

    if args.command == "list":
        list_projects(api_key=key)
    elif args.command == "create":
        create_project(args.title, api_key=key)
    elif args.command == "screens":
        list_screens(args.project_id, api_key=key)
    elif args.command == "generate":
        generate_screen(args.project_id, args.prompt, device=args.device, api_key=key)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
