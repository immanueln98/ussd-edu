"""
Session management for USSD interactions.
Uses Redis for fast state storage with automatic expiration.
"""

import redis
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.config import get_settings

settings = get_settings()


class SessionManager:
    """
    Manages USSD session state in Redis.

    Session structure:
    {
        "session_id": str,
        "phone_number": str,
        "current_menu": str,        # main, learn, quiz, chat
        "topic": str | None,        # addition, subtraction, etc.
        "quiz_state": {             # Only during quiz
            "questions": [...],
            "current_index": int,
            "answers": [...],
            "score": int,
            "source": str           # llm or static
        },
        "chat_state": {             # Only during chat (Phase 3)
            "topic": str,
            "conversation_type": str | None,  # explain, example, solve, free
            "context_window": [...],          # Last 3 turns for LLM
            "full_history": [...],            # All turns for SMS
            "turn_count": int,
            "timeout_count": int,
            "started_at": str
        },
        "chat_history": [...],      # Deprecated - use chat_state.full_history
        "created_at": str,
        "last_activity": str
    }
    """
    
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True
        )
        self.timeout = settings.session_timeout
    
    def _key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"ussd:session:{session_id}"
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session from Redis."""
        data = self.redis.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None
    
    def create_session(self, session_id: str, phone_number: str) -> Dict[str, Any]:
        """Create new session with initial state."""
        session = {
            "session_id": session_id,
            "phone_number": phone_number,
            "current_menu": "main",
            "topic": None,
            "quiz_state": None,
            "chat_state": None,
            "chat_history": [],
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        self.save_session(session_id, session)
        return session
    
    def save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """Save session to Redis with TTL."""
        data["last_activity"] = datetime.utcnow().isoformat()
        self.redis.setex(
            self._key(session_id),
            self.timeout,
            json.dumps(data)
        )
    
    def update_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """Update specific fields in session."""
        session = self.get_session(session_id)
        if session:
            session.update(kwargs)
            self.save_session(session_id, session)
        return session
    
    # =========================================================================
    # Quiz-specific methods
    # =========================================================================
    
    def start_quiz(
        self,
        session_id: str,
        topic: str,
        questions: List[dict]
    ) -> Dict[str, Any]:
        """Initialize quiz state."""
        session = self.get_session(session_id)
        if session:
            session["current_menu"] = "quiz"
            session["topic"] = topic
            session["quiz_state"] = {
                "questions": questions,
                "current_index": 0,
                "answers": [],
                "score": 0,
                "total": len(questions)
            }
            self.save_session(session_id, session)
        return session

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

    def get_current_question(self, session_id: str) -> Optional[dict]:
        """Get the current quiz question."""
        session = self.get_session(session_id)
        if session and session.get("quiz_state"):
            qs = session["quiz_state"]
            idx = qs["current_index"]
            if idx < len(qs["questions"]):
                return {
                    "question": qs["questions"][idx],
                    "number": idx + 1,
                    "total": qs["total"]
                }
        return None
    
    def submit_answer(
        self, 
        session_id: str, 
        user_answer: str
    ) -> Dict[str, Any]:
        """
        Submit answer for current question.
        Returns: {correct: bool, correct_answer: str, is_complete: bool}
        """
        session = self.get_session(session_id)
        if not session or not session.get("quiz_state"):
            return {"error": "No active quiz"}
        
        qs = session["quiz_state"]
        idx = qs["current_index"]
        
        if idx >= len(qs["questions"]):
            return {"error": "Quiz already complete"}
        
        question = qs["questions"][idx]
        correct_answer = str(question["answer"]).strip()
        user_answer = str(user_answer).strip()
        
        is_correct = user_answer == correct_answer
        
        # Record the answer
        qs["answers"].append({
            "question": question["question"],
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct
        })
        
        if is_correct:
            qs["score"] += 1
        
        # Move to next question
        qs["current_index"] += 1
        is_complete = qs["current_index"] >= len(qs["questions"])
        
        self.save_session(session_id, session)
        
        return {
            "correct": is_correct,
            "correct_answer": correct_answer,
            "is_complete": is_complete,
            "score": qs["score"],
            "total": qs["total"]
        }
    
    def get_quiz_results(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get complete quiz results for SMS delivery."""
        session = self.get_session(session_id)
        if session and session.get("quiz_state"):
            qs = session["quiz_state"]
            return {
                "topic": session.get("topic"),
                "score": qs["score"],
                "total": qs["total"],
                "percentage": round((qs["score"] / qs["total"]) * 100) if qs["total"] > 0 else 0,
                "answers": qs["answers"]
            }
        return None
    
    # =========================================================================
    # Chat-specific methods (Phase 3)
    # =========================================================================

    def start_chat(
        self,
        session_id: str,
        topic: str
    ) -> Dict[str, Any]:
        """
        Initialize chat state for a new conversation.

        Args:
            session_id: USSD session ID
            topic: Chat topic (addition, subtraction, etc.)

        Returns:
            Updated session
        """
        session = self.get_session(session_id)
        if session:
            session["current_menu"] = "chat"
            session["topic"] = topic
            session["chat_state"] = {
                "active": True,                 # Mark chat as active
                "topic": topic,
                "conversation_type": None,
                "context_window": [],           # Last 3 turns for LLM
                "full_history": [],             # All turns for SMS
                "turn_count": 0,
                "timeout_count": 0,
                "started_at": datetime.utcnow().isoformat()
            }
            self.save_session(session_id, session)
        return session

    def set_chat_topic(
        self,
        session_id: str,
        topic: str,
        clear_context: bool = True
    ) -> Dict[str, Any]:
        """
        Change chat topic mid-conversation.

        Args:
            session_id: USSD session ID
            topic: New topic
            clear_context: If True, clear context window (fresh start)

        Returns:
            Updated session
        """
        session = self.get_session(session_id)
        if session and session.get("chat_state"):
            session["chat_state"]["topic"] = topic
            session["topic"] = topic
            if clear_context:
                session["chat_state"]["context_window"] = []
            self.save_session(session_id, session)
        return session

    def set_conversation_type(
        self,
        session_id: str,
        conv_type: str
    ) -> Dict[str, Any]:
        """
        Set conversation type (explain, example, solve, free).

        Args:
            session_id: USSD session ID
            conv_type: Conversation type

        Returns:
            Updated session
        """
        session = self.get_session(session_id)
        if session and session.get("chat_state"):
            session["chat_state"]["conversation_type"] = conv_type
            self.save_session(session_id, session)
        return session

    def get_chat_context(self, session_id: str) -> List[dict]:
        """
        Get context window (last 3 turns) for LLM prompt.

        Returns:
            List of {"role": "user"/"assistant", "content": "..."}
        """
        session = self.get_session(session_id)
        if session and session.get("chat_state"):
            return session["chat_state"].get("context_window", [])
        return []

    def add_chat_turn(
        self,
        session_id: str,
        question: str,
        answer_short: str,
        answer_full: str = None,
        was_truncated: bool = False,
        was_timeout: bool = False
    ) -> Dict[str, Any]:
        """
        Add a Q&A turn to chat state with sliding window.

        Maintains:
        - context_window: Last 3 turns for LLM (sliding)
        - full_history: All turns for SMS

        Args:
            session_id: USSD session ID
            question: User's question
            answer_short: Truncated answer for USSD (≤90 chars)
            answer_full: Full answer for SMS
            was_truncated: Whether answer was truncated
            was_timeout: Whether LLM timed out

        Returns:
            Updated session
        """
        session = self.get_session(session_id)
        if not session or not session.get("chat_state"):
            return session

        chat_state = session["chat_state"]
        answer_full = answer_full or answer_short

        # Add to context window for LLM (sliding window of 3 turns)
        chat_state["context_window"].append({"role": "user", "content": question})
        chat_state["context_window"].append({"role": "assistant", "content": answer_short})

        # Keep only last 3 turns (6 messages: 3 Q&A pairs)
        max_messages = settings.chat_context_turns * 2  # 3 turns = 6 messages
        if len(chat_state["context_window"]) > max_messages:
            # Remove oldest turn (first 2 messages)
            chat_state["context_window"] = chat_state["context_window"][2:]

        # Add to full history for SMS
        chat_state["full_history"].append({
            "question": question,
            "answer_short": answer_short,
            "answer_full": answer_full,
            "was_truncated": was_truncated,
            "was_timeout": was_timeout,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Update counters
        chat_state["turn_count"] += 1
        if was_timeout:
            chat_state["timeout_count"] += 1

        self.save_session(session_id, session)
        return session

    def get_chat_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chat statistics for analytics or end summary.

        Returns:
            {topic, turn_count, timeout_count, conversation_type, started_at}
        """
        session = self.get_session(session_id)
        if session and session.get("chat_state"):
            cs = session["chat_state"]
            return {
                "topic": cs.get("topic"),
                "conversation_type": cs.get("conversation_type"),
                "turn_count": cs.get("turn_count", 0),
                "timeout_count": cs.get("timeout_count", 0),
                "started_at": cs.get("started_at"),
                "full_history": cs.get("full_history", [])
            }
        return None

    # =========================================================================
    # Legacy chat history methods (kept for backwards compatibility)
    # =========================================================================

    def get_chat_history(self, session_id: str) -> List[dict]:
        """
        Get chat history for SMS delivery.

        Note: For Phase 3 chat, use chat_state.full_history instead.
        This method is kept for backwards compatibility.
        """
        session = self.get_session(session_id)
        if session:
            # Try new chat_state first
            if session.get("chat_state"):
                return session["chat_state"].get("full_history", [])
            # Fall back to legacy chat_history
            return session.get("chat_history", [])
        return []
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def delete_session(self, session_id: str) -> None:
        """Remove session from Redis."""
        self.redis.delete(self._key(session_id))


# Singleton instance
session_manager = SessionManager()
