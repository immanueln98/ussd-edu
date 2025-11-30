"""
Chat Service for Live AI Tutor

Orchestrates LLM chat interactions with timeout handling,
response truncation, and SMS fallback for USSD constraints.

Key Design:
1. 6-second hard timeout for USSD responsiveness
2. Smart truncation to 90 characters for USSD display
3. SMS fallback when LLM takes too long
4. Graceful degradation at multiple levels
"""

import asyncio
from typing import Optional, Tuple
from fastapi import BackgroundTasks
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm import llm_service
from app.services.sms import sms_service
from app.services.session import session_manager
from app.data.content import CHAT_FALLBACKS

settings = get_settings()


# =============================================================================
# DATA MODELS
# =============================================================================

class ChatResponse(BaseModel):
    """Result of processing a chat question."""
    success: bool                    # Did we get an answer?
    answer_short: str               # For USSD display (≤90 chars)
    answer_full: str                # For SMS/storage (complete answer)
    was_truncated: bool             # Was answer shortened?
    was_timeout: bool               # Did LLM timeout?
    sms_queued: bool                # Is SMS being sent in background?
    error: Optional[str] = None     # Error message if failed


# =============================================================================
# CHAT SERVICE CLASS
# =============================================================================

class ChatService:
    """
    Handles chat orchestration with LLM.

    Responsibilities:
    - Call LLM with timeout enforcement
    - Truncate responses for USSD
    - Queue SMS for timeout scenarios
    - Coordinate session state updates
    """

    async def process_question(
        self,
        question: str,
        topic: str,
        conversation_type: str,
        session_id: str,
        phone_number: str,
        background_tasks: BackgroundTasks
    ) -> ChatResponse:
        """
        Main entry point for processing a chat question.

        Args:
            question: User's question
            topic: Current topic (addition, subtraction, etc.)
            conversation_type: explain, example, solve, or free
            session_id: USSD session ID
            phone_number: User's phone number
            background_tasks: FastAPI background tasks

        Returns:
            ChatResponse with answer and metadata
        """

        # Get context window from session (last 3 turns)
        context = session_manager.get_chat_context(session_id)

        # Try to get LLM response with timeout
        try:
            # Call LLM with tight timeout
            if settings.use_llm_chat:
                response = await llm_service.generate_chat_response(
                    topic=topic,
                    question=question,
                    context=context,
                    conversation_type=conversation_type
                )
            else:
                response = None

            # If LLM succeeded, process the response
            if response:
                # Truncate if needed
                short, full, was_truncated = self._truncate_response(response)

                return ChatResponse(
                    success=True,
                    answer_short=short,
                    answer_full=full,
                    was_truncated=was_truncated,
                    was_timeout=False,
                    sms_queued=False
                )

            # If LLM failed but within timeout, use fallback message
            else:
                fallback = CHAT_FALLBACKS.get("error_generic", "Try asking again!")
                return ChatResponse(
                    success=False,
                    answer_short=fallback,
                    answer_full=fallback,
                    was_truncated=False,
                    was_timeout=False,
                    sms_queued=False,
                    error="LLM returned no response"
                )

        except asyncio.TimeoutError:
            # LLM took too long - acknowledge and queue SMS
            timeout_msg = CHAT_FALLBACKS.get("timeout_ack", "Thinking... SMS coming!")

            # Queue background task to continue waiting for LLM
            background_tasks.add_task(
                self._complete_and_send_sms,
                phone_number=phone_number,
                question=question,
                topic=topic,
                conversation_type=conversation_type,
                context=context
            )

            return ChatResponse(
                success=True,  # Session continues successfully
                answer_short=timeout_msg,
                answer_full=timeout_msg,
                was_truncated=False,
                was_timeout=True,
                sms_queued=True
            )

        except Exception as e:
            # Unexpected error - return fallback
            print(f"[Chat Service] Unexpected error: {type(e).__name__}: {str(e)}")
            fallback = CHAT_FALLBACKS.get("error_generic", "Try asking again!")

            return ChatResponse(
                success=False,
                answer_short=fallback,
                answer_full=fallback,
                was_truncated=False,
                was_timeout=False,
                sms_queued=False,
                error=str(e)
            )

    def _truncate_response(
        self,
        response: str,
        max_chars: int = None
    ) -> Tuple[str, str, bool]:
        """
        Truncate response for USSD while preserving full version.

        Uses smart truncation algorithm:
        1. Try to cut at sentence boundary (. ! ?)
        2. Try to cut at clause boundary (, ; :)
        3. Try to cut at word boundary (space)
        4. Hard cut with ellipsis (last resort)

        Args:
            response: Full LLM response
            max_chars: Maximum characters (default from settings)

        Returns:
            (short_version, full_version, was_truncated)
        """

        max_chars = max_chars or settings.chat_max_response_chars  # 90
        full = response.strip()

        # If it fits, return as-is
        if len(full) <= max_chars:
            return (full, full, False)

        # Try to find good truncation point
        search_zone = full[:max_chars]

        # Strategy 1: Find last sentence boundary
        for boundary in ['. ', '! ', '? ']:
            last_pos = search_zone.rfind(boundary)
            if last_pos > max_chars * 0.5:  # At least half the content
                short = full[:last_pos + 1].strip()
                return (short, full, True)

        # Strategy 2: Find last clause boundary
        for boundary in [', ', '; ', ': ']:
            last_pos = search_zone.rfind(boundary)
            if last_pos > max_chars * 0.5:
                short = full[:last_pos].strip() + "..."
                return (short, full, True)

        # Strategy 3: Find last word boundary
        last_space = search_zone.rfind(' ')
        if last_space > max_chars * 0.3:
            short = full[:last_space].strip() + "..."
            return (short, full, True)

        # Strategy 4: Hard truncate with ellipsis
        short = full[:max_chars - 3].strip() + "..."
        return (short, full, True)

    async def _complete_and_send_sms(
        self,
        phone_number: str,
        question: str,
        topic: str,
        conversation_type: str,
        context: list
    ) -> None:
        """
        Background task: Continue waiting for LLM, then send SMS.

        Called when USSD already returned (timeout acknowledgment).
        Now we can wait longer without blocking the user.

        Args:
            phone_number: User's phone
            question: Original question
            topic: Current topic
            conversation_type: Conversation type
            context: Context window
        """

        try:
            # Give LLM more time in background (30 seconds vs 6)
            async with asyncio.timeout(30):
                response = await llm_service.generate_chat_response(
                    topic=topic,
                    question=question,
                    context=context,
                    conversation_type=conversation_type
                )

            if response:
                # Send full answer via SMS
                await sms_service.send_chat_timeout_response(
                    phone_number=phone_number,
                    question=question,
                    answer=response
                )
                print(f"[Chat Service] Sent delayed answer via SMS to {phone_number}")
            else:
                # LLM still failed - send apology SMS
                message = f"""EduBot - Timeout Response

Sorry! I couldn't answer:
"{question[:50]}"

Please try again by dialing back.
Try simpler questions like:
"What is addition?"

Dial back anytime!"""

                await sms_service.send_sms(phone_number, message)
                print(f"[Chat Service] Sent timeout apology SMS to {phone_number}")

        except asyncio.TimeoutError:
            # Even background timeout - send apology
            message = f"""EduBot - Timeout

I'm taking too long to answer:
"{question[:50]}"

Please try again!

Dial back anytime!"""

            await sms_service.send_sms(phone_number, message)
            print(f"[Chat Service] Background timeout, sent apology to {phone_number}")

        except Exception as e:
            print(f"[Chat Service] Background SMS error: {type(e).__name__}: {str(e)}")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Create single instance
chat_service = ChatService()
