"""
NeuroMail MCP Server
Provides file search and email sending capabilities via Model Context Protocol
"""

import os
import sys
import json
import smtplib
import logging
from email.message import EmailMessage
from dotenv import load_dotenv

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# ---------------------------------------------
# CRITICAL: Log to stderr ONLY — stdout is reserved for MCP protocol
# ---------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger("neuromail")

# ---------------------------------------------
# Configuration
# ---------------------------------------------
load_dotenv()

# ---- FIX: Resolve the correct base directory ----
def _resolve_base_dir() -> str:
    """
    Resolve ~/Documents/Neuromail correctly on Windows,
    even when Documents lives inside OneDrive.

    Priority:
      1. NEUROMAIL_DIR env var (full override)
      2. USERPROFILE\\OneDrive\\Documents\\Neuromail  (OneDrive path, Windows)
      3. ~\\Documents\\Neuromail                      (standard fallback)
    """
    # Allow full override via env var
    env_override = os.getenv("NEUROMAIL_DIR", "").strip()
    if env_override:
        return env_override

    home = os.path.expanduser("~")

    # Windows + OneDrive: try OneDrive\Documents first
    onedrive_docs = os.path.join(home, "OneDrive", "Documents", "Neuromail")
    if os.path.exists(onedrive_docs):
        return onedrive_docs

    # Standard path
    return os.path.join(home, "Documents", "Neuromail")

BASE_DIR = _resolve_base_dir()
os.makedirs(BASE_DIR, exist_ok=True)

EXCLUDED_EXTENSIONS = {".log", ".tmp", ".bak", ".swp"}

EMAIL_USER  = os.getenv("EMAIL_USER", "")
EMAIL_PASS  = os.getenv("EMAIL_PASS", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.getenv("SMTP_PORT", "587"))

log.info("BASE_DIR = %s", BASE_DIR)
if not EMAIL_USER or not EMAIL_PASS:
    log.warning("Email credentials not set — send_email will not work.")

server = Server("neuromail-server")

# ---------------------------------------------
# Helpers
# ---------------------------------------------

def _safe_abspath(base: str, relative: str):
    full = os.path.abspath(os.path.join(base, relative))
    return full if full.startswith(os.path.abspath(base)) else None

def _excluded(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in EXCLUDED_EXTENSIONS

# ---------------------------------------------
# Tool Implementations
# ---------------------------------------------

def file_search(query: str, max_results: int = 5) -> dict:
    if not query.strip():
        return {"status": "error", "message": "Query cannot be empty", "files": []}
    matches = []
    try:
        for root, dirs, files in os.walk(BASE_DIR):
            for filename in files:
                if _excluded(filename):
                    continue
                if query.lower() in filename.lower():
                    full_path = os.path.join(root, filename)
                    matches.append({
                        "name": filename,
                        "path": os.path.relpath(full_path, BASE_DIR),
                        "size": os.path.getsize(full_path)
                    })
                    if len(matches) >= max_results:
                        return {"status": "success", "count": len(matches), "files": matches}
    except Exception as e:
        return {"status": "error", "message": str(e), "files": []}
    return {"status": "success", "count": len(matches), "files": matches}


def read_file(path: str, max_chars: int = 5000) -> dict:
    full_path = _safe_abspath(BASE_DIR, path)
    if not full_path:
        return {"status": "error", "message": "Access denied: path outside safe directory"}
    if not os.path.exists(full_path):
        return {"status": "error", "message": f"File not found: {path}"}
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
        return {"status": "success", "path": path, "content": content, "truncated": len(content) == max_chars}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_files(directory: str = "") -> dict:
    cleaned = (directory or "").strip().strip("/\\")
    if cleaned.lower() in ("", "neuromail"):
        cleaned = ""
    target_dir = _safe_abspath(BASE_DIR, cleaned)
    if not target_dir:
        return {"status": "error", "message": "Access denied"}
    if not os.path.exists(target_dir):
        return {"status": "error", "message": f"Directory not found: '{directory}'"}
    files, dirs = [], []
    try:
        for item in sorted(os.listdir(target_dir)):
            if _excluded(item):
                continue
            item_path = os.path.join(target_dir, item)
            rel = os.path.relpath(item_path, BASE_DIR)
            if os.path.isfile(item_path):
                files.append({"name": item, "path": rel, "size": os.path.getsize(item_path)})
            elif os.path.isdir(item_path):
                dirs.append({"name": item, "path": rel})
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {
        "status": "success",
        "base_dir": BASE_DIR,
        "directory": cleaned or "root",
        "files": files,
        "directories": dirs
    }


def send_email(to: str, subject: str, body: str, cc: str = None) -> dict:
    if not EMAIL_USER or not EMAIL_PASS:
        return {"status": "error", "message": "Email credentials not configured."}
    try:
        msg = EmailMessage()
        msg["From"]    = EMAIL_USER
        msg["To"]      = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.set_content(body)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        return {"status": "success", "message": f"Email sent to {to}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------
# MCP Protocol Handlers
# ---------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="file_search",
            description="Search filenames in ~/Documents/Neuromail. Hidden: .log/.tmp files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query":       {"type": "string",  "description": "Filename search term"},
                    "max_results": {"type": "number",  "description": "Max results (default 5)", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="read_file",
            description="Read a file's content. Provide relative path from Neuromail root (e.g. 'notes.txt').",
            inputSchema={
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Relative file path"},
                    "max_chars": {"type": "number", "description": "Max chars (default 5000)", "default": 5000}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_files",
            description="List files and sub-folders. Pass '' (empty string) for the Neuromail root. NEVER pass 'Neuromail'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Sub-folder or '' for root", "default": ""}
                }
            }
        ),
        Tool(
            name="send_email",
            description="Send an email via SMTP.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to":      {"type": "string"},
                    "subject": {"type": "string"},
                    "body":    {"type": "string"},
                    "cc":      {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    args = arguments or {}
    log.info("Tool called: %s | args: %s", name, args)

    if   name == "file_search": result = file_search(**args)
    elif name == "read_file":   result = read_file(**args)
    elif name == "list_files":  result = list_files(**args)
    elif name == "send_email":  result = send_email(**args)
    else:                       result = {"status": "error", "message": f"Unknown tool: {name}"}

    log.info("Tool result status: %s", result.get("status"))
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


# ---------------------------------------------
# Entry Point
# ---------------------------------------------

async def main():
    log.info("NeuroMail MCP server starting…")
    try:
        async with stdio_server() as (read_stream, write_stream):
            log.info("Stdio transport ready")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="neuromail",
                    server_version="1.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    except Exception as e:
        log.error("Server crashed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())