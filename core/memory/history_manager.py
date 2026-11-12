"""
Chat History & Project Artifacts Manager for MIKE.
Stores and organizes conversation sessions, generated code projects, and media.
Similar to ChatGPT's sidebar history model.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logger import logger


class HistoryManager:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (settings.data_dir / "chat_sessions.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.projects_dir = Path.home() / "MikeProjects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = settings.data_dir / "generated_images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        self._active_session_id: Optional[str] = None
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_path.exists():
            default_data = {
                "active_session_id": None,
                "sessions": []
            }
            try:
                self.storage_path.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error(f"Error initializing chat_sessions.json: {e}")

    def _read_data(self) -> Dict[str, Any]:
        try:
            if self.storage_path.exists():
                text = self.storage_path.read_text(encoding="utf-8")
                return json.loads(text)
        except Exception as e:
            logger.error(f"Error reading chat sessions: {e}")
        return {"active_session_id": None, "sessions": []}

    def _write_data(self, data: Dict[str, Any]):
        try:
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving chat sessions: {e}")

    def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Creates a brand new conversation session, or reuses an existing empty session."""
        data = self._read_data()
        sessions = data.get("sessions", [])

        # If newest session is already empty, reuse it instead of creating duplicates
        if sessions and len(sessions[0].get("messages", [])) == 0:
            if title and sessions[0].get("title") == "New Conversation":
                sessions[0]["title"] = title
            data["active_session_id"] = sessions[0]["id"]
            self._active_session_id = sessions[0]["id"]
            self._write_data(data)
            return sessions[0]

        now = datetime.now(timezone.utc).isoformat()
        session_id = f"sess_{int(time.time())}_{os.urandom(2).hex()}"
        new_session = {
            "id": session_id,
            "title": title or "New Conversation",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }

        sessions.insert(0, new_session)
        data["sessions"] = sessions
        data["active_session_id"] = session_id
        self._active_session_id = session_id
        self._write_data(data)
        logger.info(f"Created new conversation session: {session_id}")
        return new_session

    def get_active_session(self) -> Dict[str, Any]:
        """Returns the currently active session, or creates one if none exists."""
        data = self._read_data()
        active_id = self._active_session_id or data.get("active_session_id")
        if active_id:
            for s in data.get("sessions", []):
                if s["id"] == active_id:
                    self._active_session_id = active_id
                    return s
        return self.create_session("New Conversation")

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Returns list of sessions summaries (without full message payload for fast sidebar display)."""
        data = self._read_data()
        summaries = []
        for s in data.get("sessions", []):
            summaries.append({
                "id": s["id"],
                "title": s.get("title", "Conversation"),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
                "message_count": len(s.get("messages", [])),
                "is_active": s["id"] == (self._active_session_id or data.get("active_session_id")),
            })
        return summaries

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Returns full session details and messages."""
        data = self._read_data()
        for s in data.get("sessions", []):
            if s["id"] == session_id:
                data["active_session_id"] = session_id
                self._active_session_id = session_id
                self._write_data(data)
                return s
        return None

    def add_message(self, role: str, content: str, tool_activity: Optional[str] = None, session_id: Optional[str] = None):
        """Appends a message to the active or specified session."""
        if not content or not content.strip():
            return

        data = self._read_data()
        target_id = session_id or self._active_session_id or data.get("active_session_id")

        target_session = None
        for s in data.get("sessions", []):
            if s["id"] == target_id:
                target_session = s
                break

        if not target_session:
            target_session = self.create_session()
            data = self._read_data()
            target_id = target_session["id"]

        now = datetime.now(timezone.utc).isoformat()
        msg_obj = {
            "role": role,
            "content": content.strip(),
            "timestamp": now,
        }
        if tool_activity:
            msg_obj["tool_activity"] = tool_activity

        target_session["messages"].append(msg_obj)
        target_session["updated_at"] = now

        # Auto-update title if it's the first user message
        if role == "user" and target_session.get("title") in ["New Conversation", None]:
            # Generate clean short title (up to 32 chars)
            clean_title = content.strip().split("\n")[0][:35].capitalize()
            if len(content.strip()) > 35:
                clean_title += "..."
            target_session["title"] = clean_title

        self._write_data(data)

    def delete_session(self, session_id: str) -> bool:
        """Deletes a conversation session by ID."""
        data = self._read_data()
        original_len = len(data.get("sessions", []))
        data["sessions"] = [s for s in data.get("sessions", []) if s["id"] != session_id]

        if data.get("active_session_id") == session_id:
            data["active_session_id"] = data["sessions"][0]["id"] if data["sessions"] else None
            self._active_session_id = data["active_session_id"]

        self._write_data(data)
        return len(data.get("sessions", [])) < original_len

    def list_projects(self) -> List[Dict[str, Any]]:
        """Scans ~/MikeProjects for generated scripts and project files."""
        projects = []
        if not self.projects_dir.exists():
            return projects

        for p in sorted(self.projects_dir.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True):
            if p.is_file() and p.suffix in [".py", ".js", ".ts", ".html", ".cpp", ".java", ".md", ".json"]:
                stat = p.stat()
                projects.append({
                    "name": p.name,
                    "path": str(p.resolve()),
                    "size": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "extension": p.suffix.lstrip("."),
                })
        return projects

    def open_in_vscode(self, file_path: str) -> Dict[str, Any]:
        """Opens a file or directory in VS Code."""
        p = Path(file_path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            subprocess.Popen(["code", "-r", str(p)], shell=True)
            return {"success": True, "message": f"Opened {p.name} in Visual Studio Code."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_images(self) -> List[Dict[str, Any]]:
        """Scans for generated images and user media."""
        images = []
        search_dirs = [self.images_dir, settings.base_dir / "assets"]
        for d in search_dirs:
            if d.exists():
                for img in d.glob("*.*"):
                    if img.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                        images.append({
                            "name": img.name,
                            "path": str(img.resolve()),
                            "size": img.stat().st_size,
                            "updated_at": datetime.fromtimestamp(img.stat().st_mtime, tz=timezone.utc).isoformat(),
                        })
        return images


# Global history manager instance
history_manager = HistoryManager()

