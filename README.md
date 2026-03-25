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
