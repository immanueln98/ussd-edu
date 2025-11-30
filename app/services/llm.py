"""
LLM Service for Quiz Generation

Uses Groq API for fast inference. Generates quiz questions
as structured JSON that can be parsed reliably.

Key Design Decisions:
1. Async-first: Non-blocking for FastAPI compatibility
2. Structured output: JSON with Pydantic validation
3. Fallback: Returns None on failure, caller handles fallback
4. Timeout: Hard 10-second limit to stay within USSD constraints
"""

import json
import asyncio
from typing import List, Optional, Union
from pydantic import BaseModel, ValidationError, field_validator
from groq import AsyncGroq
from app.config import get_settings

settings = get_settings()


# =============================================================================
# DATA MODELS (Pydantic)
# =============================================================================

class QuizQuestion(BaseModel):
    """Single quiz question structure."""
    question: str
    answer: Union[str, int]  # Accept both str and int from LLM

    @field_validator('answer')
    @classmethod
    def convert_answer_to_string(cls, v):
        """Convert answer to string if it's an integer."""
        return str(v)

    class Config:
        # Allow extra fields from LLM (we'll ignore them)
        extra = "ignore"


class GeneratedQuiz(BaseModel):
    """Complete quiz response from LLM."""
    questions: List[QuizQuestion]


# =============================================================================
# PROMPTS
# =============================================================================

def get_quiz_prompt(topic: str, count: int, difficulty: str = "easy") -> str:
    """
    Build the prompt for quiz generation.

    Key prompt engineering techniques used:
    1. Clear role definition ("You are a primary school maths teacher")
    2. Explicit output format (JSON schema)
    3. Constraints (difficulty, answer format)
    4. Examples (helps LLM understand expected format)
    5. Strict instruction ("Output ONLY valid JSON")
    """

    # Topic-specific guidance
    topic_guidance = {
        "addition": "Use numbers between 1-20. Answers should be under 30.",
        "subtraction": "Use numbers between 1-20. No negative answers.",
        "multiplication": "Use times tables 1-10. Keep it simple.",
        "division": "Use numbers that divide evenly. No remainders.",
    }

    guidance = topic_guidance.get(topic, "Keep questions simple.")

    prompt = f"""You are a primary school maths teacher in Botswana creating a quiz.

Generate exactly {count} {topic} questions for primary school students.

RULES:
- Difficulty: {difficulty}
- {guidance}
- Answers must be single numbers (no fractions, no words)
- Questions should be clear and simple
- Vary the numbers used

OUTPUT FORMAT:
Return ONLY a valid JSON object with this exact structure:
{{"questions": [{{"question": "What is 2 + 3?", "answer": "5"}}, {{"question": "What is 4 + 1?", "answer": "5"}}]}}

IMPORTANT:
- Output ONLY the JSON object
- No markdown, no explanation, no extra text
- Ensure valid JSON syntax (proper quotes, commas)

Generate {count} {topic} questions now:"""

    return prompt


# =============================================================================
# LLM SERVICE CLASS
# =============================================================================

class LLMService:
    """
    Handles all LLM interactions for the application.

    Currently supports:
    - Quiz generation

    Future (Phase 3):
    - Live chat
    - Lesson explanations
    """

    def __init__(self):
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.max_tokens = settings.llm_max_tokens

    async def generate_quiz(
        self,
        topic: str,
        count: int = 5,
        difficulty: str = "easy"
    ) -> Optional[List[dict]]:
        """
        Generate quiz questions using LLM.

        Args:
            topic: Math topic (addition, subtraction, etc.)
            count: Number of questions (3, 5, or 10)
            difficulty: easy, medium, or hard

        Returns:
            List of question dicts: [{"question": "...", "answer": "..."}, ...]
            Returns None if generation fails (caller should use fallback)

        Time Budget:
            - Groq API call: ~2-4 seconds typical
            - JSON parsing: ~10ms
            - Total: <5 seconds (well within 15s USSD timeout)
        """

        if not settings.groq_api_key:
            print("[LLM] No API key configured, using fallback")
            return None

        prompt = get_quiz_prompt(topic, count, difficulty)

        try:
            # Wrap in timeout to ensure we don't exceed USSD limits
            async with asyncio.timeout(self.timeout):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful maths teacher. Always respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7,  # Some variety in questions
                )

            # Extract the response text
            raw_response = response.choices[0].message.content.strip()

            # Parse and validate JSON
            questions = self._parse_quiz_response(raw_response)

            if questions and len(questions) >= count:
                print(f"[LLM] Generated {len(questions)} questions for {topic}")
                return questions[:count]  # Return exactly requested count
            else:
                print(f"[LLM] Insufficient questions generated: {len(questions) if questions else 0}")
                return None

        except asyncio.TimeoutError:
            print(f"[LLM] Timeout after {self.timeout}s")
            return None
        except Exception as e:
            print(f"[LLM] Error: {type(e).__name__}: {str(e)}")
            return None

    def _parse_quiz_response(self, raw_response: str) -> Optional[List[dict]]:
        """
        Parse LLM response into structured quiz questions.

        Handles common LLM quirks:
        - Markdown code blocks (```json ... ```)
        - Extra whitespace
        - Minor JSON issues
        """

        # Clean up common LLM response issues
        cleaned = raw_response.strip()

        # Remove markdown code blocks if present
        if cleaned.startswith("```"):
            # Extract content between ``` markers
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            # Try parsing as our expected structure
            parsed = json.loads(cleaned)

            # Validate with Pydantic
            quiz = GeneratedQuiz.model_validate(parsed)

            # Convert to list of dicts for compatibility with existing code
            return [{"question": q.question, "answer": q.answer} for q in quiz.questions]

        except json.JSONDecodeError as e:
            print(f"[LLM] JSON parse error: {e}")
            print(f"[LLM] Raw response: {cleaned[:200]}...")
            return None
        except ValidationError as e:
            print(f"[LLM] Validation error: {e}")
            return None

    async def health_check(self) -> dict:
        """
        Test LLM connectivity and response time.
        Useful for debugging and monitoring.
        """
        import time

        if not settings.groq_api_key:
            return {"status": "no_api_key", "healthy": False}

        start = time.time()

        try:
            async with asyncio.timeout(5):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Say 'OK' only."}],
                    max_tokens=5
                )

            elapsed = time.time() - start

            return {
                "status": "healthy",
                "healthy": True,
                "response_time_ms": round(elapsed * 1000),
                "model": self.model
            }
        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "error": str(e)
            }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Create single instance to reuse connection
llm_service = LLMService()
