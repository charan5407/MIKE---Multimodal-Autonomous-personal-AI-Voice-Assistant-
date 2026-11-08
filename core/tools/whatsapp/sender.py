"""
WhatsApp Integration for MIKE.
Resolves contacts from private, gitignored data/contacts.local.json.
Supports 'Mike, message <contact> <text>'.
CRITICAL SECURITY REQUIREMENT:
Tier C sensitive action - ALWAYS reads the recipient and message back
and asks for explicit confirmation before sending.
"""

import json
import os
import re
import sys
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field
import pyautogui

from core.config import settings
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


def load_contacts() -> Dict[str, str]:
    """Loads contact dictionary from contacts.local.json or contacts.example.json."""
    local_path = settings.contacts_path
    example_path = settings.contacts_example_path

    target_path = local_path if local_path.exists() else example_path
    if not target_path.exists():
        logger.warning(f"No contacts file found at {local_path} or {example_path}")
        return {}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading contacts file {target_path}: {e}")
        return {}


def resolve_contact_phone(contact_query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves contact query to (contact_name, phone_number).
    Returns (None, None) if not found and not a valid phone number.
    """
    cleaned_query = contact_query.strip()
    if not cleaned_query:
        return None, None

    # Check if query is already a phone number
    phone_pattern = re.sub(r"[^\d+]", "", cleaned_query)
    if len(phone_pattern) >= 10:
        if not phone_pattern.startswith("+") and len(phone_pattern) == 10:
            phone_pattern = "+91" + phone_pattern  # Default to India if 10-digit
        return cleaned_query, phone_pattern

    contacts = load_contacts()
    query_lower = cleaned_query.lower()

    # 1. Exact match (case-insensitive)
    for name, phone in contacts.items():
        if name.lower() == query_lower:
            return name, re.sub(r"[^\d+]", "", phone)

    # 2. Fuzzy / Substring match
    for name, phone in contacts.items():
        norm_name = re.sub(r"[^a-zA-Z0-9]", "", name.lower())
        norm_query = re.sub(r"[^a-zA-Z0-9]", "", query_lower)
        if norm_query in norm_name or norm_name in norm_query:
            return name, re.sub(r"[^\d+]", "", phone)

    return None, None


class ResolveContactArgs(BaseModel):
    name: str = Field(..., description="Name of the contact to resolve.")


class ResolveContactTool(BaseTool):
    """Resolves contact names to phone numbers from the local contacts store."""

    name = "resolve_contact"
    description = "Resolves a contact name (e.g. 'Mom', 'Dad', 'Rahul') to a verified phone number."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ResolveContactArgs
    timeout_sec = 5.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        name: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        resolved_name, phone = resolve_contact_phone(name)
        if not phone:
            return ToolResult(
                success=False,
                error=f"Contact '{name}' not found in contacts.local.json. Please add it or provide a phone number.",
            )

        return ToolResult(
            success=True,
            output=f"Resolved contact '{resolved_name}': {phone}",
            data={"name": resolved_name, "phone": phone},
        )


class SendWhatsAppMessageArgs(BaseModel):
    recipient: str = Field(..., description="Contact name (e.g. 'Mom') or full phone number.")
    message: str = Field(..., description="The message text to send.")
    confirmed: bool = Field(default=False, description="Set to true only after user has confirmed sending.")
    auto_press_enter: bool = Field(default=False, description="Whether to automatically press enter after opening.")


class SendWhatsAppMessageTool(BaseTool):
    """
    Tier C sensitive tool to send WhatsApp message.
    ALWAYS requires explicit confirmation before opening or sending.
    """

    name = "send_whatsapp_message"
    description = "Sends a WhatsApp message to a contact or phone number. Requires explicit user confirmation."
    tier = PermissionTier.TIER_C_SENSITIVE
    args_schema = SendWhatsAppMessageArgs
    timeout_sec = 20.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        recipient: str = "",
        message: str = "",
        confirmed: bool = False,
        auto_press_enter: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        if not recipient or not recipient.strip():
            return ToolResult(success=False, error="Recipient is required.")
        if not message or not message.strip():
            return ToolResult(success=False, error="Message cannot be empty.")

        recipient = recipient.strip()
        message = message.strip()

        # 1. Resolve recipient to phone number
        resolved_name, phone = resolve_contact_phone(recipient)
        if not phone:
            return ToolResult(
                success=False,
                error=f"Could not find contact '{recipient}' in contacts.local.json or as a valid phone number.",
            )

        contact_display = resolved_name if resolved_name else recipient

        # 2. Strict Tier C Confirmation Check
        if not confirmed:
            prompt = (
                f"You want to send a WhatsApp message to {contact_display} ({phone}) saying: '{message}'. "
                f"Shall I send this? Please confirm."
            )
            return ToolResult(
                success=False,
                requires_confirmation=True,
                confirmation_prompt=prompt,
                output=prompt,
                data={
                    "recipient": contact_display,
                    "phone": phone,
                    "message": message,
                },
            )

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled before dispatching message.")

        # 3. Construct WhatsApp URI & URL
        clean_phone = re.sub(r"[^\d]", "", phone)
        encoded_message = urllib.parse.quote(message)
        desktop_uri = f"whatsapp://send?phone={clean_phone}&text={encoded_message}"
        web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"

        logger.info(f"Dispatching confirmed WhatsApp message to {contact_display} ({phone})")

        launched_platform = "WhatsApp Desktop"
        try:
            if sys.platform == "win32":
                try:
                    os.startfile(desktop_uri)
                except Exception:
                    webbrowser.open(web_url)
                    launched_platform = "WhatsApp Web"
            else:
                webbrowser.open(web_url)
                launched_platform = "WhatsApp Web"

            # Optional auto enter keypress
            if auto_press_enter:
                import asyncio
                await asyncio.sleep(2.0)
                pyautogui.press("enter")

            return ToolResult(
                success=True,
                output=f"WhatsApp opened for {contact_display} ({phone}) with your message ready to send.",
                data={
                    "recipient": contact_display,
                    "phone": phone,
                    "message": message,
                    "platform": launched_platform,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to open WhatsApp: {e}")
