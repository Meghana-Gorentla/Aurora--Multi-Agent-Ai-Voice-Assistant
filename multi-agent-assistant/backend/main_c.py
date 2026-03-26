# backend/main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
from textwrap import dedent
from typing import Dict, Literal, Union, List, Optional
import sqlite3
import json
from datetime import datetime
import base64 

# Correct Agno Imports
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.models.groq import Groq
from agno.db.sqlite import SqliteDb

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware # Ensure this is imported

from .asr import transcribe_audio
from .tts import text_to_speech_stream

from .moderation import get_moderator

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables. Please set it in a .env file.")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") # Ensure this is in your .env
if not ELEVENLABS_API_KEY:
    raise ValueError("ELEVENLABS_API_KEY not found in environment variables. Please set it.")

DB_FILE = "tmp/agent.db"
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
os.makedirs("tmp/audio", exist_ok=True) 


app = FastAPI(title="Multi-Personality AI Assistant")

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Initialization for Chat Log (UPDATED SCHEMA) ---
def create_chat_log_table():
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                session_name TEXT, -- NEW: For custom session names
                role TEXT NOT NULL, -- 'user' or 'assistant'
                display_role TEXT NOT NULL, -- NEW: e.g., 'You', 'Urog (Healthcare)'
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                moderation_flagged BOOLEAN DEFAULT 0,
                moderation_result TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_log_user_session ON chat_log (user_id, session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_log_timestamp ON chat_log (timestamp);")
        conn.commit()
        print("Chat log table checked/created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating chat_log table: {e}")
    finally:
        if conn:
            conn.close()

@app.on_event("startup")
async def startup_event():
    create_chat_log_table()
    print("Initializing content moderation layer...")
    try:
        get_moderator()  # Initialize the moderator
        print("âœ“ Content moderation layer ready")
    except Exception as e:
        print(f"âš  Warning: Failed to initialize moderation layer: {e}")
        print("  Application will continue without content moderation.")


# --- Define Valid Domains & Personality Names ---
VALID_DOMAINS = Literal["healthcare", "tutor", "therapist", "finance", "general"]
DOMAIN_LIST = ["healthcare", "tutor", "therapist", "finance", "general"]

THERAPIST_SUB_DOMAINS = Literal["emotional_support", "cognitive_restructuring", "reflective_dialogue"]
THERAPIST_SUB_DOMAIN_LIST = ["emotional_support", "cognitive_restructuring", "reflective_dialogue"]

# NEW: Personality Names Mapping
PERSONALITY_NAMES = {
    "user": "You",
    "healthcare": "Urog (Healthcare)",
    "tutor": "Ravith (Tutor)",
    "therapist": "Ojas (Therapist)",
    "finance": "Artha (Finance)",
    "general": "Raahi (General)",
    "manager": "Nexus (Orchestrator)", # For the orchestrator agent itself
    "emotional_support": "Ojas (Emotional Support)",
    "cognitive_restructuring": "Ojas (Cognitive Restructuring)",
    "reflective_dialogue": "Ojas (Reflective Dialogue)",
}

# --- Agno Setup ---

groq_model = Groq(id="llama-3.1-8b-instant", api_key=GROQ_API_KEY)

agno_db = SqliteDb(db_file=DB_FILE, memory_table="user_memories")

# --- Define Agno Agents ---

# Define Agno Agents
classifier_agent = Agent(
    model=groq_model,
    instructions=dedent(f"""
        You are an expert intent classifier for a multi-personality AI system named Nexus.
        Your ONLY task is to determine the primary domain(s) of the user's query from the following list of EXACT words: {', '.join(DOMAIN_LIST)}.

        Rules for classification:
        1.  **Prioritize Specific Domains**: Always try to classify the query into one or more of the specific domains first: 'healthcare', 'tutor', 'therapist', 'finance'.
        2.  **Combine Domains**: If a query clearly spans multiple specific domains, list all relevant ones, separated by commas (e.g., 'finance, therapist').
        3.  **Strictly General**: Only use 'general' as a domain if the query *does not clearly fit* into any of the specific domains, or if it's a very broad, conversational, or non-domain-specific interaction (e.g., greetings, small talk, general knowledge questions outside the scope of the specific experts).
        4.  **Single Word/Comma-separated Response**: You MUST respond with *ONLY* the single most relevant domain word, or a comma-separated list of relevant domain words.
        5.  **No Extraneous Text**: Do NOT include any other text, punctuation, greetings, explanations, conversation, or extraneous characters. Your response must be *only* the listed words.
        6.  **No Invention**: You are NOT allowed to invent new domains or refuse to classify. If no clear specific domain is found, you MUST respond with 'general'.

        Examples:
        User: How do I calculate interest on a loan?
        Response: finance

        User: I'm feeling down lately.
        Response: therapist

        User: What are symptoms of flu?
        Response: healthcare

        User: Explain quantum physics to me.
        Response: tutor

        User: I'm stressed about my finances and need coping strategies.
        Response: finance, therapist

        User: What are symptoms of flu and how can I explain them to a child?
        Response: healthcare, tutor

        User: Hello, how are you?
        Response: general

        User: Tell me a joke.
        Response: general

        User: What is the capital of France?
        Response: general

        User: help me learn photosynthesis
        Response: tutor

        User: How do banks work?
        Response: finance

        User: I need to understand my feelings.
        Response: therapist
    """),
    markdown=False,
)

healthcare_expert = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a highly knowledgeable Healthcare Expert named Urog. Provide accurate, helpful, and
        easy-to-understand information about health conditions, symptoms, preventive care,
        and general medical knowledge. Always advise the user to consult a qualified healthcare
        professional for personalized medical advice, diagnosis, or treatment.
        Do NOT provide medical diagnoses or prescribe treatments yourself.
        Maintain a compassionate and informative tone. Focus on providing general health education.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

tutor_expert = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a patient and knowledgeable Tutor named Ravith. Your role is to explain concepts
        clearly, break down complex topics, and guide users through learning processes.
        Encourage understanding through examples and step-by-step explanations.
        Focus on educational content across various subjects.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

finance_expert = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a knowledgeable Finance Expert named Artha. Provide information on personal finance,
        investing basics, budgeting, loans, and general economic concepts.
        Always advise the user to consult a certified financial advisor for personalized
        financial planning or investment decisions. Do NOT provide specific financial advice
        or act as a broker. Focus on providing general financial education and guidance.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

# NEW: General Agent (Raahi)
raahi_general_agent = Agent(
    model=groq_model,
    instructions=dedent("""
        You are Raahi, a friendly and helpful general-purpose AI assistant. Your role is to
        engage in casual conversation, answer simple questions, provide encouraging remarks,
        or guide users if their query doesn't fit into a specific domain. Maintain a friendly
        and conversational tone. If a query is very vague or out of scope, you can politely
        ask for clarification or suggest topics related to the specialized domains (healthcare,
        tutor, therapist, finance).
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

therapist_sub_classifier = Agent(
    model=groq_model,
    instructions=dedent(f"""
        You are an expert sub-classifier for the Therapist domain. Your ONLY task is to determine the
        most appropriate therapeutic approach for the user's statement from the following EXACT words:
        {', '.join(THERAPIST_SUB_DOMAIN_LIST)}.
        You MUST respond with *ONLY* the single most relevant sub-domain word.
        Do NOT include any other text, punctuation, greetings, explanations, conversation,
        or extraneous characters. Your response must be *only* one of the listed words.
        If the query does not clearly fit one of the sub-domains, you MUST respond with the sub-domain that is the *closest* fit.
        You are NOT allowed to invent new sub-domains or refuse to classify.
    """),
    markdown=False,
)

emotional_support_agent = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a compassionate Emotional Support Agent named Ojas. Your primary role is to provide
        empathy, validation, and comfort to the user. Acknowledge their feelings, offer
        reassurance, and create a safe space for them to express themselves.
        Focus on active listening and supportive statements. Do NOT offer advice, diagnoses,
        or complex strategies.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

cognitive_restructuring_agent = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a Cognitive Restructuring Agent named Ojas, specializing in helping users identify and
        reframe negative or unhelpful thought patterns (similar to CBT). Your goal is to
        gently challenge distorted thinking, encourage alternative perspectives, and guide
        users toward more balanced thoughts. Use questioning techniques to prompt
        self-reflection on thoughts. Do NOT invalidate feelings.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

reflective_dialogue_agent = Agent(
    model=groq_model,
    instructions=dedent("""
        You are a Reflective Dialogue Agent named Ojas. Your purpose is to facilitate deep self-reflection
        and insight for the user by asking thoughtful, open-ended questions. Encourage the user
        to explore their emotions, motivations, and experiences in more depth.
        Focus on asking "why," "how," and "what" questions that prompt deeper consideration.
        Do NOT offer direct solutions or interpretations.
    """),
    db=agno_db, update_memory_on_run=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=False,
    markdown=True,
)

class TherapistExpert(Agent):
    def __init__(self, model, db, sub_classifier, sub_agents: Dict[str, Agent]):
        super().__init__(
            model=model,
            instructions=dedent("""
                You are a versatile Therapist AI named Ojas, capable of providing emotional support,
                assisting with cognitive restructuring, and facilitating reflective dialogue.
                You understand the nuance of mental health conversations and route queries
                to your specialized internal sub-personalities as needed.
                Always encourage seeking professional help for serious mental health concerns.
                Do NOT diagnose or provide clinical therapy.
            """),
            db=db,
            update_memory_on_run=True,
            add_history_to_context=True,
            num_history_runs=3,
            enable_user_memories=False,
            markdown=True,
        )
        self.sub_classifier = sub_classifier
        self.sub_agents = sub_agents

    def run(self, message: str, user_id: str, session_id: str, stream: bool = False) -> Dict:
        print(f"\n--- Therapist Internal Sub-Classification ---")
        print(f"Therapist: Sub-classifying message: '{message}'")
        
        sub_classification_prompt = f"Categorize this statement for a therapeutic approach: {message}"
        sub_classifier_response: RunOutput = self.sub_classifier.run(
            sub_classification_prompt,
            user_id=user_id,
            session_id=session_id,
            stream=False
        )
        
        classified_sub_domain = sub_classifier_response.content.strip().lower()
        print(f"Therapist Sub-Classifier raw output: '{sub_classifier_response.content}' -> Cleaned: '{classified_sub_domain}'")

        if classified_sub_domain not in THERAPIST_SUB_DOMAIN_LIST:
            print(f"Warning: Therapist sub-classifier outputted an unexpected sub-domain: '{classified_sub_domain}'. Falling back to emotional_support.")
            target_sub_agent = self.sub_agents["emotional_support"]
            actual_sub_agent_used = "emotional_support (fallback)"
        else:
            target_sub_agent = self.sub_agents[classified_sub_domain]
            actual_sub_agent_used = classified_sub_domain
        
        print(f"Therapist routing to sub-agent: '{actual_sub_agent_used}' (Instructions start: '{target_sub_agent.instructions.splitlines()[0]}')")

        final_sub_agent_response: RunOutput = target_sub_agent.run(
            message,
            user_id=user_id,
            session_id=session_id,
            stream=stream
        )
        
        return {
            "content": final_sub_agent_response.content,
            "sub_agent_used": actual_sub_agent_used,
            "run_id": final_sub_agent_response.run_id,
            "agent_id": final_sub_agent_response.agent_id,
            "session_id": final_sub_agent_response.session_id,
        }

expert_agents: Dict[str, Agent] = {
    "healthcare": healthcare_expert,
    "tutor": tutor_expert,
    "therapist": TherapistExpert(
        model=groq_model,
        db=agno_db,
        sub_classifier=therapist_sub_classifier, # This is the sub-classifier for the TherapistExpert
        sub_agents={
            "emotional_support": emotional_support_agent,
            "cognitive_restructuring": cognitive_restructuring_agent,
            "reflective_dialogue": reflective_dialogue_agent,
        }
    ),
    "finance": finance_expert,
    "general": raahi_general_agent,
}

# Helper to determine display role based on agent response details
def get_display_role_from_agent_response(classified_domain: str, agent_used_raw: str, sub_agent_used: Optional[str] = None) -> str:
    if 'Orchestrated' in agent_used_raw:
        # e.g., "Manager (Orchestrated: healthcare, tutor)"
        try:
            orchestrated_domains_str = agent_used_raw.split("Orchestrated:")[1].split(')')[0].strip()
            orchestrated_domains = [d.strip().split(' ')[0] for d in orchestrated_domains_str.split(',')] # split off '(fallback)'
            display_parts = [PERSONALITY_NAMES.get(d, d.capitalize()) for d in orchestrated_domains if d in PERSONALITY_NAMES]
            if not display_parts:
                return PERSONALITY_NAMES['manager'] # Fallback if specific domains not found
            return f"{PERSONALITY_NAMES['manager']} ({' & '.join(display_parts)})"
        except Exception as e:
            print(f"Error parsing orchestrated agent_used: {e}. Raw: {agent_used_raw}")
            return PERSONALITY_NAMES['manager']
    elif 'therapist' in agent_used_raw and sub_agent_used:
        # e.g., "therapist (emotional_support)"
        return PERSONALITY_NAMES.get(sub_agent_used, PERSONALITY_NAMES['therapist'])
    elif classified_domain:
        # For single-domain agents (healthcare, tutor, finance, general)
        primary_domain = classified_domain.split(',')[0].strip() # If somehow multiple, take first
        return PERSONALITY_NAMES.get(primary_domain, "Assistant")
    
    return "Assistant" # Default fallback


class ManagerAgent(Agent):
    def __init__(self, model, db, expert_agents: Dict[str, Agent], classifier_agent: Agent): # ADD classifier_agent parameter
        super().__init__(
            model=model,
            instructions=dedent(f"""
                You are the central Manager and Orchestrator of a multi-personality AI system, named Nexus.
                Your primary role is to understand the user's overall intent and delegate
                the query to the most appropriate expert agent(s).

                When a user sends a query, you will follow these steps:
                1.  **Identify Relevant Domains**: Determine ALL relevant domains from the following list: {', '.join(DOMAIN_LIST)}.
                    If a query clearly belongs to only one domain, just list that one.
                    If it touches upon multiple domains, list all of them, separated by commas.
                    If no clear domain is found, respond with 'general'.
                    Example 1: "How do I start investing?" -> "finance"
                    Example 2: "I'm stressed about my finances and need coping strategies." -> "finance, therapist"
                    Example 3: "What are symptoms of flu and how can I explain them to a child?" -> "healthcare, tutor"
                    Example 4: "Hello, how are you today?" -> "general"
                    Your response for this step MUST be ONLY the comma-separated domain names.

                2.  **Gather Information**: For each identified domain, formulate a specific sub-query
                    for the respective expert agent to answer. Get the responses from all relevant agents.

                3.  **Synthesize Response**: Combine the information received from all expert agents into a
                    single, comprehensive, cohesive, and natural-sounding answer for the user.
                    Ensure smooth transitions between different expert insights.
                    Address all parts of the original user's query.
                    If no specific expert response is available (e.g., fallback occurred), state that gracefully.
                    Prioritize clarity, helpfulness, and completeness.
            """),
            db=db,
            update_memory_on_run=True,
            add_history_to_context=True,
            num_history_runs=5,
            enable_user_memories=False,
            markdown=True,
        )
        self.expert_agents = expert_agents
        self.classifier_agent = classifier_agent # Store the classifier agent


    def run(self, message: str, user_id: str, session_id: str, stream: bool = False) -> Dict:
        print(f"\n--- Manager Agent Orchestration (Multi-Agent) ---")
        print(f"Manager received query: '{message}'")

        # Step 1: Manager identifies relevant domains using its own reasoning
        print(f"Manager determining relevant domains for: '{message}'")
        domain_identification_prompt = (
            f"Given the user's query: '{message}', which of the following expert domains are relevant? "
            f"List them as comma-separated values. Only use domains from: {', '.join(DOMAIN_LIST)}. "
            "Respond with ONLY the comma-separated domain names (e.g., 'finance, therapist, general')."
        )

        domain_response: RunOutput = self.classifier_agent.run( # CORRECTED: Use self.classifier_agent
            domain_identification_prompt,
            user_id=user_id,
            session_id=session_id,
            stream=False
        )

        relevant_domains_str = domain_response.content.strip().lower()
        relevant_domains = [
            d.strip() for d in relevant_domains_str.split(',') if d.strip() in DOMAIN_LIST
        ]
        
        # NEW: Fallback to General Agent if no specific domains identified
        if not relevant_domains or ("general" in relevant_domains and len(relevant_domains) == 1):
            print(f"Manager identified general domain or no valid domains for '{relevant_domains_str}'. Routing to Raahi (General) agent.")
            # Ensure only "general" is the domain to avoid confusion if other invalid domains were present
            relevant_domains = ["general"] 
            
            general_agent_response = self.expert_agents["general"].run(
                message,
                user_id=user_id,
                session_id=session_id,
                stream=stream
            )
            
            display_role = PERSONALITY_NAMES['general']
            
            return {
                "response": general_agent_response.content,
                "classified_domain": "general",
                "agent_used": f"general", # Simplified for clarity
                "run_id": general_agent_response.run_id,
                "agent_id": self.agent_id,
                "session_id": session_id,
                "display_role": display_role # Pass display role to frontend
            }

        print(f"Manager identified relevant domains: {relevant_domains}")

        # Step 2: Gather Information from relevant expert agents
        expert_responses = {}
        agents_involved_details = []

        for domain in relevant_domains:
            if domain in self.expert_agents:
                expert_agent = self.expert_agents[domain]
                print(f"Manager querying '{domain}' agent with original message: '{message}'")
                
                raw_expert_response = expert_agent.run(
                    message,
                    user_id=user_id,
                    session_id=session_id,
                    stream=False
                )

                content = ""
                agent_path_detail = domain
                
                if isinstance(raw_expert_response, dict):
                    content = raw_expert_response.get('content', '')
                    sub_agent = raw_expert_response.get('sub_agent_used', 'unknown_sub_agent')
                    agent_path_detail = f"{domain} ({sub_agent})" if sub_agent != 'unknown_sub_agent' else domain
                elif isinstance(raw_expert_response, RunOutput):
                    content = raw_expert_response.content
                
                expert_responses[domain] = content
                agents_involved_details.append(agent_path_detail)
            else:
                print(f"Warning: Manager identified domain '{domain}' but no expert agent found for it.")
                expert_responses[domain] = f"No expert found for {domain}."
                agents_involved_details.append(f"{domain} (missing expert)")

        # Step 3: Synthesize Response using the Manager's own LLM capabilities
        print(f"Manager synthesizing response from {agents_involved_details}...")
        synthesis_prompt = dedent(f"""
            The user's original query was: "{message}"

            Here are insights from relevant expert agents:
            {chr(10).join([f"- {d.capitalize()}: {resp}" for d, resp in expert_responses.items()])}

            Synthesize these insights into a single, comprehensive, cohesive, and natural-sounding answer
            for the user. Ensure you address all parts of the original query, drawing from the provided
            expert insights. Maintain a helpful and professional tone.
        """)

        final_synthesis_response: RunOutput = super().run( # Manager uses its own instructions for synthesis
            synthesis_prompt,
            user_id=user_id,
            session_id=session_id,
            stream=False
        )
        
        # Determine display role for the synthesized response
        display_role = get_display_role_from_agent_response(
            classified_domain=", ".join(relevant_domains),
            agent_used_raw="Manager (Orchestrated: " + ", ".join(agents_involved_details) + ")",
            sub_agent_used=None # Sub-agent only relevant for direct Therapist calls
        )

        return {
            "response": final_synthesis_response.content,
            "classified_domain": ", ".join(relevant_domains) if relevant_domains else "N/A",
            "agent_used": "Manager (Orchestrated: " + ", ".join(agents_involved_details) + ")",
            "run_id": final_synthesis_response.run_id,
            "agent_id": self.agent_id,
            "session_id": session_id,
            "display_role": display_role, # Pass display role to frontend
            "transcription": None 
        }

manager_agent = ManagerAgent(
    model=groq_model,
    db=agno_db,
    expert_agents=expert_agents,
    classifier_agent=classifier_agent # PASS THE CLASSIFIER AGENT HERE
)

# --- Pydantic Models (UPDATED) ---

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    session_name: Optional[str] = None # NEW: For initial session creation if name is provided

class SessionSummary(BaseModel):
    session_id: str
    session_name: Optional[str] = None # NEW: Optional session name
    last_message_preview: str
    timestamp: str

class MessageEntry(BaseModel):
    role: str # 'user' or 'assistant'
    display_role: str # NEW: e.g., 'You', 'Urog (Healthcare)'
    content: str
    timestamp: str

class UpdateSessionNameRequest(BaseModel): # NEW: For updating session names
    new_name: str

# --- FastAPI Endpoints ---

@app.post("/chat/")
@app.post("/chat")
def chat(request: ChatRequest):
    user_id = request.user_id
    session_id = request.session_id
    user_message = request.message
    initial_session_name = request.session_name 

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check user input for toxic content
        moderator = get_moderator()
        user_moderation = moderator.check_toxicity(user_message)
        
        # Log user message (always log, even if blocked)
        cursor.execute(
            "INSERT INTO chat_log (user_id, session_id, session_name, role, display_role, content, moderation_flagged, moderation_result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, session_id, initial_session_name, "user", PERSONALITY_NAMES["user"], user_message, 
             user_moderation['is_toxic'], json.dumps(user_moderation))
        )
        conn.commit()

        # Initialize variables
        assistant_response_content = ""
        assistant_display_role = "System"
        classified_domain = "moderation"
        agent_used = "Content Moderation System"
        moderation_blocked = False
        
        # Handle blocked user input
        if user_moderation['action'] == 'block':
            assistant_response_content = "⚠️ I apologize, but your message contains content that violates our content policy."
            moderation_blocked = True
            
            # Log the moderation response
            cursor.execute(
                "INSERT INTO chat_log (user_id, session_id, session_name, role, display_role, content, moderation_flagged, moderation_result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, session_id, None, "assistant", assistant_display_role, assistant_response_content,
                 True, json.dumps({"action": "block", "reason": "User input blocked"}))
            )
            conn.commit()
            
            # Return early, but AFTER logging
            return {
                "response": assistant_response_content,
                "classified_domain": classified_domain,
                "agent_used": agent_used,
                "display_role": assistant_display_role,
                "audio_base64": None,
                "transcription": user_message,
                "moderation_blocked": moderation_blocked,
                "moderation_reason": "User input flagged as toxic",
                "moderation_flagged": True
            }

        # Process message with manager agent (only if not blocked)
        response_from_manager = manager_agent.run(
            user_message,
            user_id=user_id,
            session_id=session_id,
            stream=False
        )

        assistant_response_content = response_from_manager.get("response", "No response content.")
        assistant_display_role = response_from_manager.get("display_role", "Assistant")
        classified_domain = response_from_manager.get("classified_domain", "N/A")
        agent_used = response_from_manager.get("agent_used", "N/A")

        # Check agent response for toxicity
        agent_moderation = moderator.check_toxicity(assistant_response_content)

        if agent_moderation['action'] == 'block':
            # Replace toxic response with safe message
            assistant_response_content = (
                "I apologize, but I cannot provide that response as it may contain "
                "content that violates our safety policies."
            )
            agent_moderation['is_toxic'] = True
            moderation_blocked = True

        # Generate TTS audio with error handling
        audio_base64 = None
        try:
            tts_audio_stream = text_to_speech_stream(assistant_response_content, persona="general")
            audio_base64 = base64.b64encode(tts_audio_stream.read()).decode('utf-8')
        except Exception as e:
            print(f"TTS generation failed: {e}")
            print("Continuing without audio...")
            audio_base64 = None

        # Log assistant response (always, whether blocked or not)
        cursor.execute(
            "INSERT INTO chat_log (user_id, session_id, session_name, role, display_role, content, moderation_flagged, moderation_result) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, session_id, None, "assistant", assistant_display_role, assistant_response_content,
             agent_moderation['is_toxic'], json.dumps(agent_moderation))
        )
        conn.commit()

        # Final response to frontend
        return {
            "response": assistant_response_content,
            "classified_domain": classified_domain,
            "agent_used": agent_used,
            "display_role": assistant_display_role,
            "audio_base64": audio_base64,
            "transcription": user_message,
            "moderation_blocked": moderation_blocked,
            "moderation_flagged": user_moderation['is_toxic'] or agent_moderation['is_toxic']
        }

    except Exception as e:
        print(f"Error processing chat in main endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}. Please try again.")
    finally:
        if conn:
            conn.close()
            
@app.post("/chat_audio/")
async def chat_audio(
    audio_file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    session_name: Optional[str] = Form(None)
):
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Save audio
        audio_path = f"tmp/audio/{audio_file.filename}"
        with open(audio_path, "wb") as f:
            f.write(await audio_file.read())

        # Transcribe
        transcription_result = transcribe_audio(audio_path)
        user_message_text = transcription_result.get("transcription", "")
        if not user_message_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio.")

        os.remove(audio_path)

        # Log user message
        cursor.execute(
            "INSERT INTO chat_log (user_id, session_id, session_name, role, display_role, content) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, session_id, session_name, "user", PERSONALITY_NAMES["user"], user_message_text)
        )
        conn.commit()

        # Run through manager agent (instead of undefined multi_personality_coordinator)
        response_from_manager = manager_agent.run(
            user_message_text,
            user_id=user_id,
            session_id=session_id,
            stream=False
        )

        assistant_response_content = response_from_manager.get("response", "No response content.")
        assistant_display_role = response_from_manager.get("display_role", "Assistant")

        audio_base64 = None

        try:
            tts_audio_stream = text_to_speech_stream(assistant_response_content, persona="general")
            audio_base64 = base64.b64encode(tts_audio_stream.read()).decode('utf-8')
        except Exception as tts_error:
            print(f"TTS Error (ElevenLabs) in /chat_audio/: {tts_error}")
            print("Continuing without audio...")
            audio_base64 = None
            # Don't fail - just continue without audio

        # Log assistant response
        cursor.execute(
            "INSERT INTO chat_log (user_id, session_id, session_name, role, display_role, content) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, session_id, None, "assistant", assistant_display_role, assistant_response_content)
        )
        conn.commit()

        return {
            "response": assistant_response_content,
            "classified_domain": response_from_manager.get("classified_domain", "N/A"),
            "agent_used": response_from_manager.get("agent_used", "N/A"),
            "display_role": assistant_display_role,
            "audio_base64": audio_base64
        }

    except Exception as e:
        print(f"Error in /chat_audio/: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")
    finally:
        if conn:
            conn.close()



@app.get("/sessions/{user_id}", response_model=List[SessionSummary])
async def get_user_sessions(user_id: str):
    """
    Retrieves all unique session IDs for a given user from the chat_log,
    along with a preview of the last message, its timestamp, and its name.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # UPDATED QUERY: Fetch session_name from the first message if available
        query = """
        SELECT
            c1.session_id,
            c1.content,
            c1.timestamp,
            (SELECT session_name FROM chat_log WHERE user_id = c1.user_id AND session_id = c1.session_id AND session_name IS NOT NULL ORDER BY timestamp ASC LIMIT 1) as session_name
        FROM
            chat_log AS c1
        INNER JOIN (
            SELECT
                session_id,
                MAX(timestamp) AS max_timestamp
            FROM
                chat_log
            WHERE
                user_id = ?
            GROUP BY
                session_id
        ) AS c2
        ON c1.session_id = c2.session_id AND c1.timestamp = c2.max_timestamp
        WHERE
            c1.user_id = ?
        ORDER BY
            c1.timestamp DESC;
        """
        
        cursor.execute(query, (user_id, user_id))
        
        sessions = []
        for row in cursor.fetchall():
            session_id, last_message_content, timestamp, session_name = row
            content_str = str(last_message_content) if last_message_content else ""
            sessions.append(SessionSummary(
                session_id=session_id,
                session_name=session_name, # Pass the fetched name
                last_message_preview=content_str[:50] + "..." if len(content_str) > 50 else content_str,
                timestamp=timestamp
            ))
        return sessions
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred processing history: {e}")
    finally:
        if conn:
            conn.close()

@app.get("/sessions/{user_id}/{session_id}/history", response_model=List[MessageEntry])
async def get_session_history(user_id: str, session_id: str):
    """
    Retrieves the complete chat history for a specific user and session from the chat_log.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # UPDATED QUERY: Fetch display_role
        query = """
        SELECT
            role,
            display_role, -- NEW: Fetch display_role
            content,
            timestamp
        FROM
            chat_log
        WHERE
            user_id = ? AND session_id = ?
        ORDER BY
            timestamp ASC;
        """
        
        cursor.execute(query, (user_id, session_id))
        
        history = []
        for row in cursor.fetchall():
            role, display_role, content, timestamp = row # Unpack display_role
            history.append(MessageEntry(
                role=role,
                display_role=display_role, # Pass display_role
                content=content,
                timestamp=timestamp
            ))
        return history
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred processing history: {e}")
    finally:
        if conn:
            conn.close()

# NEW: Endpoint to update session name
@app.put("/sessions/{user_id}/{session_id}/name")
async def update_session_name_endpoint(user_id: str, session_id: str, request: UpdateSessionNameRequest):
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Update session_name for the first user message in that session
        # This ensures the name is stored with the user's initial message
        cursor.execute(
            """
            UPDATE chat_log
            SET session_name = ?
            WHERE user_id = ? AND session_id = ? AND role = 'user'
            AND id = (SELECT MIN(id) FROM chat_log WHERE user_id = ? AND session_id = ?);
            """,
            (request.new_name, user_id, session_id, user_id, session_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            # This might happen if session doesn't exist or no user message in it
            raise HTTPException(status_code=404, detail="Session not found or no user message to update name.")
        return {"message": "Session name updated successfully"}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

@app.get("/favicon.ico")
async def favicon():
    favicon_path = "frontend/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        raise HTTPException(status_code=404, detail="Favicon not found")

# Serve Static Files (Frontend) - Must be at the end
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)