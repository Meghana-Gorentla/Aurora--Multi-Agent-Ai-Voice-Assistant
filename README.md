# Aurora — Multi-Agent AI Voice Assistant (Agno + FastAPI)

Aurora is a multi-personality AI voice assistant built with the Agno framework and served with FastAPI.
It dynamically routes each request to the correct domain expert agent at runtime and supports both text and voice interaction.

This project demonstrates multi-agent orchestration, domain-aware routing, and emotion-aware conversational responses.

---

## Paper

Aurora: A Multi-Personality AI Voice Assistant for Domain-Specific and Emotion-Aware Interactions  
IEEE Xplore: https://ieeexplore.ieee.org/document/11294651

---

## Features

- Agno multi-agent orchestration
- Domain classifier agent
- Manager / Orchestrator agent
- 4 domain experts
- General fallback agent
- Therapist hierarchical routing
- Voice pipeline (audio → STT → moderation → response → TTS)
- FastAPI backend
- SQLite storage
- Persona-based TTS

---

## Domains

healthcare → Urog  
tutor → Ravith  
therapist → Ojas  
finance → Artha  
general → fallback  

Therapist agent uses internal sub-routing.

---

## Architecture

```mermaid
flowchart TD
  U[User] --> API[FastAPI: /chat or /chat_audio]
  API --> MOD[Moderation]
  API --> MGR[ManagerAgent.run()]

  MGR --> CLF[Classifier Agent]
  CLF --> MGR

  MGR -->|single domain| EXP[Expert Agent]
  MGR -->|multi domain| SYN[Synthesis]

  EXP --> OUT[Response Text]

  OUT --> TTS[Edge TTS]
  TTS --> RET[Return text + audio + transcription]

  RET --> U
```

---

## Setup

Clone repo

```
git clone <your_repo_url>
cd multi-agent-assistant
```

Create virtual environment

```
python -m venv venv
```

Activate virtual environment

Windows

```
venv\Scripts\activate
```

Linux / Mac

```
source venv/bin/activate
```

Install dependencies

```
pip install -r requirements.txt
```

Create .env file in project root

```
multi-agent-assistant/.env
```

Add API key inside .env

```
GROQ_API_KEY=your_key_here
```

IMPORTANT

- Do NOT commit .env
- Add .env to .gitignore

Example .gitignore

```
venv/
.env
__pycache__/
tmp/
```

---

## Run Server

```
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open in browser

```
http://127.0.0.1:8000
```

---

## API Endpoints

POST /chat  
POST /chat/  
POST /chat_audio/  
GET /sessions/{user_id}  
GET /sessions/{user_id}/{session_id}/history  
PUT /sessions/{user_id}/{session_id}/name  

---

## Data / Files

SQLite database

```
tmp/agent.db
```

Temporary audio

```
tmp/audio/
```

These are created automatically.

---

## Domain Routing

Domains detected dynamically using classifier output

```
healthcare
tutor
therapist
finance
general
```

Therapist agent performs internal sub-classification without fine-tuning.

---

## Voice Pipeline

audio upload  
→ speech to text  
→ moderation  
→ manager agent  
→ expert agent  
→ text response  
→ text to speech  
→ return text + audio + transcription

---

## Security Notes

- API keys stored in .env
- Do not push secrets to GitHub
- SQLite used for local development
- Audio stored temporarily

---

## Author

Gorentla Sri Sai Meghana
