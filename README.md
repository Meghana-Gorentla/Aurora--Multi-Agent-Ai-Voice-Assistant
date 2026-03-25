Aurora — Multi‑Agent AI Voice Assistant (Agno)
Overview
Aurora is a multi‑personality AI voice assistant built with the Agno framework and served via FastAPI. The system dynamically routes each user query to the most relevant domain expert(s) at runtime (without extensive fine‑tuning for routing).

It supports:

Text chat (POST /chat)
Voice input: audio upload → speech‑to‑text (STT) → routed expert response (POST /chat_audio/)
Text‑to‑speech (TTS) responses with domain/persona voice selection
Session history saved in SQLite
A simple web UI served as static files
Reference Paper
This project is based on the published work:

“Aurora: A Multi-Personality AI Voice Assistant for Domain-Specific and Emotion-Aware Interactions”
IEEE Xplore: https://ieeexplore.ieee.org/document/11294651

Key Idea: Agno Multi‑Agent Personalities
The backend uses Agno to define:

A domain classifier agent that outputs only one or more domain keywords
A manager/orchestrator agent that delegates the request to the appropriate domain expert(s)
Four domain expert agents:
healthcare (Urog)
tutor (Ravith)
therapist (Ojas, with extra hierarchical sub‑routing)
finance (Artha)
A general fallback expert for out‑of‑domain / broad queries
Dynamic Domain Identification (No Hard-coded Intent Rules)
Instead of hard-coded if/else rules, routing is driven by:

classifier_agent: constrained to output only valid domain keywords from the list.
ManagerAgent.run():
If one domain is selected: route directly to that expert
If multiple domains are selected: query multiple experts and synthesize a final answer
Therapist Hierarchy (Sub‑domains)
The therapist expert is hierarchical:

A therapist sub-classifier chooses one therapeutic approach from:
emotional_support
cognitive_restructuring
reflective_dialogue
The therapist expert then routes to the chosen therapist sub-agent.
Architecture (End-to-End Flow)
Text Chat Flow (POST /chat)
POST /chat
1 domain
multiple
User
FastAPI chat()
Moderation check
Log user message to SQLite
ManagerAgent.run()
classifier_agent.run() -> domain keywords
Select expert from expert_agents
Query multiple experts
Manager synthesis -> final response
Expert response
Edge TTS (persona selected by classified domain)
Return response + audio_base64 + transcription
Voice Chat Flow (POST /chat_audio/)
POST /chat_audio/ (audio)
1 domain
multiple
User
FastAPI chat_audio()
transcribe_audio()
Moderation check on transcription
Log transcription to SQLite
ManagerAgent.run()
classifier_agent.run() -> domain keywords
Select expert
Query multiple experts
Manager synthesis
Assistant response text
Edge TTS (persona chosen from domain)
Return response + audio_base64 + transcription
Project Layout (Most Relevant Files)
multi-agent-assistant/backend/main.py
FastAPI server
Agno agent definitions (classifier, manager, experts)
Endpoints: /chat, /chat_audio/, session APIs
Serves the UI frontend static files
multi-agent-assistant/frontend/
index.html (UI)
script.js (frontend logic: text + voice, rendering chat)
style.css (UI styling)
multi-agent-assistant/requirements.txt
Python dependencies
Requirements
Python
A working virtual environment
API credentials:
GROQ_API_KEY required (used for Agno/Groq model calls)
Setup (Local Development)
1) Create/activate virtual environment
From repo root (adjust as needed):

cd "d:\Aurora- Intelligence in every voice\Codebase"
.\venv\Scripts\Activate.ps1
2) Install dependencies
From: d:\Aurora- Intelligence in every voice\Codebase\multi-agent-assistant

pip install -r requirements.txt
3) Configure environment variables
Create a .env file in: multi-agent-assistant/
Example:

GROQ_API_KEY=your_key_here
Do not commit .env.

Run the Application
From: d:\Aurora- Intelligence in every voice\Codebase\multi-agent-assistant

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
Open:

http://127.0.0.1:8000
The backend serves the frontend at / (static files).

How to Use (UI)
Enter a User ID
Click Load Sessions (optional) or New Chat
For text: type in the textarea and press →
For voice:
click the 🎤 record button
speak
stop recording
the UI displays:
your transcribed text
assistant response + audio controls (when audio is available)
API Endpoints
Text Chat
POST /chat
POST /chat/
Body fields:
user_id (string)
session_id (string)
message (string)
session_name (optional)
Behavior

logs user message to SQLite
routes through classifier → manager → expert
returns:
response (assistant text)
audio_base64 (TTS audio)
transcription (echo of user text)
classified_domain, agent_used, moderation fields
Voice Chat
POST /chat_audio/
Multipart form:
audio_file (webm)
user_id (string)
session_id (string)
session_name (optional)
Behavior

saves upload → STT transcription → moderation → routing → expert response
returns:
response
audio_base64
transcription (recognized user speech text)
classified_domain, agent_used, moderation fields
Session APIs
GET /sessions/{user_id}
list sessions + metadata
GET /sessions/{user_id}/{session_id}/history
list message history
PUT /sessions/{user_id}/{session_id}/name
rename a session
Data Storage
SQLite DB file (created/used by backend): tmp/agent.db
Temporary audio files: stored under tmp/audio/ during voice requests
Adding or Extending Domains (Dynamic Routing)
To add a new top-level domain:

Add the keyword to DOMAIN_LIST in backend/main.py
Create a new Agno expert Agent for that domain
Register it in expert_agents: Dict[str, Agent]
The router remains the same: the classifier outputs domain keywords and the manager delegates using the updated expert_agents registry.

Troubleshooting
“GROQ_API_KEY not found”
Ensure your .env is in multi-agent-assistant/
Restart the server after setting it
Mod or Transformers warning / moderation disabled
The server tries to initialize moderation on startup. If moderation dependencies are missing, it may continue with moderation disabled (audio/chat still works).

Frontend changes not showing
Browser caching is common:

Hard refresh (Ctrl+F5)
Or open the UI in a private/incognito window
License
Add your preferred license (e.g., MIT, Apache-2.0) if you plan to publish this repository.

If you want, tell me what license you prefer (MIT/Apache/GPL/none) and whether your preferred repo root is Codebase/ or multi-agent-assistant/; I can tailor the README so the “Run” and “Project Layout” sections match your exact push layout.

