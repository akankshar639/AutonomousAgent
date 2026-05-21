# Fully Autonomous Local Agent

A fully local, offline-capable AI agent that can control your desktop, browser, files, emails, calendar, LinkedIn, Teams, and more — all through natural language. No cloud. No API keys. Everything runs on your machine using Ollama.

## What It Is

This is a multi-step autonomous agent powered by local LLMs (via Ollama). You type a task in plain English, and the agent figures out which tools to use, executes them step by step, and completes the task — without you doing anything else.

It uses:
- **qwen2.5-coder:7b** — the main reasoning and code generation model
- **llava:7b** — the vision model for understanding images and UI redesign tasks


## What It Can Do

| Category | Capabilities |
|---|---|
| **Email** | Send emails via Outlook Web or Gmail |
| **Teams** | Send chat messages, share files, schedule/cancel meetings |
| **LinkedIn** | Send connection requests |
| **Google Calendar** | Schedule Google Meet / Calendar events |
| **Browser** | Open URLs, fill forms, click elements, search the web |
| **Files** | Read, write, create `.docx` Word documents, extract text from PDF/XLSX/DOCX |
| **Code** | Write and run Python, HTML, CSS, JS projects |
| **Desktop** | Take screenshots, click on screen, type text, open apps |
| **Camera** | Capture photos from webcam, record videos |
| **Media** | Transcribe video/audio files locally using Whisper |
| **Vision** | Describe images, match UI designs from reference images |
| **Shell** | Execute any shell command |

## Project Structure

```
AutonomousAgent/
├── agent/
│   ├── core.py              # Main execution loop
│   ├── context.py           # System prompt builder
│   ├── logger.py            # Tool call parser and dispatcher
│   └── memory.py            # Session memory
├── config/
│   ├── settings.py          # All config loaded from .env
│   └── platform_utils.py   # OS-level utilities
├── skills/
│   ├── browser.py           # Playwright browser automation
│   ├── communication.py     # Email, Teams, LinkedIn, camera tools
│   ├── desktop.py           # pyautogui desktop interaction
│   ├── filesystem.py        # File tools (create_docx, etc.)
│   ├── media.py             # Video transcription, document extraction
│   ├── calendar_skill.py    # Google Calendar integration
│   └── uitars.py            # UI-TARS style desktop vision
├── tools/
│   └── registry.py          # Tool registry (all tools in one place)
├── sandbox/
│   └── executor.py          # Sandboxed code execution
├── memory/                  # SQLite checkpoint storage
├── AGENTS.md                # Agent rules and tool routing instructions
├── main.py                  # CLI entry point
├── setup_browser_session.py # One-time browser login setup
├── requirements.txt
└── .env                     # Your local configuration
```

## Requirements

### System Requirements
- Python 3.10 or higher
- Linux / macOS / Windows
- [Ollama](https://ollama.com) installed and running
- A webcam (optional, for camera/video features)
- `ffmpeg` (optional, for video recording/transcription)
- `fswebcam` on Linux (optional, for photo capture)

### Accounts Needed (for communication features)
- Microsoft account (for Outlook + Teams)
- Google account (for Gmail + Google Calendar)
- LinkedIn account

## Installation

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd AutonomousAgent
```

### Step 2 — Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Install Playwright and Chromium

```bash
playwright install chromium
```

### Step 5 — Install and start Ollama

Download from [https://ollama.com](https://ollama.com) and install it, then start the server:

```bash
ollama serve
```

### Step 6 — Pull the required models

Open a new terminal and run:

```bash
ollama pull qwen2.5-coder:7b
ollama pull llava:7b
```

> These models will be downloaded to your local machine. `qwen2.5-coder:7b` is ~4.7 GB and `llava:7b` is ~4.7 GB. Make sure you have enough disk space.

### Step 7 — Configure environment variables

Copy the `.env` file and update:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
LITELLM_MODEL=ollama/qwen2.5-coder:7b
VISION_MODEL=llava:7b
SANDBOX_WORKDIR=/tmp/autonomous_sandbox
SANDBOX_TIMEOUT=120
CHECKPOINT_DB_PATH=./memory/checkpoints.db
MAX_ITERATIONS=50
AGENTS_MD_PATH=./AGENTS.md
```

No changes are needed unless you want to use a different model or path.

### Step 8 — Set up browser session

This saves your login sessions for Outlook, Teams, Gmail, LinkedIn, and Google Calendar so the agent can use them without asking you to log in every time.

```bash
python setup_browser_session.py
```

A browser window will open with tabs for each service. Log in to all of them, then press **ENTER** in the terminal. Your session is saved to `~/.config/autonomous_agent_session.json`.

> You only need to do this once. Re-run it if your sessions expire.

## How to Run

### Interactive Chat Mode

```bash
python main.py chat
```

This starts an interactive session. Type your task and press Enter. Type `exit` or `quit` to end.

```
You: Send a good morning message to xyz on Teams
Agent: Message sent to xyz on Teams.

You: Write a Python calculator code with full-fledged UI using react and save it to ["Path"]
Agent: Files written: /home/user/Desktop/calculator.py

You: exit or ctrl+c
```

### Single Task Mode (non-interactive)

```bash
python main.py run "Send an email To John via Outlook and put CC xyz tell about the project update"
```

### Session Continuity (optional)

Use `--thread` to maintain memory across sessions:

```bash
python main.py chat --thread my-session
python main.py run "Summarize what we discussed" --thread my-session
```

## How It Works

1. You type a task in natural language
2. The agent enriches the task with routing hints (email vs code vs document)
3. The task is sent to `qwen2.5-coder:7b` running locally via Ollama
4. The model outputs JSON tool calls
5. The agent parses and executes each tool call
6. Results are fed back to the model for the next step
7. The loop continues until the task is complete (max 50 iterations)

For image/vision tasks (e.g. "redesign this page to match this image"), `llava:7b` is called to describe the reference image before the main model generates the code.

## Example Tasks

```
Send an email to xyz via Outlook with subject "Meeting Tomorrow" and a formal body
Schedule a Google Meet with team@example.com tomorrow at 3pm for 1 hour
Send a LinkedIn connection request to xyz at TechCorp
Create a full-fledged Python todo app and save it to my Desktop or /home/Desktop/project
Take a screenshot of my screen
Record a 30-second video from my webcam
Transcribe the video at /home/user/Videos/meeting.mp4
Create a Word document with a formal leave application and save to Desktop
Search the web for latest AI news and summarize it
Open VS Code
```

## Troubleshooting

**Ollama not running**
```bash
ollama serve
```

**Model not found**
```bash
ollama pull qwen2.5-coder:7b
ollama pull llava:7b
```

**Browser session expired (login required)**
```bash
python setup_browser_session.py
```

**Playwright not installed**
```bash
playwright install chromium
```

**Camera not working on Linux**
```bash
sudo apt install fswebcam ffmpeg
```

**Permission error on Linux for pyautogui**
```bash
sudo apt install python3-tk python3-dev
```

## Dependencies Overview

| Package | Purpose |
|---|---|
| `deepagents` | Core agent framework with built-in tools |
| `langgraph` | Multi-step agent execution graph |
| `langchain-ollama` | LangChain integration with Ollama |
| `litellm` | Unified LLM interface routing to Ollama |
| `ollama` | Python client for Ollama |
| `playwright` | Browser automation (Chromium) |
| `pyautogui` | Desktop mouse/keyboard control |
| `pillow` | Image processing |
| `opencv-python` | Computer vision for UI element detection |
| `faster-whisper` | Local video/audio transcription |
| `python-docx` | Create and read Word documents |
| `pypdf` | Extract text from PDF files |
| `openpyxl` | Read Excel files |
| `rich` | Beautiful terminal output |
| `typer` | CLI interface |
| `python-dotenv` | Load `.env` configuration |

## Notes

- All processing is fully local — no data is sent to any cloud service
- The agent uses a persistent Chromium browser session for all web-based tasks
- Memory is stored in a local SQLite database at `./memory/checkpoints.db`
- The `AGENTS.md` file contains the agent's rules and tool routing logic — edit it to customize behavior
- If you want to enhance performance further, use a **>7b** model.
