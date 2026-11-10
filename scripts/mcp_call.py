from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:  # pragma: no cover - dotenv is optional for this helper
    pass

DEFAULT_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8020/mcp")
TOKEN = os.environ.get("MCP_TOKEN", "").strip()


def _usage() -> str:
    return (
        "Usage:\n"
        "  mcp_call.py tools\n"
        "  mcp_call.py call <tool_name> ['{\"arg\": \"value\"}']\n"
        "  mcp_call.py <tool_name> ['{\"arg\": \"value\"}']\n\n"
        "Authentication:\n"
        "  Set MCP_TOKEN in the environment or in CartoonStudio/.env.\n"
        "  Create one with:\n"
        "    POST http://127.0.0.1:8010/api/v1/mcp/tokens\n"
        "    {\"name\": \"desktop-commander\", \"scopes\": \"production\"}\n"
    )


async def _run(command: str, tool: str | None, arguments: dict) -> int:
    if not TOKEN:
        print(
            "MCP_TOKEN is not set. Create a token from the backend and put it in .env.",
            file=sys.stderr,
        )
        print(_usage(), file=sys.stderr)
        return 2

    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        async with streamablehttp_client(DEFAULT_URL, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if command == "tools":
                    listing = await session.list_tools()
                    for item in listing.tools:
                        description = (item.description or "").strip().splitlines()
                        print(f"{item.name}\t{description[0] if description else ''}")
                    return 0
                assert tool
                result = await session.call_tool(tool, arguments)
    except Exception as exc:  # noqa: BLE001 - surface the real transport/auth error
        print(f"MCP call failed: {exc}", file=sys.stderr)
        if "401" in str(exc) or "unauthorized" in str(exc).lower():
            print(
                "Check MCP_TOKEN: the token may be revoked or the MCP server may be in no-auth mode.",
                file=sys.stderr,
            )
        return 1

    payload = getattr(result, "structuredContent", None)
    if payload is None:
        payload = getattr(result, "structured_content", None)
    texts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            texts.append(text)
    if texts:
        print("\n".join(texts))
    elif payload is not None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", default="tools")
    parser.add_argument("tool", nargs="?")
    parser.add_argument("arguments", nargs="?")
    args = parser.parse_args()

    if args.command in ("-h", "--help", "help"):
        print(_usage())
        return 0

    if args.command == "tools":
        return asyncio.run(_run("tools", None, {}))

    if args.command == "call":
        if not args.tool:
            print(_usage(), file=sys.stderr)
            return 2
        tool = args.tool
        raw = args.arguments or "{}"
    else:
        tool = args.command
        raw = args.tool or "{}"

    try:
        arguments = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Arguments must be valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(arguments, dict):
        print("Arguments must be a JSON object.", file=sys.stderr)
        return 2
    return asyncio.run(_run("call", tool, arguments))


if __name__ == "__main__":
    raise SystemExit(main())
