"""
SMS Service for Africa's Talking API.
Handles sending lesson content, quiz results, and chat history.
"""

import httpx
import asyncio
from typing import List, Optional
from app.config import get_settings

settings = get_settings()


class SMSService:
    """
    Africa's Talking SMS integration.
    
    Sandbox URL: https://api.sandbox.africastalking.com/version1/messaging
    Production URL: https://api.africastalking.com/version1/messaging
    """
    
    def __init__(self):
        # Use sandbox for development
        self.base_url = "https://api.sandbox.africastalking.com/version1/messaging"
        self.username = settings.at_username
        self.api_key = settings.at_api_key
    
    def _chunk_message(self, text: str, limit: int = 160) -> List[str]:
        """
        Split long messages into SMS-safe chunks.

        Note: Using 160 for single SMS (GSM-7 encoding).
        For multi-part, network handles concatenation.
        We avoid emojis to stay in GSM-7 (not Unicode).
        """
        chunks = []
        
        while len(text) > limit:
            # Find last space before limit
            break_point = text.rfind(' ', 0, limit)
            if break_point == -1:
                break_point = limit
            
            chunks.append(text[:break_point].strip())
            text = text[break_point:].strip()
        
        if text:
            chunks.append(text)
        
        return chunks
    
    async def send_sms(
        self, 
        phone_number: str, 
        message: str,
        chunk: bool = True
    ) -> dict:
        """
        Send SMS via Africa's Talking.
        
        Args:
            phone_number: Recipient in E.164 format (+267...)
            message: Message content
            chunk: If True, split long messages
        
        Returns:
            API response dict
        """
        if not self.api_key:
            print(f"[SMS DEBUG] Would send to {phone_number}:\n{message}")
            return {"status": "debug_mode", "message": message}
        
        chunks = self._chunk_message(message) if chunk else [message]
        results = []
        
        async with httpx.AsyncClient(timeout=30) as client:
            for i, chunk_text in enumerate(chunks):
                try:
                    response = await client.post(
                        self.base_url,
                        headers={
                            "apiKey": self.api_key,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Accept": "application/json"
                        },
                        data={
                            "username": self.username,
                            "to": phone_number,
                            "message": chunk_text
                        }
                    )
                    results.append({
                        "chunk": i + 1,
                        "status": response.status_code,
                        "response": response.json() if response.status_code == 201 else response.text
                    })
                except Exception as e:
                    results.append({
                        "chunk": i + 1,
                        "error": str(e)
                    })
        
        return {
            "total_chunks": len(chunks),
            "results": results
        }
    
    async def send_lesson(
        self, 
        phone_number: str, 
        lesson: dict
    ) -> dict:
        """Send lesson content via SMS."""
        return await self.send_sms(phone_number, lesson["content"])
    
    async def send_quiz_results(
        self,
        phone_number: str,
        results: dict
    ) -> dict:
        """
        Format and send quiz results - OPTIMIZED for cost savings.

        Optimizations:
        - No emojis (stays in GSM-7 encoding: 160 chars/SMS vs 70 chars/SMS)
        - Only shows incorrect answers (saves space)
        - Compact format to minimize SMS count

        results: {
            topic: str,
            score: int,
            total: int,
            percentage: int,
            answers: [{question, user_answer, correct_answer, is_correct}, ...]
        }
        """
        topic = results.get("topic", "Maths").title()
        score = results["score"]
        total = results["total"]
        pct = results["percentage"]

        # Compact header without emojis
        lines = [
            f"QUIZ RESULTS - {topic}",
            f"Score: {score}/{total} ({pct}%)"
        ]

        # Performance message (no emoji)
        if pct >= 80:
            lines.append("Excellent work!")
        elif pct >= 60:
            lines.append("Good job!")
        else:
            lines.append("Keep practicing!")

        # Only show WRONG answers to save space
        wrong_answers = [ans for ans in results["answers"] if not ans["is_correct"]]

        if wrong_answers:
            lines.append("")
            lines.append("Review these:")
            for ans in wrong_answers:
                # Find original question number
                q_num = results["answers"].index(ans) + 1
                # Compact format: "Q2: 3x4=? You:10 Ans:12"
                q_text = ans['question'].replace(" × ", "x").replace(" + ", "+").replace(" - ", "-").replace(" ÷ ", "/")
                lines.append(f"Q{q_num}: {q_text}")
                lines.append(f"You:{ans['user_answer']} Ans:{ans['correct_answer']}")
        else:
            lines.append("")
            lines.append("Perfect score! All correct!")

        lines.append("")
        lines.append("Dial back to practice more!")

        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)
    
    async def send_chat_history(
        self,
        phone_number: str,
        history: List[dict],
        topic: Optional[str] = None
    ) -> dict:
        """
        Send chat conversation history via SMS - OPTIMIZED for cost savings.

        Optimizations:
        - No emojis (stays in GSM-7)
        - Compact format
        - Truncated content to fit more in fewer SMS

        history: [{question, answer, timestamp}, ...]
        """
        if not history:
            return {"status": "no_history"}

        lines = [
            f"CHAT HISTORY - {topic.title() if topic else 'Maths'}",
            ""
        ]

        for i, turn in enumerate(history, 1):
            # Truncate for compactness
            q = turn["question"][:45]
            a = turn["answer"][:80]

            lines.append(f"Q{i}: {q}")
            lines.append(f"A{i}: {a}")
            if i < len(history):  # No blank line after last entry
                lines.append("")

        lines.append("")
        lines.append("Dial back anytime!")

        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)

    async def send_chat_timeout_response(
        self,
        phone_number: str,
        question: str,
        answer: str
    ) -> dict:
        """
        Send SMS when LLM timed out during USSD session.

        Called from background task after LLM eventually responds.
        Optimized: No emojis (GSM-7 encoding).

        Args:
            phone_number: Recipient phone number
            question: User's original question
            answer: LLM's full answer (may be long)
        """
        # Truncate question if too long
        q_display = question[:50] + "..." if len(question) > 50 else question

        lines = [
            "EduBot - Answer to your question",
            "",
            f"Q: {q_display}",
            "",
            f"A: {answer}",
            "",
            "Dial back to continue chatting!"
        ]

        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)

    async def send_session_summary(
        self,
        phone_number: str,
        lesson_topic: Optional[str] = None,
        quiz_results: Optional[dict] = None,
        chat_history: Optional[dict] = None
    ) -> dict:
        """
        Send complete session summary when user exits - OPTIMIZED for cost savings.

        Optimizations:
        - No emojis (stays in GSM-7)
        - Compact format
        - Minimal content to reduce SMS count

        Combines all activities into one SMS (or multiple if needed).

        Args:
            chat_history: Chat summary dict with 'full_history', 'topic', etc.
        """
        lines = ["EDUBOT SESSION SUMMARY", ""]

        if lesson_topic:
            lines.append(f"Lesson: {lesson_topic.title()}")

        if quiz_results:
            lines.append(f"Quiz: {quiz_results['score']}/{quiz_results['total']} ({quiz_results['percentage']}%)")

        if chat_history and isinstance(chat_history, dict):
            # Extract full conversation history
            full_history = chat_history.get("full_history", [])
            topic = chat_history.get("topic", "").title()

            if full_history:
                lines.append(f"CHAT - {topic}")
                lines.append("")

                # Format each Q&A turn (compact, no emojis)
                for i, turn in enumerate(full_history, 1):
                    question = turn.get("question", "")
                    # Use full answer if available, otherwise short answer
                    answer = turn.get("answer_full") or turn.get("answer_short", "")

                    # Compact format: Q1: question / A: answer
                    lines.append(f"Q{i}: {question}")
                    lines.append(f"A: {answer}")
                    lines.append("")  # Blank line between turns

        lines.append("Thanks for learning!")
        lines.append("Dial back anytime.")

        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)


# Singleton instance
sms_service = SMSService()


# Convenience function for fire-and-forget SMS
def send_sms_background(phone_number: str, message: str):
    """Queue SMS send without blocking USSD response."""
    asyncio.create_task(sms_service.send_sms(phone_number, message))
