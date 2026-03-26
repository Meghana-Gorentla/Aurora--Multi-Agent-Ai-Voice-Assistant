import os
from typing import IO
from io import BytesIO
import edge_tts
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ✅ FIXED: Using ONLY verified, stable voices
PERSONA_VOICES = {
    "therapist": "en-US-JennyNeural",
    "tutor": "en-US-GuyNeural",
    "healthcare": "en-US-AriaNeural",
    "finance": "en-US-ChristopherNeural",  # Changed from DavisNeural
    "general": "en-US-AriaNeural",          # ✅ FIXED: Changed from SaraNeural
    "coordinator": "en-US-GuyNeural",       # ✅ FIXED: Changed from TonyNeural
    
    # Therapist sub-personalities
    "emotional_support": "en-US-JennyNeural",
    "cognitive_restructuring": "en-US-AriaNeural",
    "reflective_dialogue": "en-US-JennyNeural",  # ✅ FIXED: Changed from SaraNeural
}

# ✅ FIXED: Simplified settings with VALID parameters only
PERSONA_VOICE_SETTINGS = {
    "therapist": {
        "rate": "-5%",
        "pitch": "+0Hz",     # ✅ FIXED: Removed invalid pitch
        "volume": "+0%"
    },
    "tutor": {
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+5%"
    },
    "healthcare": {
        "rate": "-3%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+0%"
    },
    "finance": {
        "rate": "+5%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+8%"
    },
    "general": {
        "rate": "+0%",       # ✅ FIXED: Neutral settings
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+0%"
    },
    "coordinator": {
        "rate": "+3%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+10%"
    },
    "emotional_support": {
        "rate": "-8%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+0%"
    },
    "cognitive_restructuring": {
        "rate": "-2%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+2%"
    },
    "reflective_dialogue": {
        "rate": "-5%",
        "pitch": "+0Hz",     # ✅ FIXED
        "volume": "+0%"
    }
}

def get_voice_and_settings(persona: str):
    """Get voice ID and settings for persona"""
    voice = PERSONA_VOICES.get(persona, "en-US-AriaNeural")  # Safe fallback
    settings = PERSONA_VOICE_SETTINGS.get(persona, {
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%"
    })
    return voice, settings

async def text_to_speech_stream_async(text: str, persona: str = "general") -> BytesIO:
    """
    Async TTS generation - USE THIS IN ASYNC CONTEXTS (FastAPI endpoints)
    """
    try:
        # ✅ CRITICAL: Clean text thoroughly
        text = text.strip()
        
        # Remove markdown and problematic characters
        text = text.replace('**', '').replace('*', '').replace('_', '')
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # Normalize whitespace
        
        # Validate text
        if not text or len(text) < 3:
            print(f"⚠️ TTS: Text too short: '{text}'")
            return BytesIO()
        
        if len(text) > 3000:
            print(f"⚠️ TTS: Text too long, truncating")
            text = text[:2997] + "..."
        
        voice, settings = get_voice_and_settings(persona)
        
        print(f"🎤 TTS: voice={voice}, text_len={len(text)}")
        print(f"🎤 TTS: First 100 chars: '{text[:100]}'")
        print(f"🎤 TTS: Settings: {settings}")
        
        # ✅ CRITICAL: Create communicate object with minimal settings first
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice
            # Try WITHOUT rate/pitch/volume first to test
        )
        
        audio_stream = BytesIO()
        chunk_count = 0
        
        # Stream audio chunks
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])
                chunk_count += 1
        
        print(f"🎤 TTS: Received {chunk_count} chunks, {audio_stream.tell()} bytes")
        
        audio_stream.seek(0)
        
        if audio_stream.tell() == 0:
            print(f"❌ TTS: No audio generated")
            print(f"❌ TTS: Text: '{text}'")
            print(f"❌ TTS: Voice: {voice}")
        
        return audio_stream
        
    except Exception as e:
        print(f"❌ Edge TTS Error: {e}")
        import traceback
        traceback.print_exc()
        return BytesIO()

def text_to_speech_stream(text: str, persona: str = "general") -> IO[bytes]:
    """
    Synchronous wrapper - DO NOT USE IN ASYNC CONTEXTS
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            print("⚠️ WARNING: text_to_speech_stream called from async context!")
            return BytesIO()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(text_to_speech_stream_async(text, persona))
            loop.close()
            return result
    except Exception as e:
        print(f"❌ Edge TTS Error (sync): {e}")
        return BytesIO()

def test_all_voices():
    """Test function"""
    test_text = "Hello, this is a test."
    
    print("\n🎤 Testing All Voices\n" + "="*50)
    
    for persona in PERSONA_VOICES.keys():
        print(f"Testing {persona:25}", end=" ")
        try:
            audio = text_to_speech_stream(test_text, persona)
            size = len(audio.getvalue())
            if size > 0:
                print(f"✓ Working ({size:,} bytes)")
            else:
                print(f"✗ Failed (0 bytes)")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("="*50 + "\n")

if __name__ == "__main__":
    print("\n🚀 Testing Edge TTS")
    test_all_voices()