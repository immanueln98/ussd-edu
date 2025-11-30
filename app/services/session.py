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
            "score": int
        },
        "chat_history": [...],      # Q&A pairs for SMS
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
    # Chat history methods
    # =========================================================================
    
    def add_chat_turn(
        self, 
        session_id: str, 
        question: str, 
        answer: str
    ) -> None:
        """Add a Q&A pair to chat history."""
        session = self.get_session(session_id)
        if session:
            session["chat_history"].append({
                "question": question,
                "answer": answer,
                "timestamp": datetime.utcnow().isoformat()
            })
            self.save_session(session_id, session)
    
    def get_chat_history(self, session_id: str) -> List[dict]:
        """Get chat history for SMS delivery."""
        session = self.get_session(session_id)
        if session:
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
