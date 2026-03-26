import os
from typing import IO
from io import BytesIO
import asyncio
from dotenv import load_dotenv

# Use Google TTS (more reliable)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️ gTTS not available - install: pip install gtts")

# Fallback: pyttsx3 (offline)
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

load_dotenv()

# Persona voice settings for gTTS
# Persona voice settings for gTTS
PERSONA_GTTS_SETTINGS = {
    # Therapist - Warm, empathetic, slightly slower for calming effect
    "therapist": {
        "lang": "en", 
        "tld": "com",      # American English (warm, conversational)
        "slow": False      # ✅ Normal speed (slow=True is too robotic)
    },
    
    # Tutor - Clear, educational, energetic
    "tutor": {
        "lang": "en", 
        "tld": "co.in",    # Indian English (clear enunciation, good for teaching)
        "slow": False
    },
    
    # Healthcare - Professional, calm, authoritative
    "healthcare": {
        "lang": "en", 
        "tld": "co.uk",    # British English (professional, trustworthy)
        "slow": False
    },
    
    # Finance - Confident, businesslike, direct
    "finance": {
        "lang": "en", 
        "tld": "com.au",   # Australian English (confident, direct)
        "slow": False
    },
    
    # General - Friendly, versatile, neutral
    "general": {
        "lang": "en", 
        "tld": "com",      # American English (neutral, friendly)
        "slow": False
    },
    
    # Coordinator - Commanding, efficient
    "coordinator": {
        "lang": "en", 
        "tld": "ca",       # Canadian English (clear, neutral authority)
        "slow": False
    },
    
    # Emotional Support - Gentle, compassionate (therapist sub-personality)
    "emotional_support": {
        "lang": "en", 
        "tld": "ie",       # Irish English (warm, gentle tone)
        "slow": False
    },
    
    # Cognitive Restructuring - Thoughtful, measured (therapist sub-personality)
    "cognitive_restructuring": {
        "lang": "en", 
        "tld": "co.uk",    # British English (analytical, measured)
        "slow": False
    },
    
    # Reflective Dialogue - Contemplative, patient (therapist sub-personality)
    "reflective_dialogue": {
        "lang": "en", 
        "tld": "co.za",    # South African English (thoughtful, unique)
        "slow": False
    },
}

async def generate_tts_gtts(text: str, persona: str = "general") -> BytesIO:
    """Google TTS - Works when Edge TTS fails"""
    try:
        if not GTTS_AVAILABLE:
            raise Exception("gTTS not available")
        
        settings = PERSONA_GTTS_SETTINGS.get(persona, {"lang": "en", "tld": "com", "slow": False})
        
        print(f"🎤 Using Google TTS: persona={persona}, len={len(text)}")
        
        # Generate TTS
        tts = gTTS(text=text, lang=settings["lang"], tld=settings["tld"], slow=settings["slow"])
        
        # Save to BytesIO
        audio_stream = BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        
        print(f"✅ Google TTS success: {audio_stream.tell()} bytes")
        return audio_stream
        
    except Exception as e:
        print(f"❌ Google TTS failed: {e}")
        raise

def generate_tts_pyttsx3(text: str, persona: str = "general") -> BytesIO:
    """Offline fallback - Always works"""
    try:
        if not PYTTSX3_AVAILABLE:
            raise Exception("pyttsx3 not available")
        
        print(f"🎤 Using pyttsx3 (offline): len={len(text)}")
        
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        # Female personas
        female_personas = ["therapist", "healthcare", "general", "emotional_support", "cognitive_restructuring", "reflective_dialogue"]
        
        if persona in female_personas and len(voices) > 1:
            engine.setProperty('voice', voices[1].id)
        elif len(voices) > 0:
            engine.setProperty('voice', voices[0].id)
        
        # Adjust rate
        rate = engine.getProperty('rate')
        if persona in ["therapist", "emotional_support", "reflective_dialogue"]:
            engine.setProperty('rate', rate - 30)
        elif persona == "finance":
            engine.setProperty('rate', rate + 20)
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        
        # Read into BytesIO
        with open(tmp_path, 'rb') as f:
            audio_stream = BytesIO(f.read())
        
        os.unlink(tmp_path)
        audio_stream.seek(0)
        
        print(f"✅ pyttsx3 success: {audio_stream.tell()} bytes")
        return audio_stream
        
    except Exception as e:
        print(f"❌ pyttsx3 failed: {e}")
        return BytesIO()

async def text_to_speech_stream_async(text: str, persona: str = "general") -> BytesIO:
    """
    Multi-tier fallback TTS system:
    1. Try Google TTS (online, reliable)
    2. Fall back to pyttsx3 (offline, always works)
    """
    # Clean text
    text = text.strip()
    text = text.replace('**', '').replace('*', '').replace('_', '')
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = ' '.join(text.split())
    
    if not text or len(text) < 3:
        print(f"⚠️ TTS: Text too short")
        return BytesIO()
    
    if len(text) > 3000:
        text = text[:2997] + "..."
    
    # Try Google TTS first
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: asyncio.run(generate_tts_gtts(text, persona)))
    except Exception as gtts_error:
        print(f"⚠️ Google TTS failed: {gtts_error}")
        
        # Fallback to pyttsx3
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, generate_tts_pyttsx3, text, persona)
        except Exception as fallback_error:
            print(f"❌ All TTS failed: {fallback_error}")
            return BytesIO()

def text_to_speech_stream(text: str, persona: str = "general") -> IO[bytes]:
    """Synchronous wrapper"""
    try:
        try:
            loop = asyncio.get_running_loop()
            print("⚠️ Called from async context!")
            return BytesIO()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(text_to_speech_stream_async(text, persona))
            loop.close()
            return result
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        return BytesIO()

if __name__ == "__main__":
    print("\n🚀 Testing TTS System\n")
    test_text = "Hello, this is a test of the text to speech system."
    
    for persona in ["general", "therapist", "healthcare"]:
        print(f"\nTesting {persona}:")
        audio = text_to_speech_stream(test_text, persona)
        size = len(audio.getvalue())
        print(f"Result: {'✓ Success' if size > 0 else '✗ Failed'} ({size:,} bytes)\n")