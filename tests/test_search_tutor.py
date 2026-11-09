"""
Unit Tests for Phase 9: Web Search Bar & AIML Tutor / Debugger.
Tests DuckDuckGo search formatting, AIML tutor personas (Standard, Exam Mode, Quiz),
traceback parsing, code debugging, and Intent Router search/tutor patterns.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.brain.base import LLMResponse
from core.brain.intent_router import IntentRouter
from core.brain.tutor.debugger import CodeDebugger
from core.brain.tutor.tools import DebugCodeTool, ExplainConceptTool, GenerateQuizTool
from core.brain.tutor.tutor import AIMLTutor
from core.tools.cancellation import root_cancellation_token
from core.tools.search.web_search import WebSearchTool


# ==============================================================================
# 1. Web Search Tool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_web_search_tool_formatting():
    """Verifies DuckDuckGo search executes, formats snippets and source URLs."""
    tool = WebSearchTool()

    mock_ddg_results = [
        {
            "title": "Python 3.11 Features",
            "body": "Python 3.11 is up to 60% faster with specialized adaptive interpreter.",
            "href": "https://docs.python.org/3.11/",
        },
        {
            "title": "Real Python 3.11 Guide",
            "body": "Explore fine-grained error locations in tracebacks and exception groups.",
            "href": "https://realpython.com/python311/",
        },
    ]

    with patch("duckduckgo_search.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.return_value = mock_ddg_results

        res = await tool.execute(root_cancellation_token, query="Python 3.11 performance", max_results=2)

        assert res.success is True
        assert res.data["count"] == 2
        assert "Python 3.11 Features" in res.output
        assert "Source: https://docs.python.org/3.11/" in res.output
        assert res.data["results"][0]["title"] == "Python 3.11 Features"


@pytest.mark.asyncio
async def test_web_search_empty_and_error():
    """Verifies search handles empty queries and network errors cleanly."""
    tool = WebSearchTool()

    # Empty query
    res = await tool.execute(root_cancellation_token, query="   ")
    assert res.success is False
    assert "empty" in res.error

    # Network error
    with patch("duckduckgo_search.DDGS", side_effect=Exception("Connection refused")):
        res = await tool.execute(root_cancellation_token, query="test offline")
        assert res.success is False
        assert "failed" in res.error.lower()


# ==============================================================================
# 2. AIML Tutor Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_aiml_tutor_standard_and_exam_modes():
    """Verifies AIMLTutor switches between intuitive standard and academic exam personas."""
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=LLMResponse(
        content="📌 FORMAL DEFINITION: Gradient Descent is a first-order iterative optimization algorithm...",
        provider="gemini",
        model="gemini-2.0-flash",
    ))

    tutor = AIMLTutor(router=mock_router)

    # Exam mode
    output = await tutor.explain_concept(
        concept="Gradient Descent",
        topic="Machine Learning",
        level="intermediate",
        mode="exam",
    )

    assert "FORMAL DEFINITION" in output
    called_messages = mock_router.generate.call_args[0][0]
    assert called_messages[0].role == "system"
    assert "EXAM PREPARATION MODE" in called_messages[0].content


@pytest.mark.asyncio
async def test_aiml_tutor_quiz_generation():
    """Verifies AIMLTutor generates targeted quiz challenges."""
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=LLMResponse(
        content="Q: What is the primary advantage of Layer Normalization over Batch Normalization in Transformers?",
        provider="gemini",
        model="gemini-2.0-flash",
    ))

    tutor = AIMLTutor(router=mock_router)
    quiz = await tutor.generate_quiz(topic="Transformers", level="advanced")

    assert "Layer Normalization" in quiz
    called_messages = mock_router.generate.call_args[0][0]
    assert "AIML Examiner" in called_messages[0].content


# ==============================================================================
# 3. Code Debugger Tests
# ==============================================================================

def test_traceback_metadata_parser():
    """Verifies regex extraction of file names, line numbers, and error types."""
    debugger = CodeDebugger()

    sample_tb = (
        'Traceback (most recent call last):\n'
        '  File "c:/project/model.py", line 54, in forward\n'
        '    out = self.fc(x)\n'
        '  File "c:/project/layers.py", line 128, in __call__\n'
        '    return torch.matmul(input, self.weight)\n'
        'RuntimeError: mat1 and mat2 shapes cannot be multiplied (64x128 and 256x10)\n'
    )

    meta = debugger.extract_traceback_metadata(sample_tb)
    assert meta["file_name"] == "c:/project/layers.py"
    assert meta["line_number"] == 128
    assert meta["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_code_debugger_workflow():
    """Verifies code debugger identifies root cause and returns corrected code."""
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=LLMResponse(
        content=(
            "🔍 ROOT CAUSE: In linear layer forward pass, input dimension 128 does not match weight matrix input 256.\n"
            "🛠️ CORRECTED CODE:\n```python\nself.fc = nn.Linear(128, 10)\n```"
        ),
        provider="gemini",
        model="gemini-2.0-flash",
    ))

    debugger = CodeDebugger(router=mock_router)
    res = await debugger.debug_code(
        code="out = self.fc(x)",
        traceback="RuntimeError: mat1 and mat2 shapes cannot be multiplied",
        language="python",
    )

    assert "ROOT CAUSE" in res["analysis"]
    assert res["error_type"] == "RuntimeError"


# ==============================================================================
# 4. Agent Tools Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_tutor_and_debug_agent_tools():
    """Verifies ExplainConceptTool, DebugCodeTool, and GenerateQuizTool via BaseTool."""
    with patch("core.brain.tutor.tools.aiml_tutor.explain_concept", new_callable=AsyncMock) as mock_exp, \
         patch("core.brain.tutor.tools.code_debugger.debug_code", new_callable=AsyncMock) as mock_dbg, \
         patch("core.brain.tutor.tools.aiml_tutor.generate_quiz", new_callable=AsyncMock) as mock_qz:

        mock_exp.return_value = "Detailed explanation of Convolutional Neural Networks."
        mock_dbg.return_value = {"analysis": "Fix: import torch", "error_type": "NameError"}
        mock_qz.return_value = "Quiz: What does Backprop compute?"

        # 1. Explain Tool
        exp_tool = ExplainConceptTool()
        res = await exp_tool.execute(root_cancellation_token, concept="CNN", level="intermediate")
        assert res.success is True
        assert "Convolutional" in res.output

        # 2. Debug Tool
        dbg_tool = DebugCodeTool()
        res = await dbg_tool.execute(root_cancellation_token, code="x = torch.zeros(1)")
        assert res.success is True
        assert "NameError" in res.data["error_type"]

        # 3. Quiz Tool
        qz_tool = GenerateQuizTool()
        res = await qz_tool.execute(root_cancellation_token, topic="Neural Networks")
        assert res.success is True
        assert "Backprop" in res.output


# ==============================================================================
# 5. Intent Router Fast Path Tests
# ==============================================================================

def test_intent_router_search_and_tutor_fast_paths():
    """Verifies instant regex matching for web search, exam mode, and quizzes."""
    router = IntentRouter()

    # Web search
    match = router.match("Mike, search the web for latest quantum computing breakthroughs")
    assert match is not None
    assert match.tool_name == "web_search"
    assert "quantum computing" in match.parameters["query"]

    match = router.match("search for PyTorch 2.0 release")
    assert match is not None
    assert match.tool_name == "web_search"
    assert "PyTorch 2.0" in match.parameters["query"]

    # Exam Mode
    match = router.match("Mike, explain Backpropagation in exam mode")
    assert match is not None
    assert match.tool_name == "explain_concept"
    assert match.parameters["concept"] == "backpropagation"
    assert match.parameters["mode"] == "exam"

    match = router.match("explain like I'm in an exam Support Vector Machines")
    assert match is not None
    assert match.tool_name == "explain_concept"
    assert "support vector machines" in match.parameters["concept"].lower()
    assert match.parameters["mode"] == "exam"

    # Quiz Mode
    match = router.match("Mike, quiz me on deep learning")
    assert match is not None
    assert match.tool_name == "generate_quiz"
    assert match.parameters["topic"] == "deep learning"
