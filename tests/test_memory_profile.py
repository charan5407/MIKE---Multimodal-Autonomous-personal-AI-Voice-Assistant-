"""
Unit Tests for Phase 12: Private Profile Store, Long-Term Memory, and Audio Privacy.
Tests Fernet encryption/decryption, zero UI exposure, audio-only responses,
short-term sliding-window summarization, persistent SQLite memory with TF-IDF recall,
'forget that' deletion, rollback capability, and intent router fast-paths.
"""

import json
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

from core.brain.intent_router import IntentRouter
from core.memory.long_term import LongTermMemory
from core.memory.short_term import ShortTermMemory
from core.memory.tools import ForgetLastTool, RecallMemoryTool, RememberTool
from core.security.audit import AuditLogger
from core.security.profile import ProfileManager
from core.security.profile_tool import QueryProfileTool
from core.tools.cancellation import root_cancellation_token


# ==============================================================================
# 1. Private Profile Store & Fernet Encryption (Feature 8)
# ==============================================================================

def test_profile_encryption_and_decryption(tmp_path):
    """Verifies profile encryption, roundtrip decryption, and secure disk persistence."""
    profile_file = tmp_path / "profile.local.json"
    key_file = tmp_path / "secret_key.key"
    example_file = tmp_path / "profile.example.json"

    dummy_data = {
        "name": "Charan",
        "dob": "2004-01-01",
        "age": 21,
        "education": {
            "degree": "B.Tech in Artificial Intelligence & Machine Learning",
            "institution": "Engineering College",
            "year": "3rd Year",
        },
        "interests": ["Machine Learning", "Autonomous Agents"],
        "current_projects": ["MIKE Assistant"],
        "preferences": {"wake_word_enabled": True},
    }
    with open(example_file, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f)

    manager = ProfileManager(profile_path=profile_file, key_path=key_file, example_path=example_file)

    # 1. Initial load should populate from example and write encrypted to disk
    profile = manager.load_profile()
    assert profile["name"] == "Charan"
    assert profile["age"] == 21
    assert profile["education"]["year"] == "3rd Year"

    # 2. Key file must exist on disk
    assert key_file.exists()
    with open(key_file, "rb") as kf:
        key_content = kf.read().strip()
        Fernet(key_content)  # Should not raise exception

    # 3. Profile file on disk must be encrypted envelope
    assert profile_file.exists()
    with open(profile_file, "r", encoding="utf-8") as pf:
        disk_json = json.load(pf)
        assert disk_json.get("encrypted") is True
        assert "payload" in disk_json
        # Raw name must NOT be plain text in the file
        assert "Charan" not in disk_json["payload"]

    # 4. Updating a field re-encrypts and persists
    success = manager.update_field("age", 22)
    assert success is True
    assert manager.get_field("age") == 22

    # 5. Nested field retrieval
    degree = manager.get_field("education.degree")
    assert "Artificial Intelligence" in degree


def test_profile_auto_migration_of_plain_json(tmp_path):
    """Verifies that if an unencrypted JSON profile is dropped on disk, it is auto-encrypted."""
    profile_file = tmp_path / "profile.local.json"
    key_file = tmp_path / "secret_key.key"

    plain_data = {"name": "Charan", "age": 21, "secret_note": "private"}
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(plain_data, f)

    manager = ProfileManager(profile_path=profile_file, key_path=key_file)
    loaded = manager.load_profile()
    assert loaded["secret_note"] == "private"

    # Check that disk file was automatically encrypted
    with open(profile_file, "r", encoding="utf-8") as pf:
        disk_data = json.load(pf)
        assert disk_data.get("encrypted") is True


def test_audio_privacy_responses(tmp_path):
    """Verifies that MIKE provides audio-only natural verbal answers without markdown formatting."""
    profile_file = tmp_path / "profile.local.json"
    key_file = tmp_path / "secret_key.key"
    example_file = tmp_path / "profile.example.json"

    dummy_data = {
        "name": "Charan",
        "dob": "2004-05-15",
        "age": 21,
        "education": {
            "degree": "B.Tech in Artificial Intelligence",
            "institution": "University",
            "year": "3rd Year",
        },
        "interests": ["Robotics", "ML"],
        "current_projects": ["MIKE Autonomous Assistant"],
    }
    with open(example_file, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f)

    manager = ProfileManager(profile_path=profile_file, key_path=key_file, example_path=example_file)

    age_answer = manager.get_audio_answer("what is my age")
    assert "21 years old" in age_answer
    assert "**" not in age_answer  # No markdown formatting for TTS

    identity_answer = manager.get_audio_answer("who am i")
    assert "Charan" in identity_answer

    edu_answer = manager.get_audio_answer("what is my degree")
    assert "B.Tech" in edu_answer

    proj_answer = manager.get_audio_answer("tell me about my projects")
    assert "MIKE Autonomous Assistant" in proj_answer


def test_audit_log_profile_sanitization(tmp_path):
    """Verifies Zero UI Exposure / Logging sanitization for profile data."""
    log_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path=log_file)

    sensitive_args = {
        "query": "what is my age",
        "profile_dob": "2004-01-01",
        "password": "supersecretpassword",
        "auth_token": "abc123token",
    }
    sanitized = logger._sanitize_dict(sensitive_args)
    assert sanitized["password"] == "[REDACTED_SECRET]"
    assert sanitized["auth_token"] == "[REDACTED_SECRET]"
    assert sanitized["profile_dob"] == "[REDACTED_PRIVATE_DATA]"


# ==============================================================================
# 2. Query Profile Tool
# ==============================================================================

@pytest.mark.asyncio
async def test_query_profile_tool(tmp_path):
    """Tests QueryProfileTool execution and audio_only output flag."""
    profile_file = tmp_path / "profile.local.json"
    key_file = tmp_path / "secret_key.key"
    example_file = tmp_path / "profile.example.json"

    dummy = {"name": "Charan", "age": 21, "interests": ["AI"]}
    with open(example_file, "w", encoding="utf-8") as f:
        json.dump(dummy, f)

    manager = ProfileManager(profile_path=profile_file, key_path=key_file, example_path=example_file)

    tool = QueryProfileTool()
    # Patch manager
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("core.security.profile_tool.profile_manager", manager)
        result = await tool.execute(root_cancellation_token, query="how old am i")
        assert result.success is True
        assert "21 years old" in result.output
        assert result.data.get("audio_only") is True


# ==============================================================================
# 3. Short-Term Rolling Memory (Feature 7)
# ==============================================================================

def test_short_term_memory_sliding_window_summarization():
    """Verifies conversation rolling buffer and context compression."""
    mem = ShortTermMemory(max_turns=6, keep_recent=2)

    for i in range(10):
        mem.add_message("user", f"User question {i}")
        mem.add_message("assistant", f"Assistant response {i}")

    # Buffer should not exceed max_turns
    assert len(mem) <= 6
    # Earlier turns should be condensed into context summary
    summary = mem.summary
    assert len(summary) > 0
    assert "Earlier conversation context" in summary

    # Messages ready for LLM
    llm_msgs = mem.get_messages(include_summary=True)
    assert llm_msgs[0]["role"] == "system"
    assert "Earlier conversation context" in llm_msgs[0]["content"]
    assert llm_msgs[-1]["content"] == "Assistant response 9"

    mem.clear()
    assert len(mem) == 0
    assert mem.summary == ""


# ==============================================================================
# 4. Long-Term Memory Engine (Features 7 & 14)
# ==============================================================================

def test_long_term_memory_store_and_tfidf_recall(tmp_path):
    """Verifies SQLite storage, keyword extraction, and TF-IDF semantic recall."""
    db_file = tmp_path / "test_memory.db"
    ltm = LongTermMemory(db_path=db_file)

    id1 = ltm.store("I prefer dark mode and high contrast in all my IDEs.", category="preference")
    id2 = ltm.store("My favorite programming languages are Python and Rust.", category="preference")
    id3 = ltm.store("Always keep voice synthesis speed calm and soft.", category="preference")
    assert id1 > 0 and id2 > 0 and id3 > 0
    assert ltm.count() == 3

    # Recall dark mode
    matches = ltm.recall("What theme or mode do I prefer for my editor?")
    assert len(matches) > 0
    assert "dark mode" in matches[0]["content"]

    # Recall voice setting
    voice_matches = ltm.recall("voice speed setting")
    assert len(voice_matches) > 0
    assert "voice synthesis speed" in voice_matches[0]["content"]


def test_long_term_memory_forget_last_and_matching(tmp_path):
    """Verifies 'Mike, forget that' and topic deletion."""
    db_file = tmp_path / "test_memory.db"
    ltm = LongTermMemory(db_path=db_file)

    ltm.store("Fact one: Charan likes tea.", category="fact")
    ltm.store("Fact two: Temporary note to be forgotten.", category="temporary")
    assert ltm.count() == 2

    # Forget last
    deleted = ltm.forget_last()
    assert deleted is not None
    assert "Temporary note" in deleted["content"]
    assert ltm.count() == 1

    # Forget matching
    ltm.store("Fact three: Charan is learning PyTorch.", category="fact")
    count_deleted = ltm.forget_matching("PyTorch")
    assert count_deleted >= 1
    assert ltm.count() == 1


# ==============================================================================
# 5. Memory Tools & Rollback (Feature 14)
# ==============================================================================

@pytest.mark.asyncio
async def test_memory_tools_execution_and_rollback(tmp_path):
    """Verifies RememberTool, RecallMemoryTool, and ForgetLastTool with rollback."""
    db_file = tmp_path / "test_memory.db"
    ltm = LongTermMemory(db_path=db_file)

    rem_tool = RememberTool()
    recall_tool = RecallMemoryTool()
    forget_tool = ForgetLastTool()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("core.memory.tools.long_term_memory", ltm)

        # 1. Store
        rem_res = await rem_tool.execute(
            root_cancellation_token,
            fact="I am building MIKE with FastAPI and React Three Fiber.",
            category="project",
        )
        assert rem_res.success is True
        assert "committed that to memory" in rem_res.output

        # 2. Recall
        rec_res = await recall_tool.execute(
            root_cancellation_token,
            query="What tech stack am I using for MIKE?",
        )
        assert rec_res.success is True
        assert "FastAPI" in rec_res.output

        # 3. Forget last
        forget_res = await forget_tool.execute(root_cancellation_token)
        assert forget_res.success is True
        assert "removed that from my memory" in forget_res.output
        assert forget_res.reversible is True

        # Verify it was removed
        assert ltm.count() == 0

        # 4. Rollback
        rollback_success = await forget_tool.rollback(forget_res.rollback_data)
        assert rollback_success is True
        assert ltm.count() == 1


# ==============================================================================
# 6. Intent Router Fast-Paths (Features 8, 7, 14)
# ==============================================================================

def test_intent_router_profile_and_memory_fast_paths():
    """Verifies zero-latency regex matching for profile questions and memory commands."""
    router = IntentRouter()

    # Profile queries
    m1 = router.match("Mike, who am I?")
    assert m1 is not None and m1.intent_name == "query_profile"

    m2 = router.match("what is my age")
    assert m2 is not None and m2.intent_name == "query_profile"

    m3 = router.match("Mike, what is my date of birth?")
    assert m3 is not None and m3.intent_name == "query_profile"

    m4 = router.match("tell me about my projects")
    assert m4 is not None and m4.intent_name == "query_profile"

    m5 = router.match("what is my degree")
    assert m5 is not None and m5.intent_name == "query_profile"

    # Memory commands
    m_rem = router.match("Mike, remember that I like low latency audio")
    assert m_rem is not None and m_rem.intent_name == "remember_fact"
    assert "low latency audio" in m_rem.parameters["fact"]

    m_fgt1 = router.match("Mike, forget that")
    assert m_fgt1 is not None and m_fgt1.intent_name == "forget_last"

    m_fgt2 = router.match("forget what I just said")
    assert m_fgt2 is not None and m_fgt2.intent_name == "forget_last"

    m_fgt3 = router.match("Mike, forget about dark mode")
    assert m_fgt3 is not None and m_fgt3.intent_name == "forget_last"
    assert m_fgt3.parameters["topic"] == "dark mode"

    m_rec = router.match("Mike, what do you remember about audio?")
    assert m_rec is not None and m_rec.intent_name == "recall_memory"
    assert m_rec.parameters["query"] == "audio"
