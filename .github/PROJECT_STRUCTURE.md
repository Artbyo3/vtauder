# Project Structure: VTAuder

## Key Files & Directories
- `main.py`: Main app logic, UI, orchestration
- `config/settings.py`: Configuration management
- `src/integrations/vrchat.py`: OSC client for VRChat chatbox
- `src/integrations/stt.py`: Speech-to-Text integration
- `src/ui/components.py`: CustomTkinter UI widgets
- `src/core/audio_engine.py`: Audio routing (paused)
- `src/utils/system.py`: System utilities
- `assets/`: App icons/images

## Example Patterns
- Send chatbox message:
  ```python
  sent = self.send_chatbox_message("Hello VRChat!")
  ```
- Start DVD animation:
  ```python
  self.start_dvd_animation()
  ```
- Handle STT text:
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
