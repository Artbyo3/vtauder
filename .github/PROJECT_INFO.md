# Project Info: VTAuder (VRChat Integration)

## Overview
 **Purpose:** VTAuder enables mute-friendly communication in VRChat by sending music status, window info, and chat messages to the VRChat chatbox via OSC. No avatar parameter logic is used; all messaging is chat-focused.

## Mission
VTAuder aims to make communication easier for people who do not have a voice, helping them interact in VRChat and other programs. The app supports voice-to-text for users who are mute-friendly (can use STT), but does not provide full accessibility for actual mute users who cannot speak at all. Future improvements will focus on better accessibility and alternative input methods.
## Main Features
- OSC chatbox messaging with global rate limiting
- CustomTkinter UI for status, chat log, and controls
- DVD-style animation in chatbox when music is paused
- Speech-to-Text (STT) integration for chatbox messaging
- Manual chat entry and logging
- Optional active window info sharing

## Key Workflows
- Run app: `python main.py`
- Debug via console output: `[OSC SEND]`, `[STT]`, `[ANIM]`, `[CHATBOX]`
- Configuration managed at runtime via `config/settings.py`

## Feedback
If any section is unclear or missing, please specify what needs improvement or additional detail.
