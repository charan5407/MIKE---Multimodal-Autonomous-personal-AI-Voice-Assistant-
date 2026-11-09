"""
AIML Tutor Engine for MIKE.
Provides deep, pedagogical explanations of core AIML, CS, and Math topics:
Machine Learning, Deep Learning, NLP, Computer Vision, Statistics, Linear Algebra, Python, DSA, DBMS.
Supports Beginner/Intermediate/Advanced levels and Standard, Exam, and Quiz modes.
"""

from typing import List, Optional
from core.brain.base import ChatMessage
from core.brain.router import router as llm_router
from core.brain.tutor.prompts import (
    EXAM_MODE_PROMPT,
    QUIZ_MODE_PROMPT,
    STANDARD_TUTOR_PROMPT,
)
from core.logger import logger


class AIMLTutor:
    """Intelligent pedagogical mentor for AI, ML, Math, and CS subjects."""

    SUPPORTED_TOPICS = [
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Computer Vision",
        "Statistics & Probability",
        "Linear Algebra",
        "Python & Concurrency",
        "Data Structures & Algorithms",
        "DBMS & SQL",
    ]

    def __init__(self, router=None):
        self.router = router or llm_router

    async def explain_concept(
        self,
        concept: str,
        topic: Optional[str] = None,
        level: str = "intermediate",
        mode: str = "standard",
    ) -> str:
        """
        Explains an AIML or computer science concept tailored to requested level and mode.
        """
        level = level.lower().strip()
        mode = mode.lower().strip()

        # Select prompt persona
        if mode == "exam":
            system_prompt = EXAM_MODE_PROMPT
            mode_instruction = "Provide a comprehensive, high-scoring university examination answer."
        else:
            system_prompt = STANDARD_TUTOR_PROMPT
            mode_instruction = "Provide an intuitive analogy, mathematical formula, and practical Python implementation."

        user_content = (
            f"Please explain the concept: '{concept}'\n"
            f"Topic Category: {topic or 'AI / Computer Science'}\n"
            f"Student Academic Level: {level.upper()} (Charan - B.Tech AIML Student)\n"
            f"Instruction: {mode_instruction}"
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]

        logger.info(f"AIMLTutor generating explanation for '{concept}' [Level: {level}, Mode: {mode}]")
        response = await self.router.generate(messages, temperature=0.3)
        return response.content

    async def generate_quiz(
        self,
        topic: str = "Machine Learning",
        concept: Optional[str] = None,
        level: str = "intermediate",
    ) -> str:
        """Generates an interactive technical quiz question with options and hidden answer."""
        concept_str = f" focused on '{concept}'" if concept else ""
        user_content = (
            f"Generate a technical quiz challenge on '{topic}'{concept_str} "
            f"for a {level.upper()} level AIML student. "
            f"Do not give the answer away in the question. Include 4 distinct multiple-choice options."
        )

        messages = [
            ChatMessage(role="system", content=QUIZ_MODE_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

        logger.info(f"AIMLTutor generating quiz on topic '{topic}' [Level: {level}]")
        response = await self.router.generate(messages, temperature=0.5)
        return response.content

    async def evaluate_quiz_answer(
        self,
        quiz_question: str,
        user_answer: str,
    ) -> str:
        """Evaluates Charan's quiz answer and provides comprehensive feedback."""
        eval_prompt = (
            "You are evaluating a student's answer to an AIML quiz question.\n"
            f"Question:\n{quiz_question}\n\n"
            f"Student's Answer:\n{user_answer}\n\n"
            "State clearly whether the answer is CORRECT, PARTIALLY CORRECT, or INCORRECT. "
            "Explain the technical reasoning and any nuances."
        )

        messages = [
            ChatMessage(role="system", content=QUIZ_MODE_PROMPT),
            ChatMessage(role="user", content=eval_prompt),
        ]

        response = await self.router.generate(messages, temperature=0.2)
        return response.content


# Global tutor instance
aiml_tutor = AIMLTutor()

