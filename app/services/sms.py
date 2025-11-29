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
    
    def _chunk_message(self, text: str, limit: int = 153) -> List[str]:
        """
        Split long messages into SMS-safe chunks.
        Uses 153 chars (not 160) to leave room for UDH concatenation.
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
        Format and send quiz results.
        
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
        
        # Build message
        lines = [
            f"📝 QUIZ RESULTS",
            f"",
            f"Topic: {topic}",
            f"Score: {score}/{total} ({pct}%)",
            ""
        ]
        
        # Add emoji based on score
        if pct >= 80:
            lines.append("⭐ Excellent work!")
        elif pct >= 60:
            lines.append("👍 Good job!")
        else:
            lines.append("📚 Keep practicing!")
        
        lines.append("")
        
        # Add each answer
        for i, ans in enumerate(results["answers"], 1):
            mark = "✓" if ans["is_correct"] else "✗"
            lines.append(f"Q{i}: {ans['question']}")
            lines.append(f"Your answer: {ans['user_answer']} {mark}")
            if not ans["is_correct"]:
                lines.append(f"Correct: {ans['correct_answer']}")
            lines.append("")
        
        lines.append("Dial back to learn more!")
        
        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)
    
    async def send_chat_history(
        self, 
        phone_number: str, 
        history: List[dict],
        topic: Optional[str] = None
    ) -> dict:
        """
        Send chat conversation history via SMS.
        
        history: [{question, answer, timestamp}, ...]
        """
        if not history:
            return {"status": "no_history"}
        
        lines = [
            "📚 CHAT HISTORY",
            f"Topic: {topic.title() if topic else 'Maths'}",
            ""
        ]
        
        for i, turn in enumerate(history, 1):
            # Truncate if needed
            q = turn["question"][:50]
            a = turn["answer"][:100]
            
            lines.append(f"Q{i}: {q}")
            lines.append(f"A{i}: {a}")
            lines.append("")
        
        lines.append("Dial back anytime!")
        
        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)
    
    async def send_session_summary(
        self, 
        phone_number: str,
        lesson_topic: Optional[str] = None,
        quiz_results: Optional[dict] = None,
        chat_history: Optional[List[dict]] = None
    ) -> dict:
        """
        Send complete session summary when user exits.
        Combines all activities into one SMS (or multiple if needed).
        """
        lines = ["📱 EDUBOT SESSION SUMMARY", ""]
        
        if lesson_topic:
            lines.append(f"📚 Lesson viewed: {lesson_topic.title()}")
            lines.append("")
        
        if quiz_results:
            lines.append(f"📝 Quiz: {quiz_results['score']}/{quiz_results['total']} ({quiz_results['percentage']}%)")
            lines.append("")
        
        if chat_history:
            lines.append(f"💬 Chat questions: {len(chat_history)}")
            for turn in chat_history[:3]:  # First 3 only in summary
                lines.append(f"  • {turn['question'][:30]}...")
            lines.append("")
        
        lines.append("Thanks for learning with EduBot!")
        lines.append("Dial back anytime to continue.")
        
        message = "\n".join(lines)
        return await self.send_sms(phone_number, message)


# Singleton instance
sms_service = SMSService()


# Convenience function for fire-and-forget SMS
def send_sms_background(phone_number: str, message: str):
    """Queue SMS send without blocking USSD response."""
    asyncio.create_task(sms_service.send_sms(phone_number, message))
