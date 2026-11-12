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

        # 0.5 Pure Wake-Word Activation: "wake up mike", "mike", "hey mike", "wake up"
        wake_patterns = [
            r"^(?:hey\s+)?mike$",
            r"^wake\s+up(?:\s+mike)?$",
            r"^(?:are\s+you\s+there\s+mike|mike\s+are\s+you\s+there)$",
            r"^mic$",
        ]
        for pat in wake_patterns:
            if re.match(pat, norm):
                return IntentMatch(
                    intent_name="wake_up",
                    tool_name="wake_up",
                    parameters={"query": raw},
                )

        # Strip conversational filler prefixes so core intents match effortlessly
        cleaned = norm
        prefixes = [
            r"^(?:hey\s+)?mike[\s,]+",
            r"^what\s+happened[\s,]+",
            r"^can\s+(?:you|u)\s+(?:please\s+)?",
            r"^could\s+(?:you|u)\s+(?:please\s+)?",
            r"^will\s+(?:you|u)\s+(?:please\s+)?",
            r"^would\s+(?:you|u)\s+(?:please\s+)?",
            r"^please\s+",
            r"^just\s+",
            r"^i\s+want\s+you\s+to\s+",
            r"^help\s+me\s+",
            r"^go\s+ahead\s+and\s+",
            r"^tell\s+me\s+",
            r"^do\s+one\s+thing\s+",
        ]
        for p in prefixes:
            cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()

        # 0.8 VS Code & Program Execution (Direct execution + VS Code Launch)
        # e.g. "what happened open visual studio code and show the program", "open vscode and run the code", "run in vscode"
        is_vscode = any(v in norm for v in ["visual studio code", "vscode", "vs code"])
        text_without_vscode = re.sub(r"\b(?:visual\s+studio\s+code|vscode|vs\s+code)\b", " ", norm)
        is_exec = any(e in text_without_vscode for e in ["show", "run", "execute", "display", "output", "program", "script", "code"])

        if is_vscode and is_exec:
            topic = "linked list"
            for candidate in ["linked list", "bubble sort", "binary search", "calculator", "sort", "tree", "graph", "stack", "queue"]:
                if candidate in norm:
                    topic = candidate
                    break
            return IntentMatch(
                intent_name="execute_code",
                tool_name="execute_code",
                parameters={"prompt": topic, "open_vscode": True},
            )

        # 0.9 Direct Code Writing & Running
        # e.g. "write a python script for linked list", "run bubble sort in python", "execute linked list"
        code_exec_match = (
            re.match(r"^(?:write|create|code|generate|build)\s+(?:a\s+)?(?:python\s+)?(?:script|program|code)\s+(?:for|to|of)?\s*(.+)$", cleaned, re.IGNORECASE)
            or re.match(r"^(?:run|execute)\s+(?:the\s+)?(?:python\s+)?(?:script|program|code)?\s*(?:for|to|of)?\s*(.+)$", cleaned, re.IGNORECASE)
        )
        if code_exec_match:
            concept = code_exec_match.group(1).strip()
            if not any(w in concept for w in ["youtube", "spotify", "music", "app", "window", "chrome", "notepad", "calculator", "browser"]):
                return IntentMatch(
                    intent_name="execute_code",
                    tool_name="execute_code",
                    parameters={"prompt": concept, "open_vscode": True},
                )

        # Dedicated VS Code launch without execution
        if cleaned in ["open vscode", "open vs code", "open visual studio code", "launch vscode", "launch visual studio code", "vscode", "visual studio code"]:
            return IntentMatch(
                intent_name="open_app",
                tool_name="open_app",
                parameters={"app_name": "vscode"},
            )

        # 1. YouTube Direct Open & Play: "Mike, open YouTube" / "Mike, play <query> on YouTube"
        if cleaned in ["open youtube", "launch youtube", "go to youtube", "youtube"]:
            return IntentMatch(
                intent_name="open_app",
                tool_name="open_app",
                parameters={"app_name": "youtube"},
            )

        yt_play = (
            re.match(r"^(?:play|search)\s+(.+?)\s+on\s+youtube$", cleaned)
            or re.match(r"^youtube\s+(?:play|search)\s+(.+)$", cleaned)
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
            try:
                from core.tools.whatsapp.sender import resolve_contact_phone
                resolved_name, phone = resolve_contact_phone(recipient)
            except Exception:
                resolved_name, phone = recipient, None
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

        # 5.4 Image Capability & Info Checks
        # e.g. "can you generate a image", "can you create images", "what do you require to generate an image"
        if cleaned in [
            "generate a image", "generate an image", "generate image", "generate images",
            "create a image", "create an image", "create image", "create images",
            "make a image", "make an image", "make image", "can u generate a image",
            "can you generate a image", "can you generate an image", "can you create images",
            "can you make images", "draw a picture", "draw an image", "image generation",
        ]:
            return IntentMatch(
                intent_name="can_generate_image",
                tool_name="can_generate_image",
                parameters={},
            )

        if any(q in cleaned for q in [
            "what do you require to generate an image",
            "what upgrades i need to make",
            "what upgrades do you require",
            "how do you generate image",
            "how do you create image",
        ]):
            return IntentMatch(
                intent_name="image_capabilities_info",
                tool_name="image_capabilities_info",
                parameters={"query": raw},
            )

        # 5.5 Multimodal Generation & Perception Fast-Paths
        # Show / Display Latest Generated Image
        norm_no_space = re.sub(r"\s+", "", cleaned)
        if any(w in cleaned for w in [
            "display image", "display it", "show image", "show the image",
            "open image", "open the image", "where is the image",
            "dont see any image", "dont see the image", "didnt see the image",
            "don t see any image", "don t see the image", "didn t see the image",
            "don t see", "dont see", "can you please display", "please display it",
            "display the image", "show the bike image", "display the bike image",
            "show the latest image", "display the latest image", "show the picture"
        ]) or "displayit" in norm_no_space or "showimage" in norm_no_space or "opentheimage" in norm_no_space:
            return IntentMatch(
                intent_name="show_latest_image",
                tool_name="show_latest_image",
                parameters={},
            )

        # Text-to-Image Generation
        img_gen_match = (
            re.match(r"^(?:create|generate|make|draw|paint|produce|show\s+me)\s+(?:an?\s+)?(?:illustration|image|photo|picture|artwork|drawing)\s+(?:of|for)?\s+(.+)$", cleaned)
            or re.match(r"^(?:image|photo|picture|illustration|artwork)\s+(?:of|for)\s+(.+)$", cleaned)
            or re.match(r"^generate\s+image\s+(.+)$", cleaned)
            or re.match(r"^draw\s+(?:an?\s+)?(.+)$", cleaned)
            or re.match(r"^(?:create|generate|make)\s+(?:an?\s+)?(.+?\s+(?:image|illustration|picture))$", cleaned)
            or re.match(r"^(?:illustration|image|photo|picture)\s+(?:of\s+)?(.+)$", cleaned)
        )
        if img_gen_match:
            img_prompt = img_gen_match.group(1).strip()
            # Clean trailing words like "image" or "illustration" if redundant
            img_prompt = re.sub(r"\s+(?:image|illustration|picture)$", "", img_prompt, flags=re.IGNORECASE).strip()
            if img_prompt:
                return IntentMatch(
                    intent_name="generate_image",
                    tool_name="generate_image",
                    parameters={"prompt": img_prompt},
                )

        # Vision QA & Screen Perception
        vision_screen_match = (
            re.match(r"^(?:what|describe|explain)\s+(?:is\s+)?(?:on\s+my\s+screen|my\s+screen|the\s+screen)$", cleaned)
            or re.match(r"^what\s+warning\s+is\s+visible(?:\s+on\s+the\s+machine\s+label)?", cleaned)
            or "describe my screen" in cleaned
            or "take a screenshot and analyze" in cleaned
        )
        if vision_screen_match:
            return IntentMatch(
                intent_name="analyze_image",
                tool_name="analyze_image",
                parameters={"query": raw, "image_path": "screen"},
            )

        # Text-to-Video Generation
        vid_gen_match = re.match(r"^(?:create|generate|make)\s+(?:a\s+)?(?:video|clip|animation)\s+(?:of|for)\s+(.+)$", cleaned)
        if vid_gen_match:
            vid_prompt = vid_gen_match.group(1).strip()
            return IntentMatch(
                intent_name="generate_video",
                tool_name="generate_video",
                parameters={"prompt": vid_prompt},
            )

        # Text-to-3D Generation
        three_d_match = re.match(r"^(?:create|generate|make)\s+(?:a\s+)?3d\s+(?:model|object|mesh)\s+(?:of|for)\s+(.+)$", cleaned)
        if three_d_match:
            three_d_prompt = three_d_match.group(1).strip()
            return IntentMatch(
                intent_name="generate_3d",
                tool_name="generate_3d",
                parameters={"prompt": three_d_prompt},
            )

        # Multimodal Meeting / Slides Summarizer
        if any(w in cleaned for w in ["summarize meeting", "summarize the meeting", "summarize slides", "meeting summary"]):
            return IntentMatch(
                intent_name="summarize_meeting",
                tool_name="summarize_meeting",
                parameters={"content_or_path": raw},
            )

        # Laptop Management & System Stats
        if cleaned in ["system stats", "laptop stats", "battery status", "laptop health", "system health", "cpu usage", "ram usage"]:
            return IntentMatch(
                intent_name="manage_laptop",
                tool_name="manage_laptop",
                parameters={"action": "system_stats"},
            )

        if cleaned in ["list apps", "list running apps", "what apps are open", "running applications"]:
            return IntentMatch(
                intent_name="manage_laptop",
                tool_name="manage_laptop",
                parameters={"action": "list_apps"},
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

        # 7. Volume Control: "set volume to 50", "mute audio", "volume up", "volume down"
        vol_match = (
            re.match(r"^(?:set|change)\s+volume(?:\s+to)?\s+(\d+)%?$", cleaned)
            or re.match(r"^volume\s+(\d+)%?$", cleaned)
            or re.match(r"^(?:mike\s+)?(?:set|change)\s+volume(?:\s+to)?\s+(\d+)%?$", norm)
        )
        if vol_match:
            level = int(vol_match.group(1))
            return IntentMatch(
                intent_name="set_volume",
                tool_name="set_volume",
                parameters={"level": level},
            )

        if any(w in cleaned for w in ["volume up", "increase volume", "turn it up", "louder", "make it louder"]):
            return IntentMatch(intent_name="set_volume", tool_name="set_volume", parameters={"level": 75})
        if any(w in cleaned for w in ["volume down", "decrease volume", "turn it down", "quieter", "lower volume"]):
            return IntentMatch(intent_name="set_volume", tool_name="set_volume", parameters={"level": 30})

        if cleaned in ["mute", "unmute", "toggle mute", "mute audio", "unmute audio"] or norm in ["mike mute", "mike unmute"]:
            return IntentMatch(
                intent_name="toggle_mute",
                tool_name="toggle_mute",
                parameters={},
            )

        # 8. Brightness Control: "set brightness to 80"
        bright_match = (
            re.match(r"^(?:set|change)\s+brightness(?:\s+to)?\s+(\d+)%?$", cleaned)
            or re.match(r"^brightness\s+(\d+)%?$", cleaned)
            or re.match(r"^(?:mike\s+)?(?:set|change)\s+brightness(?:\s+to)?\s+(\d+)%?$", norm)
        )
        if bright_match:
            level = int(bright_match.group(1))
            return IntentMatch(
                intent_name="set_brightness",
                tool_name="set_brightness",
                parameters={"level": level},
            )

        # 9. App Management: "open notepad", "close chrome", "open spotify", "open youtube"
        KNOWN_APP_KEYWORDS = {
            "notepad", "calculator", "calc", "chrome", "google chrome", "edge", "ms edge",
            "vscode", "vs code", "visual studio code", "spotify", "whatsapp", "youtube",
            "terminal", "cmd", "powershell", "explorer", "file explorer", "task manager",
            "browser", "settings", "camera", "word", "excel", "powerpoint", "paint", "discord"
        }
        STOP_WORDS = {"your", "the", "a", "an", "my", "this", "that", "it", "something", "anything"}

        open_app = (
            re.match(r"^open\s+([a-zA-Z0-9_\-\.\s]+)$", cleaned)
            or re.match(r"^(?:mike\s+)?open\s+([a-zA-Z0-9_\-\.\s]+)$", norm)
        )
        if open_app:
            target_app = open_app.group(1).strip().lower()
            # Only trigger open_app if target is known or a plausible app name (not stop words or question words)
            if target_app not in STOP_WORDS and not any(q in target_app for q in ["how", "what", "who", "why", "when", "language", "program", "code"]):
                if target_app in KNOWN_APP_KEYWORDS or len(target_app.split()) <= 2:
                    return IntentMatch(
                        intent_name="open_app",
                        tool_name="open_app",
                        parameters={"app_name": target_app},
                    )

        close_app = re.match(r"^(?:mike\s+)?close\s+([a-zA-Z0-9_\-\.\s]+)$", norm)
        if close_app:
            target_app = close_app.group(1).strip().lower()
            if target_app not in STOP_WORDS:
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

        # 16. Private Profile Fast-Paths (Feature 8):
        # Questions strictly answered for Charan's ear with zero UI exposure
        profile_patterns = [
            r"^(?:mike[\s,]+)?(?:who am i|what is my name|my name)$",
            r"^(?:mike[\s,]+)?(?:how old am i|what is my age|my age)$",
            r"^(?:mike[\s,]+)?(?:what is my (?:dob|date of birth)|when was i born|what is my birthday)$",
            r"^(?:mike[\s,]+)?(?:what (?:is|are) my (?:education|degree|college|university)|where do i study)$",
            r"^(?:mike[\s,]+)?(?:what are my (?:current )?projects|tell me (?:about )?my projects)$",
            r"^(?:mike[\s,]+)?(?:what are my interests|what do i like)$",
            r"^(?:mike[\s,]+)?(?:tell me my profile summary|profile summary)$",
        ]
        for pat in profile_patterns:
            if re.match(pat, norm):
                return IntentMatch(
                    intent_name="query_profile",
                    tool_name="query_profile",
                    parameters={"query": raw},
                )

        # 17. Memory Commands (Features 7 & 14):
        # "remember that...", "forget that", "recall..."
        rem_match = re.match(
            r"^(?:mike[\s,]+)?(?:remember that|remember this|keep in mind that)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if rem_match:
            fact = re.sub(r"[\?\.\!,]+$", "", rem_match.group(1)).strip()
            return IntentMatch(
                intent_name="remember_fact",
                tool_name="remember_fact",
                parameters={"fact": fact, "category": "preference"},
            )

        if norm in [
            "forget that",
            "mike forget that",
            "forget what i said",
            "mike forget what i said",
            "forget what i just said",
            "delete that memory",
            "forget that fact",
        ]:
            return IntentMatch(
                intent_name="forget_last",
                tool_name="forget_last",
                parameters={},
            )

        fgt_match = re.match(
            r"^(?:mike[\s,]+)?(?:forget about|delete memory about)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if fgt_match:
            topic = re.sub(r"[\?\.\!,]+$", "", fgt_match.group(1)).strip()
            return IntentMatch(
                intent_name="forget_last",
                tool_name="forget_last",
                parameters={"topic": topic},
            )

        recall_match = re.match(
            r"^(?:mike[\s,]+)?(?:what do you remember about|what did i say about|recall|do you remember)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if recall_match:
            topic = re.sub(r"[\?\.\!,]+$", "", recall_match.group(1)).strip()
            return IntentMatch(
                intent_name="recall_memory",
                tool_name="recall_memory",
                parameters={"query": topic},
            )

        # 18. Greetings & Identity Queries: "hello", "hi", "hey mike", "who are you", "what can you do"
        greeting_patterns = [
            r"^(?:mike[\s,]+)?(?:hello|hi|hey|hey mike|good morning|good afternoon|good evening)$",
            r"^(?:mike[\s,]+)?(?:who are you|what can you do|what are your features|help)$",
            r"^hello mike$",
        ]
        for pat in greeting_patterns:
            if re.match(pat, norm):
                return IntentMatch(
                    intent_name="greeting",
                    tool_name="greeting",
                    parameters={"query": raw},
                )

        return None


# Global intent router singleton
intent_router = IntentRouter()
