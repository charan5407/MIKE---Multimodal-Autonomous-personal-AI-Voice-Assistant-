"""
MIKE Private Profile Store (Feature 8).
Cryptographically encrypted personal store for Charan's private details.
Uses cryptography.fernet.Fernet with local key storage in data/secret_key.key
or PROFILE_ENCRYPTION_KEY environment variable.

ZERO UI EXPOSURE RULE: The UI has no field rendering these details.
AUDIO PRIVACY RULE: MIKE never reveals profile facts unless Charan explicitly
asks aloud (e.g. "Mike, what is my age?").
"""

import base64
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings
from core.logger import logger


class ProfileManager:
    """Manages encrypted private profile information for Charan."""

    def __init__(
        self,
        profile_path: Optional[Path] = None,
        key_path: Optional[Path] = None,
        example_path: Optional[Path] = None,
    ):
        self.profile_path = profile_path or settings.profile_path
        self.key_path = key_path or settings.secret_key_path
        self.example_path = example_path or settings.profile_example_path
        self._fernet: Optional[Fernet] = None
        self._cached_profile: Optional[Dict[str, Any]] = None

    def _get_or_create_fernet(self) -> Fernet:
        """Initializes or retrieves the Fernet encryption cipher."""
        if self._fernet is not None:
            return self._fernet

        key_bytes: Optional[bytes] = None

        # 1. Environment variable key
        if settings.profile_encryption_key:
            raw_key = settings.profile_encryption_key.strip()
            try:
                # Validate if it's already a valid Fernet key
                key_bytes = raw_key.encode("utf-8")
                Fernet(key_bytes)
            except Exception:
                # Derive 32-byte url-safe base64 key from arbitrary secret string
                digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
                key_bytes = base64.urlsafe_b64encode(digest)

        # 2. Local secret key file
        if key_bytes is None:
            if self.key_path.exists():
                try:
                    with open(self.key_path, "rb") as f:
                        file_key = f.read().strip()
                        Fernet(file_key)
                        key_bytes = file_key
                except Exception as e:
                    logger.warning(f"Existing key file invalid ({e}). Regenerating secure key.")

        # 3. Generate fresh key if none existed
        if key_bytes is None:
            key_bytes = Fernet.generate_key()
            try:
                self.key_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.key_path, "wb") as f:
                    f.write(key_bytes)
                # Restrict permissions on Windows/Unix if feasible
                try:
                    os.chmod(self.key_path, 0o600)
                except Exception:
                    pass
                logger.info(f"Generated new encryption key at {self.key_path}")
            except Exception as e:
                logger.error(f"Failed to persist encryption key to disk: {e}")

        self._fernet = Fernet(key_bytes)
        return self._fernet

    def load_profile(self) -> Dict[str, Any]:
        """Loads and decrypts profile from disk, falling back to template if absent."""
        if self._cached_profile is not None:
            return self._cached_profile

        fernet = self._get_or_create_fernet()

        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                # Check if it's stored in an encrypted envelope
                try:
                    envelope = json.loads(content)
                    if isinstance(envelope, dict) and envelope.get("encrypted") is True:
                        ciphertext = envelope.get("payload", "").encode("utf-8")
                        decrypted_bytes = fernet.decrypt(ciphertext)
                        self._cached_profile = json.loads(decrypted_bytes.decode("utf-8"))
                        return self._cached_profile
                    elif isinstance(envelope, dict):
                        # Plain JSON found on disk - auto-encrypt immediately for security
                        logger.warning("Unencrypted profile found on disk. Encrypting now.")
                        self._cached_profile = envelope
                        self.save_profile(envelope)
                        return self._cached_profile
                except json.JSONDecodeError:
                    # Might be raw fernet token string
                    decrypted_bytes = fernet.decrypt(content.encode("utf-8"))
                    self._cached_profile = json.loads(decrypted_bytes.decode("utf-8"))
                    return self._cached_profile
            except (InvalidToken, Exception) as e:
                logger.error(f"Failed to decrypt profile from {self.profile_path}: {e}")

        # Fallback to example template
        if self.example_path.exists():
            try:
                with open(self.example_path, "r", encoding="utf-8") as f:
                    template = json.load(f)
                self._cached_profile = template
                # Auto-encrypt and save local copy
                self.save_profile(template)
                return self._cached_profile
            except Exception as e:
                logger.error(f"Failed to load example profile from {self.example_path}: {e}")

        # Default minimal fallback
        fallback = {
            "name": "Charan",
            "dob": "2004-01-01",
            "age": 21,
            "education": {
                "degree": "B.Tech in Artificial Intelligence & Machine Learning",
                "institution": "University",
                "year": "3rd Year",
            },
            "interests": ["Machine Learning", "Autonomous Agents", "Robotics"],
            "current_projects": ["MIKE - Multimodal Autonomous Agentic Desktop Assistant"],
            "preferences": {"wake_word_enabled": True},
        }
        self._cached_profile = fallback
        return fallback

    def save_profile(self, profile: Dict[str, Any]) -> bool:
        """Encrypts and persists the profile data to disk."""
        fernet = self._get_or_create_fernet()
        try:
            raw_bytes = json.dumps(profile, indent=2).encode("utf-8")
            ciphertext = fernet.encrypt(raw_bytes).decode("utf-8")
            envelope = {
                "encrypted": True,
                "version": "1.0",
                "payload": ciphertext,
            }
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)

            self._cached_profile = profile
            return True
        except Exception as e:
            logger.error(f"Failed to encrypt and save profile: {e}")
            return False

    def get_field(self, field_path: str, default: Any = None) -> Any:
        """Retrieves a nested field from the decrypted profile (e.g. 'education.degree')."""
        profile = self.load_profile()
        parts = field_path.strip().split(".")
        current = profile
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def update_field(self, field_path: str, value: Any) -> bool:
        """Updates a field and securely persists the re-encrypted profile."""
        profile = dict(self.load_profile())
        parts = field_path.strip().split(".")
        current = profile
        for i, part in enumerate(parts[:-1]):
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        return self.save_profile(profile)

    def get_audio_answer(self, query: str) -> str:
        """
        Generates a warm, natural verbal response for Charan's ear only.
        Formatted specifically for TTS playback without markdown formatting symbols.
        """
        profile = self.load_profile()
        q = query.lower().strip()

        name = profile.get("name", "Charan")
        age = profile.get("age", 21)
        dob = profile.get("dob", "")
        education = profile.get("education", {})
        degree = education.get("degree", "B.Tech in Artificial Intelligence & Machine Learning")
        year = education.get("year", "3rd Year")
        institution = education.get("institution", "your college")
        projects = profile.get("current_projects", ["MIKE Assistant"])
        interests = profile.get("interests", ["Machine Learning", "Autonomous Agents"])

        if any(w in q for w in ["who am i", "my name", "what is my name"]):
            return f"You are {name}, currently studying {degree}."

        if any(w in q for w in ["how old am i", "what is my age", "my age"]):
            # If DOB exists, format DOB as well
            if dob:
                return f"You are {age} years old, born on {dob}."
            return f"You are {age} years old."

        if any(w in q for w in ["date of birth", "dob", "when was i born", "my birthday"]):
            if dob:
                return f"Your date of birth is {dob}."
            return f"I don't have your exact date of birth recorded yet."

        if any(w in q for w in ["education", "degree", "college", "university", "study", "studying"]):
            return f"You are in your {year} of {degree} at {institution}."

        if any(w in q for w in ["project", "projects", "what am i building"]):
            proj_str = ", ".join(projects)
            return f"Your current projects include {proj_str}."

        if any(w in q for w in ["interest", "interests", "what do i like"]):
            int_str = ", ".join(interests)
            return f"Your recorded interests are {int_str}."

        # General summary
        proj_str = ", ".join(projects)
        return (
            f"Here is a summary, {name}. You are {age} years old, pursuing {degree} at {institution}, "
            f"and currently developing {proj_str}."
        )


# Global profile manager singleton
profile_manager = ProfileManager()
