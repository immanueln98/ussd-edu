# LLM Quiz Integration Guide

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Technology Choices & Rationale](#2-technology-choices--rationale)
3. [Implementation](#3-implementation)
4. [Integration with Existing Demo](#4-integration-with-existing-demo)
5. [Testing & Debugging](#5-testing--debugging)
6. [Cost Analysis](#6-cost-analysis)

---

## 1. Architecture Overview

### The Core Challenge

USSD sessions have strict timeout constraints (15-30 seconds). Standard LLM API calls can take 5-30 seconds. We need a strategy that works within these limits.

### Solution: "Pre-Generate at Session Start"

```
┌─────────────────────────────────────────────────────────────────────┐
│                     QUIZ FLOW ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User selects "Quiz" + Topic + Count                                │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────┐                       │
│  │  LLM CALL (Groq - ~2-4 seconds)         │  ◄── ONE call only    │
│  │  Generate ALL questions at once         │                       │
│  │  Return as JSON array                   │                       │
│  └─────────────────────────────────────────┘                       │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────┐                       │
│  │  REDIS: Store questions in session      │                       │
│  └─────────────────────────────────────────┘                       │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────┐                       │
│  │  USSD: Show Q1 (instant from Redis)     │  ◄── No LLM latency   │
│  │  User answers...                        │                       │
│  │  Show Q2 (instant from Redis)           │                       │
│  │  User answers...                        │                       │
│  │  ... until complete                     │                       │
│  └─────────────────────────────────────────┘                       │
│         │                                                           │
│         ▼                                                           │
│  SMS: Send results                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

| Approach | Latency per Question | Total for 5 Questions | Verdict |
|----------|---------------------|----------------------|---------|
| Generate each question on-demand | 2-4s | 10-20s of waiting | ❌ Bad UX, timeout risk |
| Pre-generate all at start | 2-4s once | 2-4s total waiting | ✅ Good UX |

The user waits **once** when starting the quiz, then all subsequent interactions are instant.

---

## 2. Technology Choices & Rationale

### 2.1 LLM Provider: Groq

**What is Groq?**
Groq is an AI inference company that built custom hardware (LPU - Language Processing Unit) specifically for running LLMs extremely fast. They offer an API similar to OpenAI's but with much faster response times.

**Why Groq for this project?**

| Factor | Groq | OpenAI GPT-4o-mini | Claude Haiku |
|--------|------|-------------------|--------------|
| Speed | ~1,200 tokens/sec | ~100-200 tokens/sec | ~150-250 tokens/sec |
| Time for 200 tokens | ~0.17 seconds | ~1-2 seconds | ~0.8-1.3 seconds |
| Cost (per 1M input tokens) | $0.05 | $0.15 | $0.25 |
| Cost (per 1M output tokens) | $0.08 | $0.60 | $1.25 |
| USSD Compatible? | ✅ Excellent | ⚠️ Risky | ⚠️ Possible |

**Groq is 5-10x faster than alternatives** - this is critical for USSD where every second counts.

**Model Choice: Llama 3.1 8B**
- Fast inference (smaller model = faster)
- Excellent at structured output (JSON)
- Good reasoning for educational content
- Very cheap ($0.05/$0.08 per million tokens)

```python
# Groq model options for this use case:
MODELS = {
    "llama-3.1-8b-instant": {
        "speed": "fastest",
        "quality": "good for simple tasks",
        "use_for": "quiz generation, simple chat"
    },
    "llama-3.1-70b-versatile": {
        "speed": "fast",
        "quality": "better reasoning",
        "use_for": "complex explanations (use sparingly)"
    }
}
```

### 2.2 Python Package: `groq`

**What is it?**
The official Groq Python SDK. It provides a simple interface to call Groq's API, similar to OpenAI's SDK.

**Why use it?**
- Official SDK (maintained, reliable)
- Async support (important for FastAPI)
- Familiar interface if you've used OpenAI
- Handles retries, errors gracefully

```bash
pip install groq
```

```python
# Basic usage - synchronous
from groq import Groq
client = Groq(api_key="your-key")
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Hello"}]
)

# Async usage - for FastAPI
from groq import AsyncGroq
client = AsyncGroq(api_key="your-key")
response = await client.chat.completions.create(...)
```

### 2.3 JSON Parsing: `pydantic`

**What is Pydantic?**
A Python library for data validation using type hints. It ensures data matches expected structure.

**Why use it for LLM responses?**
LLMs can return malformed JSON. Pydantic:
- Validates the structure
- Provides clear error messages
- Converts types automatically
- Gives you autocomplete in your IDE

```python
from pydantic import BaseModel
from typing import List

class QuizQuestion(BaseModel):
    question: str
    answer: str
    difficulty: str = "easy"

class QuizResponse(BaseModel):
    questions: List[QuizQuestion]

# Parse LLM response safely
raw_json = '{"questions": [{"question": "2+2?", "answer": "4"}]}'
quiz = QuizResponse.model_validate_json(raw_json)
# Now quiz.questions[0].question is typed and validated
```

### 2.4 Async HTTP: Why It Matters

**The Problem with Sync Code:**
```python
# BLOCKING - bad for web servers
response = groq_client.generate(...)  # Server frozen for 3 seconds
# No other requests can be handled during this time
```

**The Solution - Async:**
```python
# NON-BLOCKING - good for web servers
response = await groq_client.generate(...)  # Server can handle other requests
# While waiting for Groq, FastAPI handles other USSD callbacks
```

FastAPI is async-native, and Groq's SDK supports async. Use `AsyncGroq` for best performance.

### 2.5 Technology Stack Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR EXISTING STACK                          │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI      │ Web framework (handles USSD callbacks)          │
│  Redis        │ Session storage (quiz state, questions)         │
│  httpx        │ HTTP client (SMS delivery)                      │
│  Pydantic     │ Data validation (already included in FastAPI)   │
└─────────────────────────────────────────────────────────────────┘
                              +
┌─────────────────────────────────────────────────────────────────┐
│                    NEW FOR LLM INTEGRATION                      │
├─────────────────────────────────────────────────────────────────┤
│  groq         │ LLM API client (fast inference)                 │
│  (pydantic)   │ Already have it - use for LLM response parsing  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementation

### 3.1 Install New Dependency

```bash
# Add to your virtual environment
pip install groq

# Or add to requirements.txt
echo "groq==0.4.2" >> requirements.txt
pip install -r requirements.txt
```

### 3.2 Update Environment Variables

Add to your `.env`:
```env
# Groq API Key
# Get from: https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# LLM Settings
LLM_MODEL=llama-3.1-8b-instant
LLM_TIMEOUT=10
LLM_MAX_TOKENS=500
```

### 3.3 Update Configuration

Update `app/config.py`:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration from environment variables."""
    
    # Africa's Talking
    at_username: str = "sandbox"
    at_api_key: str = ""
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Groq LLM - NEW
    groq_api_key: str = ""
    llm_model: str = "llama-3.1-8b-instant"
    llm_timeout: int = 10  # seconds
    llm_max_tokens: int = 500
    
    # App Settings
    debug: bool = True
    session_timeout: int = 300
    max_ussd_chars: int = 160
    
    # Feature Flags - NEW
    use_llm_quiz: bool = True  # Set to False to use pre-stored questions
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 3.4 Create LLM Service

Create new file `app/services/llm.py`:

```python
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
from typing import List, Optional
from pydantic import BaseModel, ValidationError
from groq import AsyncGroq
from app.config import get_settings

settings = get_settings()


# =============================================================================
# DATA MODELS (Pydantic)
# =============================================================================

class QuizQuestion(BaseModel):
    """Single quiz question structure."""
    question: str
    answer: str
    
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
```

### 3.5 Create Quiz Service (Combines LLM + Fallback)

Create new file `app/services/quiz.py`:

```python
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
```

### 3.6 Update Session Manager for LLM Quiz

Update `app/services/session.py` - add this method to the `SessionManager` class:

```python
# Add to SessionManager class in app/services/session.py

def start_quiz_v2(
    self, 
    session_id: str, 
    topic: str, 
    questions: List[dict],
    source: str = "static"
) -> Dict[str, Any]:
    """
    Initialize quiz state with questions from any source.
    
    Args:
        session_id: USSD session ID
        topic: Quiz topic
        questions: List of {"question": "...", "answer": "..."}
        source: "llm" or "static" (for analytics)
    """
    session = self.get_session(session_id)
    if session:
        session["current_menu"] = "quiz"
        session["topic"] = topic
        session["quiz_state"] = {
            "questions": questions,
            "current_index": 0,
            "answers": [],
            "score": 0,
            "total": len(questions),
            "source": source  # Track if LLM or static
        }
        self.save_session(session_id, session)
    return session
```

---

## 4. Integration with Existing Demo

### 4.1 Update USSD Router

Update `app/routers/ussd.py` to use the new quiz service.

**Add imports at the top:**

```python
from app.services.quiz import quiz_service
```

**Replace the `handle_quiz_path` function:**

```python
async def handle_quiz_path(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """
    Handle the Quiz path with LLM integration.
    
    Flow:
    2 → Show topics
    2*1 → Select topic, ask question count
    2*1*5 → Generate questions with LLM, start quiz
    2*1*5*7 → Answer question
    """
    
    # Check if quiz is already in progress
    if session.get("quiz_state"):
        return await handle_quiz_in_progress(
            session, session_id, phone_number,
            sub_input, background_tasks
        )
    
    # Step 1: Show topic selection
    if not sub_input or sub_input == ['']:
        return topic_menu("quiz")
    
    topic_choice = sub_input[0]
    
    # Handle back
    if topic_choice == '0':
        return main_menu()
    
    # Invalid topic
    if topic_choice not in TOPICS:
        return topic_menu("quiz")
    
    topic_key = TOPICS[topic_choice]["key"]
    topic_name = TOPICS[topic_choice]["name"]
    
    # Step 2: Ask for question count
    if len(sub_input) == 1:
        return (
            f"CON {topic_name} Quiz\n\n"
            f"How many questions?\n"
            f"Enter: 3, 5, or 10"
        )
    
    # Step 3: Generate questions and start quiz
    if len(sub_input) == 2:
        try:
            count = int(sub_input[1])
            if count not in [3, 5, 10]:
                count = 5
        except ValueError:
            count = 5
        
        # NEW: Use quiz service (LLM with fallback)
        quiz_data = await quiz_service.get_questions(
            topic=topic_key,
            count=count,
            difficulty="easy"
        )
        
        questions = quiz_data["questions"]
        source = quiz_data["source"]
        
        # Start quiz with questions
        session = session_manager.start_quiz_v2(
            session_id, 
            topic_key, 
            questions,
            source
        )
        
        # Show loading message if using LLM (optional UX enhancement)
        return show_question(session_id)
    
    # Step 4+: Process answer
    return await process_quiz_answer(
        session, session_id, phone_number,
        sub_input[-1], background_tasks
    )


async def handle_quiz_in_progress(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """Handle input when quiz is already active."""
    
    if not sub_input or sub_input == ['']:
        return show_question(session_id)
    
    answer = sub_input[-1]
    
    return await process_quiz_answer(
        session, session_id, phone_number,
        answer, background_tasks
    )


async def process_quiz_answer(
    session: dict,
    session_id: str,
    phone_number: str,
    answer: str,
    background_tasks: BackgroundTasks
) -> str:
    """Process a quiz answer and show next question or results."""
    
    result = session_manager.submit_answer(session_id, answer)
    
    if "error" in result:
        return f"END {result['error']}"
    
    # Build feedback
    if result["correct"]:
        feedback = "✓ Correct!"
    else:
        feedback = f"✗ Wrong. Answer: {result['correct_answer']}"
    
    # Check if complete
    if result["is_complete"]:
        quiz_results = session_manager.get_quiz_results(session_id)
        
        # Send results via SMS
        background_tasks.add_task(
            sms_service.send_quiz_results,
            phone_number,
            quiz_results
        )
        
        score = result["score"]
        total = result["total"]
        pct = round((score / total) * 100)
        
        emoji = "⭐" if pct >= 80 else ("👍" if pct >= 60 else "📚")
        
        # Include source in completion message (optional, for debugging)
        source_note = ""
        if session.get("quiz_state", {}).get("source") == "llm":
            source_note = "\n(AI-generated quiz)"
        
        return (
            f"END {feedback}\n\n"
            f"Quiz Complete! {emoji}\n"
            f"Score: {score}/{total} ({pct}%){source_note}\n\n"
            f"Full results sent via SMS!"
        )
    
    # Show next question
    q_data = session_manager.get_current_question(session_id)
    q = q_data["question"]
    num = q_data["number"]
    total = q_data["total"]
    
    return (
        f"CON {feedback}\n\n"
        f"Q{num} of {total}\n"
        f"{q['question']}\n\n"
        f"Enter your answer:"
    )
```

**Update the router to be async:**

Make sure the callback is async:

```python
@router.post("/ussd/callback", response_class=PlainTextResponse)
async def ussd_callback(
    background_tasks: BackgroundTasks,
    sessionId: str = Form(...),
    phoneNumber: str = Form(...),
    serviceCode: str = Form(...),
    text: str = Form("")
):
    # ... existing code ...
    
    # Update route_request call to be async
    response = await route_request(
        session=session,
        session_id=sessionId,
        phone_number=phoneNumber,
        user_input=user_input,
        background_tasks=background_tasks
    )
    
    return response


async def route_request(...) -> str:
    """Make this async too."""
    # ... existing code ...
    
    if first_choice == '2':
        # Quiz path - now async
        return await handle_quiz_path(
            session, session_id, phone_number,
            user_input[1:], background_tasks
        )
    
    # ... rest of function ...
```

### 4.2 Add LLM Health Check Endpoint

Update `app/main.py`:

```python
@app.get("/health/llm")
async def llm_health():
    """Check LLM service health and response time."""
    from app.services.llm import llm_service
    return await llm_service.health_check()
```

---

## 5. Testing & Debugging

### 5.1 Test LLM Service Directly

Create `test_llm.py` in your project root:

```python
#!/usr/bin/env python3
"""
Test LLM quiz generation directly.
Run: python test_llm.py
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.llm import llm_service
from app.services.quiz import quiz_service


async def test_llm_direct():
    """Test LLM service directly."""
    print("=" * 50)
    print("Testing LLM Service")
    print("=" * 50)
    
    # Health check
    print("\n1. Health Check:")
    health = await llm_service.health_check()
    print(f"   Status: {health['status']}")
    if health.get('response_time_ms'):
        print(f"   Response time: {health['response_time_ms']}ms")
    
    if not health['healthy']:
        print("   ❌ LLM not healthy, check API key")
        return
    
    # Generate quiz
    print("\n2. Generate Addition Quiz (5 questions):")
    import time
    start = time.time()
    
    questions = await llm_service.generate_quiz(
        topic="addition",
        count=5,
        difficulty="easy"
    )
    
    elapsed = time.time() - start
    print(f"   Time: {elapsed:.2f}s")
    
    if questions:
        print(f"   ✓ Generated {len(questions)} questions:")
        for i, q in enumerate(questions, 1):
            print(f"      Q{i}: {q['question']} = {q['answer']}")
    else:
        print("   ❌ Failed to generate questions")


async def test_quiz_service():
    """Test quiz service with fallback."""
    print("\n" + "=" * 50)
    print("Testing Quiz Service (with fallback)")
    print("=" * 50)
    
    # Test with LLM
    print("\n1. With LLM enabled:")
    result = await quiz_service.get_questions(
        topic="multiplication",
        count=3,
        force_llm=True
    )
    print(f"   Source: {result['source']}")
    print(f"   Questions: {result['count']}")
    for q in result['questions']:
        print(f"      - {q['question']}")
    
    # Test fallback
    print("\n2. With static fallback:")
    result = await quiz_service.get_questions(
        topic="subtraction",
        count=3,
        force_static=True
    )
    print(f"   Source: {result['source']}")
    print(f"   Questions: {result['count']}")


async def main():
    await test_llm_direct()
    await test_quiz_service()
    print("\n✓ All tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
python test_llm.py
```

### 5.2 Test via API

```bash
# Start server
uvicorn app.main:app --reload --port 8000

# Check LLM health
curl http://localhost:8000/health/llm

# Test full quiz flow via USSD simulator
python test_ussd.py
```

### 5.3 Debug Mode Logging

The LLM service includes print statements for debugging:
- `[LLM] Generated X questions for topic`
- `[LLM] Timeout after Xs`
- `[LLM] JSON parse error: ...`
- `[Quiz] Using LLM-generated questions`
- `[Quiz] Using static questions`

For production, replace with proper logging:

```python
import logging
logger = logging.getLogger(__name__)

# Replace print() with:
logger.info(f"Generated {len(questions)} questions")
logger.error(f"Timeout after {self.timeout}s")
```

---

## 6. Cost Analysis

### 6.1 Per-Quiz LLM Cost

```
Model: llama-3.1-8b-instant
Prompt tokens: ~250 (our prompt)
Output tokens: ~150 (5 questions as JSON)

Cost per quiz:
  Input:  250 tokens × $0.05/1M = $0.0000125
  Output: 150 tokens × $0.08/1M = $0.000012
  Total:  ~$0.000025 per quiz

In Pula (BWP):
  $0.000025 × 13.5 = BWP 0.00034 per quiz
  
That's essentially FREE.
```

### 6.2 Monthly Cost Estimate

| Daily Users | Quizzes/User | Monthly Quizzes | LLM Cost (USD) |
|-------------|--------------|-----------------|----------------|
| 100 | 2 | 6,000 | $0.15 |
| 1,000 | 2 | 60,000 | $1.50 |
| 10,000 | 2 | 600,000 | $15.00 |

**The LLM cost is negligible.** Your main costs will be:
- USSD session fees (from MNO/aggregator)
- SMS delivery fees

### 6.3 Groq Free Tier

Groq offers a generous free tier:
- Rate limit: ~30 requests/minute
- Daily limit: Check console.groq.com

For a pilot with <1,000 daily users, you may not even need to pay.

---

## Summary

### What You've Added

1. **Groq Integration** - Fast LLM inference (~2-4 seconds)
2. **Quiz Generation** - AI-generated questions per topic
3. **Fallback System** - Static questions if LLM fails
4. **Pydantic Validation** - Safe JSON parsing
5. **Async Architecture** - Non-blocking for FastAPI

### File Changes

```
app/
├── config.py           # Updated with Groq settings
├── services/
│   ├── llm.py          # NEW: LLM service
│   ├── quiz.py         # NEW: Quiz orchestration
│   └── session.py      # Updated: start_quiz_v2()
└── routers/
    └── ussd.py         # Updated: async quiz handlers

test_llm.py             # NEW: LLM testing script
```

### Quick Start After Integration

```bash
# 1. Add Groq API key to .env
echo "GROQ_API_KEY=gsk_your_key_here" >> .env

# 2. Install dependency
pip install groq

# 3. Test LLM
python test_llm.py

# 4. Run server
uvicorn app.main:app --reload

# 5. Test quiz flow
python test_ussd.py
```

---

## Next Steps

Once this is working, let me know and I'll create the **Live Chat** guide which is more complex due to:
- Real-time response generation
- Conversation context management
- Aggressive prompt optimization for brevity
- Timeout handling with SMS fallback
