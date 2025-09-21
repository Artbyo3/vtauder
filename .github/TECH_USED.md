# Tech Used: VTAuder

## Languages & Frameworks
- Python 3.13
- CustomTkinter (UI)
- PIL (image handling)
- win32gui (Windows window info)
- requests (HTTP API)

## Integrations
- VRChat OSC (port 9000, chatbox only)
- Speech-to-Text via `src/integrations/stt.py`
- Audio routing (paused, see `src/core/audio_engine.py`)

## Patterns & Conventions
- All OSC messages use `VRChatOSCClient.send_chat_message(text)`
- Global rate limiter: 2s between messages, 30s spam timeout
- UI status and chat log: `status_text.configure`, `append_chat_log`
- DVD animation: emoji/text, random position/speed, main class methods
- STT disables music animation for 10s, then resumes

## Dependencies
- See `requirements.txt` or install manually as needed.
