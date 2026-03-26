from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")

def transcribe_audio(file_path):
    segments, info = model.transcribe(file_path, beam_size=5)
    transcription = " ".join([segment.text for segment in segments])
    return {
        "language": info.language,
        "probability": info.language_probability,
        "transcription": transcription
    }