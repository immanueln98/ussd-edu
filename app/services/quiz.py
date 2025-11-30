"""
Quiz Service

Orchestrates quiz generation with intelligent fallback.
If LLM fails or is disabled, falls back to pre-stored questions.

This separation of concerns means:
- LLM service handles API communication
- Quiz service handles business logic and fallback
- USSD router stays clean and simple
"""

from typing import List, Optional
from app.services.llm import llm_service
from app.data.content import get_quiz_questions as get_static_questions
from app.config import get_settings

settings = get_settings()


class QuizService:
    """
    Manages quiz question generation with fallback strategy.

    Strategy:
    1. If LLM enabled → Try LLM generation
    2. If LLM fails or disabled → Use pre-stored questions
    3. Always return questions (graceful degradation)
    """

    async def get_questions(
        self,
        topic: str,
        count: int = 5,
        difficulty: str = "easy",
        force_llm: bool = False,
        force_static: bool = False
    ) -> dict:
        """
        Get quiz questions, with automatic fallback.

        Args:
            topic: Math topic (addition, subtraction, etc.)
            count: Number of questions
            difficulty: easy, medium, hard
            force_llm: Force LLM generation (for testing)
            force_static: Force static questions (for testing)

        Returns:
            {
                "questions": [...],
                "source": "llm" | "static",
                "count": int
            }
        """

        # Validate count
        count = min(max(count, 1), 10)  # Between 1 and 10

        # Check if we should use LLM
        use_llm = (settings.use_llm_quiz or force_llm) and not force_static

        questions = None
        source = "static"

        if use_llm and settings.groq_api_key:
            # Try LLM generation
            questions = await llm_service.generate_quiz(
                topic=topic,
                count=count,
                difficulty=difficulty
            )

            if questions:
                source = "llm"
                print(f"[Quiz] Using LLM-generated questions for {topic}")

        # Fallback to static if LLM failed or disabled
        if not questions:
            questions = get_static_questions(topic, count)
            source = "static"
            print(f"[Quiz] Using static questions for {topic}")

        return {
            "questions": questions,
            "source": source,
            "count": len(questions)
        }

    def validate_answer(self, user_answer: str, correct_answer: str) -> bool:
        """
        Check if user's answer is correct.

        Handles common variations:
        - Whitespace: "5 " → "5"
        - Leading zeros: "05" → "5" (maybe)
        """
        user = str(user_answer).strip().lower()
        correct = str(correct_answer).strip().lower()

        # Direct match
        if user == correct:
            return True

        # Numeric comparison (handles "5.0" == "5")
        try:
            return float(user) == float(correct)
        except ValueError:
            return False


# Singleton
quiz_service = QuizService()
