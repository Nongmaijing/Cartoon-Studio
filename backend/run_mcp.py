from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cartoon Studio MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    parser.add_argument("--profile", choices=["all", "studio", "opencode"], default=os.environ.get("MCP_PROFILE", "all"))
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--public-url", default=None, help="Issuer/resource URL for bearer metadata")
    args = parser.parse_args()

    os.environ["MCP_PROFILE"] = args.profile
    if args.host:
        os.environ["MCP_HOST"] = args.host
    if args.port:
        os.environ["MCP_PORT"] = str(args.port)
    if args.public_url:
        os.environ["MCP_PUBLIC_URL"] = args.public_url

    from app.mcp.server import create_mcp_server

    mcp = create_mcp_server(args.profile)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
