"""
Intent Router & Fast-Path Command Dispatcher for MIKE.
Intercepts common commands (lock, volume, YouTube, Spotify, WhatsApp, apps)
via regex patterns for zero-latency (<10ms) local execution.
Handles Tier C confirmation dialogs (e.g. WhatsApp message verification).
Falls back to Brain LLM Router for complex planning and open-ended queries.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.logger import logger
from core.tools.whatsapp.sender import resolve_contact_phone


@dataclass
class IntentMatch:
    intent_name: str
    tool_name: str
    parameters: Dict[str, Any]
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class IntentRouter:
    """Fast-path intent matcher and confirmation state tracker."""

    def __init__(self):
        self._pending_action: Optional[Dict[str, Any]] = None

    @property
    def has_pending_confirmation(self) -> bool:
        return self._pending_action is not None

    def clear_pending_confirmation(self):
        self._pending_action = None

    def match(self, text: str) -> Optional[IntentMatch]:
        """Matches user speech/text against fast-path regex rules."""
        raw = text.strip()
        # Clean text: replace punctuation with space for reliable matching
        norm = re.sub(r"[^\w\s\+]", " ", raw.lower())
        norm = re.sub(r"\s+", " ", norm).strip()

        # 0. Pending confirmation handler: Yes/No
        if self._pending_action:
            if norm in ["yes", "yeah", "yep", "sure", "confirm", "send it", "proceed", "go ahead", "do it"]:
                tool = self._pending_action["tool_name"]
                args = self._pending_action["parameters"].copy()
                args["confirmed"] = True
                self._pending_action = None
                return IntentMatch(
                    intent_name="confirm_action",
                    tool_name=tool,
                    parameters=args,
                    requires_confirmation=False,
                )
            elif norm in ["no", "nope", "cancel", "don't send", "abort", "never mind", "stop"]:
                self._pending_action = None
                return IntentMatch(
                    intent_name="cancel_action",
                    tool_name="cancel",
                    parameters={"message": "Action cancelled."},
                    requires_confirmation=False,
                )

        # 1. YouTube Play: "Mike, play <query> on YouTube"
        yt_play = (
            re.match(r"^(?:mike\s+)?(?:play|search)\s+(.+?)\s+on\s+youtube$", norm)
            or re.match(r"^(?:mike\s+)?youtube\s+(?:play|search)\s+(.+)$", norm)
        )
        if yt_play:
            return IntentMatch(
                intent_name="play_youtube",
                tool_name="play_youtube",
                parameters={"query": yt_play.group(1).strip()},
            )

        # 2. YouTube Controls: pause, next, fullscreen
        yt_ctrl = re.match(r"^(?:mike\s+)?(?:pause|resume|next|fullscreen|mute|rewind|forward)\s+(?:youtube|video)$", norm)
        if yt_ctrl:
            act = norm.split()[1] if norm.startswith("mike") else norm.split()[0]
            action_map = {
                "pause": "pause",
                "resume": "resume",
                "next": "next",
                "fullscreen": "fullscreen",
                "mute": "mute",
                "rewind": "rewind",
                "forward": "forward",
            }
            return IntentMatch(
                intent_name="control_youtube",
                tool_name="control_youtube",
                parameters={"action": action_map.get(act, "play_pause")},
            )

        # 3. WhatsApp: "Mike, message <contact> <text>"
        wa_match = (
            re.match(r"^(?:mike[\s,]+)?(?:message|whatsapp|text|send\s+message\s+to)\s+([a-zA-Z0-9_\+]+)\s+(.+)$", raw, re.IGNORECASE)
        )
        if wa_match:
            recipient = wa_match.group(1).strip()
            msg_body = wa_match.group(2).strip()
            resolved_name, phone = resolve_contact_phone(recipient)
            display_target = resolved_name if resolved_name else recipient
            phone_str = f" ({phone})" if phone else ""
            prompt = f"You want to send a WhatsApp message to {display_target}{phone_str} saying: '{msg_body}'. Shall I send this? Please confirm."

            # Store pending action
            self._pending_action = {
                "tool_name": "send_whatsapp_message",
                "parameters": {
                    "recipient": recipient,
                    "message": msg_body,
                },
            }
            return IntentMatch(
                intent_name="send_whatsapp",
                tool_name="send_whatsapp_message",
                parameters={"recipient": recipient, "message": msg_body, "confirmed": False},
                requires_confirmation=True,
                confirmation_prompt=prompt,
            )

        # 4. Spotify / Music Play: "Mike, play <query> on Spotify" or "play music"
        sp_play = (
            re.match(r"^(?:mike\s+)?(?:play|listen to)\s+(.+?)\s+on\s+spotify$", norm)
            or re.match(r"^(?:mike\s+)?spotify\s+play\s+(.+)$", norm)
        )
        if sp_play:
            return IntentMatch(
                intent_name="play_spotify",
                tool_name="play_music",
                parameters={"query": sp_play.group(1).strip(), "player": "spotify"},
            )

        if norm in ["mike play music", "play music", "mike listen to music"]:
            return IntentMatch(
                intent_name="play_music",
                tool_name="play_music",
                parameters={},
            )

        # 5. Global Media Controls: pause music, next song, previous song, stop music
        media_ctrl = (
            re.match(r"^(?:mike\s+)?(?:pause|resume|next|previous|stop)\s+(?:music|song|track)$", norm)
            or re.match(r"^(?:mike\s+)?(?:pause|resume|skip|next\s+song|previous\s+song)$", norm)
        )
        if media_ctrl:
            if "next" in norm or "skip" in norm:
                action = "next"
            elif "previous" in norm or "prev" in norm:
                action = "previous"
            elif "stop" in norm:
                action = "stop"
            else:
                action = "play_pause"

            return IntentMatch(
                intent_name="control_media",
                tool_name="control_media_playback",
                parameters={"action": action},
            )

        # 6. Laptop Lock: "Mike, lock the laptop"
        if norm in [
            "mike lock the laptop",
            "lock the laptop",
            "mike lock laptop",
            "lock laptop",
            "mike lock the pc",
            "lock pc",
            "mike lock workstation",
            "lock screen",
            "mike lock screen",
        ]:
            return IntentMatch(
                intent_name="lock_workstation",
                tool_name="lock_workstation",
                parameters={},
            )

        # 7. Volume Control: "set volume to 50", "mute audio"
        vol_match = re.match(r"^(?:mike\s+)?(?:set|change)\s+volume(?:\s+to)?\s+(\d+)%?$", norm) or re.match(r"^(?:mike\s+)?volume\s+(\d+)%?$", norm)
        if vol_match:
            level = int(vol_match.group(1))
            return IntentMatch(
                intent_name="set_volume",
                tool_name="set_volume",
                parameters={"level": level},
            )

        if norm in ["mike mute", "mute", "unmute", "mike unmute", "toggle mute", "mute audio", "unmute audio"]:
            return IntentMatch(
                intent_name="toggle_mute",
                tool_name="toggle_mute",
                parameters={},
            )

        # 8. Brightness Control: "set brightness to 80"
        bright_match = re.match(r"^(?:mike\s+)?(?:set|change)\s+brightness(?:\s+to)?\s+(\d+)%?$", norm) or re.match(r"^(?:mike\s+)?brightness\s+(\d+)%?$", norm)
        if bright_match:
            level = int(bright_match.group(1))
            return IntentMatch(
                intent_name="set_brightness",
                tool_name="set_brightness",
                parameters={"level": level},
            )

        # 9. App Management: "open notepad", "close chrome"
        open_app = re.match(r"^(?:mike\s+)?open\s+([a-zA-Z0-9_\-\.\s]+)$", norm)
        if open_app:
            target_app = open_app.group(1).strip()
            # Don't match special keywords
            if target_app not in ["youtube", "spotify", "music", "whatsapp"]:
                return IntentMatch(
                    intent_name="open_app",
                    tool_name="open_app",
                    parameters={"app_name": target_app},
                )

        close_app = re.match(r"^(?:mike\s+)?close\s+([a-zA-Z0-9_\-\.\s]+)$", norm)
        if close_app:
            target_app = close_app.group(1).strip()
            return IntentMatch(
                intent_name="close_app",
                tool_name="close_app",
                parameters={"app_name": target_app},
            )

        # 10. Mouse Scrolling: "scroll down", "scroll up"
        scroll_match = re.match(r"^(?:mike\s+)?scroll\s+(up|down|left|right)$", norm)
        if scroll_match:
            return IntentMatch(
                intent_name="scroll_mouse",
                tool_name="scroll_mouse",
                parameters={"direction": scroll_match.group(1), "clicks": 3},
            )

        # 11. Vision Click: "click <target>", "double click <target>", "right click <target>"
        dclick_match = re.match(r"^(?:mike[\s,]+)?double\s+click(?:\s+on)?\s+(.+)$", raw, re.IGNORECASE)
        if dclick_match:
            return IntentMatch(
                intent_name="vision_click",
                tool_name="vision_click",
                parameters={"target": dclick_match.group(1).strip(), "click_type": "double"},
            )

        rclick_match = re.match(r"^(?:mike[\s,]+)?right\s+click(?:\s+on)?\s+(.+)$", raw, re.IGNORECASE)
        if rclick_match:
            return IntentMatch(
                intent_name="vision_click",
                tool_name="vision_click",
                parameters={"target": rclick_match.group(1).strip(), "click_type": "right"},
            )

        click_match = re.match(r"^(?:mike[\s,]+)?click(?:\s+on)?\s+(.+)$", raw, re.IGNORECASE)
        if click_match:
            tgt = click_match.group(1).strip()
            if tgt.lower() not in ["the laptop", "laptop", "pc"]:
                return IntentMatch(
                    intent_name="vision_click",
                    tool_name="vision_click",
                    parameters={"target": tgt, "click_type": "left"},
                )

        # 12. Web Search: "search the web for <query>", "search for <query>"
        search_match = re.match(
            r"^(?:mike[\s,]+)?(?:search\s+(?:the\s+)?web\s+for|web\s+search(?:\s+for)?|search\s+for|look\s+up)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if search_match:
            sq = search_match.group(1).strip()
            if not sq.lower().endswith("on youtube") and not sq.lower().endswith("on spotify"):
                return IntentMatch(
                    intent_name="web_search",
                    tool_name="web_search",
                    parameters={"query": sq},
                )

        # 13. AIML Tutor: Exam Mode & Quiz Mode
        exam_match1 = re.match(r"^(?:mike[\s,]+)?explain\s+(?:like\s+i\s+m\s+in\s+an\s+exam|in\s+exam\s+mode)\s+(.+)$", norm)
        exam_match2 = re.match(r"^(?:mike[\s,]+)?explain\s+(.+)\s+in\s+exam\s+mode$", norm)
        if exam_match1 or exam_match2:
            target_concept = (exam_match1 or exam_match2).group(1).strip()
            return IntentMatch(
                intent_name="explain_concept_exam",
                tool_name="explain_concept",
                parameters={"concept": target_concept, "mode": "exam"},
            )

        quiz_match = re.match(r"^(?:mike[\s,]+)?quiz\s+me(?:\s+on)?\s+(.+)$", norm)
        if quiz_match:
            return IntentMatch(
                intent_name="generate_quiz",
                tool_name="generate_quiz",
                parameters={"topic": quiz_match.group(1).strip()},
            )

        # 14. Project Builder: "Mike, create a <project>", "create a snake game in Python"
        proj_match = re.match(
            r"^(?:mike[\s,]+)?(?:create\s+(?:a\s+)?project|create\s+a|build\s+(?:a\s+)?project|build\s+a)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if proj_match:
            desc = proj_match.group(1).strip()
            # Exclude non-project phrases
            if not desc.lower().startswith("whatsapp") and not desc.lower().startswith("file") and not desc.lower().startswith("shortcut"):
                return IntentMatch(
                    intent_name="create_project",
                    tool_name="create_project",
                    parameters={"project_description": desc, "open_vscode": True},
                )

        # 15. Stock Analysis: "analyze stock RELIANCE", "analyze Apple stock", "stock shortlist"
        stock_match = re.match(
            r"^(?:mike[\s,]+)?(?:analyze\s+stock|analyze|stock\s+analysis\s+for|stock\s+price\s+of|stock\s+report\s+for)\s+([a-zA-Z0-9_\-\.\s]+?)(?:\s+stock)?$",
            raw,
            re.IGNORECASE,
        )
        if stock_match:
            stk = stock_match.group(1).strip()
            if stk.lower() not in ["the laptop", "laptop", "pc", "music", "code", "file"]:
                return IntentMatch(
                    intent_name="analyze_stock",
                    tool_name="analyze_stock",
                    parameters={"ticker": stk},
                )

        if any(phrase in norm for phrase in ["stock shortlist", "candidate stocks", "stock recommendations"]):
            return IntentMatch(
                intent_name="stock_shortlist",
                tool_name="stock_shortlist",
                parameters={"market": "NSE"},
            )

        return None


# Global intent router singleton
intent_router = IntentRouter()
