"""
NeuroMail Streamlit Client with MCP Integration
"""

import json
import asyncio
import concurrent.futures
import sys
import os
import re
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

import streamlit as st
import ollama

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

st.set_page_config(
    page_title="AstraMind • NeuroMail",
    page_icon="🧠",
    layout="wide",
)

# ---------------------------------------------
# Path Helper (mirrors mcp_server.py logic)
# ---------------------------------------------

def _resolve_base_dir() -> str:
    """
    Resolve ~/Documents/Neuromail correctly on Windows,
    even when Documents lives inside OneDrive.

    Priority:
      1. NEUROMAIL_DIR env var (full override)
      2. USERPROFILE\\OneDrive\\Documents\\Neuromail  (OneDrive path, Windows)
      3. ~\\Documents\\Neuromail                      (standard fallback)
    """
    env_override = os.getenv("NEUROMAIL_DIR", "").strip()
    if env_override:
        return env_override

    home = os.path.expanduser("~")

    onedrive_docs = os.path.join(home, "OneDrive", "Documents", "Neuromail")
    if os.path.exists(onedrive_docs):
        return onedrive_docs

    return os.path.join(home, "Documents", "Neuromail")


# ---------------------------------------------
# Async Helper
# ---------------------------------------------

def run_async(coro):
    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_in_thread).result()


# ---------------------------------------------
# MCP Session
# ---------------------------------------------

@asynccontextmanager
async def get_mcp_session():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "mcp_server.py")

    if not os.path.exists(server_script):
        raise FileNotFoundError(f"mcp_server.py not found at: {server_script}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env={**os.environ}   # pass full env so dotenv vars are available
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _list_mcp_tools_async():
    try:
        async with get_mcp_session() as session:
            response = await session.list_tools()
            return [
                {"name": t.name, "description": t.description, "schema": t.inputSchema}
                for t in response.tools
            ], None
    except Exception as e:
        return [], str(e)


async def _call_mcp_tool_async(tool_name: str, arguments: dict) -> str:
    async with get_mcp_session() as session:
        result = await session.call_tool(tool_name, arguments)
        if result.content:
            return result.content[0].text
        return json.dumps({"status": "error", "message": "No content returned"})


# ---------------------------------------------
# Ollama Helpers
# ---------------------------------------------

def list_local_models() -> List[str]:
    try:
        return [m["model"] for m in ollama.list()["models"]]
    except Exception as e:
        st.error(f"Ollama error: {e}")
        return []


def ensure_model(model: str):
    if model not in list_local_models():
        with st.spinner(f"Downloading {model}..."):
            for _ in ollama.pull(model, stream=True):
                pass


def stream_chat(model: str, messages: List[Dict], options: dict):
    for chunk in ollama.chat(model=model, messages=messages, stream=True, options=options):
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield content


def parse_tool_call(text: str) -> Optional[Dict]:
    try:
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            if "tool" in data and "arguments" in data:
                return data
    except Exception:
        pass
    return None


# ---------------------------------------------
# Prompts
# ---------------------------------------------

def build_system_prompt(tools: List[Dict]) -> str:
    tools_desc = "\n".join(f"- {t['name']}: {t['description']}" for t in tools)
    return f"""You are NeuroMail, an AI email and file-management assistant.

=== AVAILABLE TOOLS ===
{tools_desc}

=== RULES ===

RULE 1 — TOOL CALL FORMAT
When calling a tool, output ONLY a raw JSON object — no markdown, no extra text:
{{"tool": "tool_name", "arguments": {{"param": "value"}}}}

RULE 2 — NEVER INVENT FILES
You have NO prior knowledge of files. Always use a tool. If the tool returns empty or error, say so honestly.

RULE 3 — list_files ROOT
To list root: {{"tool": "list_files", "arguments": {{"directory": ""}}}}
NEVER pass "Neuromail" as directory.

RULE 4 — AFTER TOOL RESULT
Describe ONLY what the tool returned. Do not guess or add extra information.
"""

def build_summarise_prompt(tool_result_json: str) -> str:
    return (
        "Tool executed. Exact result from server:\n\n"
        f"{tool_result_json}\n\n"
        "Summarise ONLY the above. Do NOT invent or assume anything not present. "
        "Report errors clearly if status is 'error'."
    )


# ---------------------------------------------
# Session State
# ---------------------------------------------

for key, default in [
    ("messages", []),
    ("mcp_tools", []),
    ("mcp_initialized", False),
    ("mcp_error", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------
# Connect MCP
# ---------------------------------------------

if not st.session_state.mcp_initialized and MCP_AVAILABLE:
    with st.spinner("Connecting to MCP server..."):
        tools, error = run_async(_list_mcp_tools_async())
        if error:
            st.session_state.mcp_error = error
        else:
            st.session_state.mcp_tools = tools
            st.session_state.mcp_initialized = True
            st.session_state.mcp_error = None


# ---------------------------------------------
# Sidebar
# ---------------------------------------------

with st.sidebar:
    st.title("🦙 Ollama Settings")
    models = list_local_models()
    if not models:
        st.warning("⚠️ No Ollama models found!")
        model = "mistral:latest"
    else:
        model = st.selectbox("Model", models, index=0)

    temperature = st.slider("Temperature", 0.0, 1.0, 0.0)
    max_tokens  = st.slider("Max Tokens", 64, 2048, 512)

    st.divider()
    st.title("🔧 MCP Status")

    if not MCP_AVAILABLE:
        st.error("❌ MCP not installed — run: pip install mcp")
    elif st.session_state.mcp_error:
        st.error("❌ MCP Connection Error")
        with st.expander("Show Error"):
            st.code(st.session_state.mcp_error)
        if st.button("🔄 Retry"):
            st.session_state.mcp_initialized = False
            st.session_state.mcp_error = None
            st.rerun()
    elif st.session_state.mcp_initialized:
        st.success(f"✅ Connected ({len(st.session_state.mcp_tools)} tools)")
        for t in st.session_state.mcp_tools:
            with st.expander(f"📦 {t['name']}"):
                st.caption(t['description'])
    else:
        st.warning("⏳ Not initialized")

    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()


# ---------------------------------------------
# Main UI
# ---------------------------------------------

st.title("AstraMind 🧠 — NeuroMail")
st.caption("Context-aware email & file assistant powered by MCP + Ollama")

if not st.session_state.mcp_initialized:
    st.warning("⚠️ MCP server not connected. File and email tools are unavailable.")
    if st.session_state.mcp_error:
        with st.expander("🔍 Troubleshooting"):
            st.code(st.session_state.mcp_error)
            st.markdown("""
**Fix checklist:**
1. `mcp_server.py` must be in the **same folder** as `streamlit_app.py`
2. Install dependencies: `pip install mcp python-dotenv`
3. Python version must be **≥ 3.10**
4. Run: `streamlit run streamlit_app.py`
""")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


user_input = st.chat_input("Ask about files, read content, or send an email…")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if st.session_state.mcp_initialized:
        ensure_model(model)
        system_prompt = build_system_prompt(st.session_state.mcp_tools)
        messages = [{"role": "system", "content": system_prompt}] + st.session_state.messages
        options  = {"temperature": temperature, "num_predict": max_tokens}

        # First LLM call
        with st.chat_message("assistant"):
            placeholder = st.empty()
            output = ""
            try:
                for token in stream_chat(model, messages, options):
                    output += token
                    placeholder.markdown(output + "▌")
                placeholder.markdown(output)
            except Exception as e:
                output = f"❌ Ollama error: {e}"
                placeholder.markdown(output)

        tool_call = parse_tool_call(output)

        if tool_call:
            with st.spinner(f"🔧 Running `{tool_call['tool']}`…"):
                try:
                    tool_result_raw = run_async(
                        _call_mcp_tool_async(tool_call["tool"], tool_call["arguments"])
                    )
                except Exception as e:
                    tool_result_raw = json.dumps({"status": "error", "message": str(e)})

            with st.expander("🛠️ Raw Tool Result (ground truth)"):
                st.code(tool_result_raw, language="json")

            summarise_messages = [
                {"role": "system",    "content": system_prompt},
                *st.session_state.messages,
                {"role": "assistant", "content": output},
                {"role": "system",    "content": build_summarise_prompt(tool_result_raw)},
            ]

            final_output = ""
            with st.chat_message("assistant"):
                fp = st.empty()
                try:
                    for token in stream_chat(model, summarise_messages, options):
                        final_output += token
                        fp.markdown(final_output + "▌")
                    fp.markdown(final_output)
                except Exception as e:
                    final_output = f"❌ Summary error: {e}"
                    fp.markdown(final_output)

            st.session_state.messages.append({"role": "assistant", "content": final_output})
        else:
            st.session_state.messages.append({"role": "assistant", "content": output})

    else:
        msg = "⚠️ MCP tools unavailable. Check sidebar."
        with st.chat_message("assistant"):
            st.warning(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})


# ---------------------------------------------
# Debug
# ---------------------------------------------

with st.expander("🐛 Debug Info"):
    import glob
    BASE_DIR = _resolve_base_dir()   # FIX: use the same resolver as the server
    st.write("**Python:**", sys.version)
    st.write("**MCP Available:**", MCP_AVAILABLE)
    st.write("**MCP Initialized:**", st.session_state.mcp_initialized)
    st.write("**Tools Loaded:**", len(st.session_state.mcp_tools))
    st.write("**Ollama Models:**", list_local_models())
    st.write("**BASE_DIR:**", BASE_DIR)
    files = [os.path.relpath(f, BASE_DIR) for f in glob.glob(os.path.join(BASE_DIR, "**/*"), recursive=True)]
    st.write("**Files in folder:**", files if files else "None found")