# Copilot Instructions for VTAuder (VRChat Integration)

## Project Overview
- **Purpose:** VTAuder enables mute-friendly communication in VRChat by sending music status, window info, and chat messages to the VRChat chatbox via OSC. No avatar parameter logic is used; all messaging is chat-focused.
- **Main Components:**
  - `main.py`: Main app logic, UI, and orchestration.
  - `src/integrations/vrchat.py`: OSC client for VRChat chatbox (`send_chat_message`).
  - `src/integrations/stt.py`: Speech-to-Text integration.
  - `config/settings.py`: Configuration management.
  - `src/ui/components.py`: CustomTkinter UI widgets.
  - `src/core/audio_engine.py`: Audio routing (currently paused).

## Key Patterns & Conventions
- **OSC Messaging:**
  - All messages are sent to `/chatbox/input` using `VRChatOSCClient.send_chat_message(text)`.
  - Global rate limiter: Minimum 2s between messages, 30s timeout if spam detected.
- **UI:**
  - Uses `customtkinter` for all UI elements.
  - Status and chat log updates use `status_text.configure` and `append_chat_log`.
- **DVD Animation:**
  - When music is paused, a DVD-style animation is sent to the chatbox using emoji and text, with random position/speed.
  - Animation logic is inside the main class; see `start_dvd_animation`, `animate_dvd_status`, and `stop_dvd_animation`.
- **STT (Speech-to-Text):**
  - STT messages are sent to chatbox if enabled, with debug prints for troubleshooting.
  - STT disables music animation for 10s, then resumes.
- **Manual Chat:**
  - Manual messages are sent via the chat entry box and logged.
- **Window Info:**
  - Optionally sends active window info to chatbox if enabled.

## Developer Workflows
- **Run App:**
  - Entry point: `main.py` (`python main.py`).
- **Debugging:**
  - Debug prints are used for OSC, STT, and animation events.
  - Check console output for `[OSC SEND]`, `[STT]`, `[ANIM]`, and `[CHATBOX]` logs.
- **Configuration:**
  - Settings are managed via `config/settings.py` and updated at runtime.
- **Dependencies:**
  - Python 3.13, `customtkinter`, `PIL`, `win32gui`, `requests`.

## Integration Points
- **VRChat OSC:**
  - Always uses port 9000.
  - Only chatbox messages are sent; no avatar logic.
- **STT:**
  - Integrated via `realtime_stt` from `src/integrations/stt.py`.
- **Audio Routing:**
  - Paused; code present in `src/core/audio_engine.py`.

## Examples
- **Send chatbox message:**
  ```python
  sent = self.send_chatbox_message("Hello VRChat!")
  ```
- **Start DVD animation:**
  ```python
  self.start_dvd_animation()
  ```
- **Handle STT text:**
  ```python
  def on_stt_text(self, text):
      self.stop_music_animation()
      self.send_chatbox_message(text)
  ```

## File References
- Main logic: `main.py`
- OSC: `src/integrations/vrchat.py`
- STT: `src/integrations/stt.py`
- UI: `src/ui/components.py`
- Config: `config/settings.py`

---
**Feedback:** If any section is unclear or missing, please specify what needs improvement or additional detail.
