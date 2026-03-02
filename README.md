🧠 NeuroMail — Context-Aware Email & File Assistant

NeuroMail is an AI-powered desktop assistant that helps you search files, read documents, and send emails using a local Large Language Model (LLM).

It combines:

🦙 Ollama (local AI model)

🔌 Model Context Protocol (MCP)

🌐 Streamlit UI

📁 Local file system access

📧 Email automation

The goal of NeuroMail is to make your computer files and email system understandable through natural language.

Example:

“Find my notes file and summarize it”
“Read report.txt”
“Send this file summary to my professor”

🚀 What This Project Does

NeuroMail contains two main programs that work together.

1️⃣ Streamlit Client (streamlit_app.py)

This is the frontend AI chat interface.

It provides:

✅ Chat-based UI
✅ Connection to local Ollama models
✅ Tool calling through MCP
✅ Streaming AI responses
✅ File & email interaction through natural language

What happens here?

User types a message in chat.

The AI model analyzes the request.

If needed, it requests a tool (file search, read file, email).

The tool runs via MCP server.

Results are returned and summarized for the user.

So this file acts like:

👉 The Brain + User Interface

Key Features

ChatGPT-style interface

Model selection from local Ollama models

Temperature & token control

MCP tool status monitoring

Debug panel for troubleshooting

Streaming responses (real-time typing)

2️⃣ MCP Server (mcp_server.py)

This is the backend tool server.

It safely allows the AI to interact with your computer.

Think of it as:

👉 The Hands of the AI

Tools Provided by MCP Server
📁 File Search

Search files inside:

~/Documents/Neuromail

Example:

Find files containing "report"
📄 Read File

Reads content of a file securely.

Example:

Read notes.txt
📂 List Files

Shows folders and files inside NeuroMail directory.

Example:

Show all files
📧 Send Email

Sends emails using SMTP (Gmail supported).

Example:

Send summary to someone@example.com
🔒 Safety Features

AI cannot access files outside Neuromail folder

Path validation prevents system access

Hidden temp/log files ignored

Secure environment variable email login

🧩 How Both Programs Work Together
User
  ↓
Streamlit Chat UI
  ↓
Local LLM (Ollama)
  ↓
MCP Tool Request
  ↓
MCP Server
  ↓
File System / Email
  ↓
Result → AI Summary → User

Simple idea:

👉 AI decides WHAT to do
👉 MCP server performs HOW to do it

📁 Project Folder Structure
NeuroMail/
│
├── streamlit_app.py     # Chat interface
├── mcp_server.py        # MCP backend server
├── .env                 # Email credentials
└── README.md
⚙️ Requirements

Install Python packages:

pip install streamlit ollama mcp python-dotenv

Install Ollama from:
https://ollama.com

Pull a model:

ollama pull mistral
▶️ How to Run the Project
Step 1 — Create Neuromail Folder

Create:

Documents/Neuromail

Put files you want AI to access here.

Step 2 — Setup Email (Optional)

Create .env file:

EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
Step 3 — Run Application
streamlit run streamlit_app.py

Browser will open automatically.

💬 Example Commands

Try asking:

“List my files”

“Search for notes”

“Read project.txt”

“Summarize this file”

“Send email with this content”

🐛 Debug Panel

The app includes a debug section showing:

Python version

MCP connection status

Loaded tools

Base directory

Available files

Helpful if something doesn't work.

🎯 Why This Project Is Powerful

Most AI assistants cannot safely access local files.

NeuroMail solves this by using Model Context Protocol (MCP) which allows:

✅ Controlled tool usage
✅ Secure local automation
✅ Real AI + real actions

This turns a local LLM into a personal productivity assistant.

🔮 Future Improvements (Ideas)

Google Drive integration

Calendar scheduling

Voice commands

File summarization memory

Multi-user profiles

Automatic email drafting

👨‍💻 Author

NeuroMail — Context-Aware Email & File Automation using MCP + Local LLM.
