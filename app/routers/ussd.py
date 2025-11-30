"""
USSD Callback Router - The Heart of the Application

This module implements the USSD state machine that handles:
1. Menu navigation
2. Lesson selection
3. Quiz interaction
4. (Future) Live chat

Africa's Talking sends POST requests with:
- sessionId: Unique session ID
- phoneNumber: User's phone number
- serviceCode: USSD code dialed
- text: Cumulative user input separated by '*'

Responses must start with:
- "CON " to continue the session (show menu)
- "END " to terminate the session
"""

from fastapi import APIRouter, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse
from app.services.session import session_manager
from app.services.sms import sms_service
from app.services.quiz import quiz_service
from app.data.content import (
    TOPICS,
    get_lesson,
    get_quiz_questions,
    get_topic_name
)

router = APIRouter()


# =============================================================================
# MAIN CALLBACK ENDPOINT
# =============================================================================

@router.post("/ussd/callback", response_class=PlainTextResponse)
async def ussd_callback(
    background_tasks: BackgroundTasks,
    sessionId: str = Form(...),
    phoneNumber: str = Form(...),
    serviceCode: str = Form(...),
    text: str = Form("")
):
    """
    Main USSD callback handler.
    
    The 'text' parameter contains cumulative user input.
    Example progression:
        Initial dial: text = ""
        Select 1: text = "1"
        Then select 2: text = "1*2"
        Then type "5": text = "1*2*5"
    """
    
    # Get or create session
    session = session_manager.get_session(sessionId)
    if not session:
        session = session_manager.create_session(sessionId, phoneNumber)
    
    # Parse the navigation path
    user_input = text.split('*') if text else []
    
    # Route to appropriate handler based on current menu state
    response = await route_request(
        session=session,
        session_id=sessionId,
        phone_number=phoneNumber,
        user_input=user_input,
        background_tasks=background_tasks
    )

    return response


async def route_request(
    session: dict,
    session_id: str,
    phone_number: str,
    user_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """
    Route to the appropriate handler based on navigation depth.
    """

    # Empty input = main menu
    if not user_input or user_input == ['']:
        return main_menu()

    # First level selection
    first_choice = user_input[0]

    if first_choice == '1':
        # LEARN PATH
        return handle_learn_path(
            session, session_id, phone_number,
            user_input[1:], background_tasks
        )

    elif first_choice == '2':
        # QUIZ PATH
        return await handle_quiz_path(
            session, session_id, phone_number,
            user_input[1:], background_tasks
        )

    elif first_choice == '3':
        # CHAT PATH (Phase 3)
        return await handle_chat_path(
            session, session_id, phone_number,
            user_input[1:], background_tasks
        )

    elif first_choice == '4':
        # EXIT
        return handle_exit(session, session_id, phone_number, background_tasks)

    else:
        return invalid_choice_main()


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu() -> str:
    """Display main menu."""
    return (
        "CON Welcome to EduBot!\n"
        "Primary School Maths\n\n"
        "1. Learn a Topic\n"
        "2. Take a Quiz\n"
        "3. Chat with AI Tutor\n"
        "4. Exit"
    )


def invalid_choice_main() -> str:
    """Invalid main menu choice."""
    return (
        "CON Invalid choice.\n\n"
        "1. Learn a Topic\n"
        "2. Take a Quiz\n"
        "3. Chat with AI Tutor\n"
        "4. Exit"
    )


# =============================================================================
# LEARN PATH
# =============================================================================

def handle_learn_path(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """
    Handle the Learn/Lesson path.
    
    Flow:
    1 → Show topics
    1*1 → Select topic, send SMS
    """
    
    # Show topic selection
    if not sub_input or sub_input == ['']:
        return topic_menu("lesson")
    
    topic_choice = sub_input[0]
    
    # Handle back option
    if topic_choice == '0':
        return main_menu()
    
    # Valid topic?
    if topic_choice not in TOPICS:
        return (
            "CON Invalid topic.\n\n"
            "1. Addition\n"
            "2. Subtraction\n"
            "3. Multiplication\n"
            "4. Division\n"
            "0. Back"
        )
    
    # Get lesson and send via SMS
    topic_key = TOPICS[topic_choice]["key"]
    topic_name = TOPICS[topic_choice]["name"]
    lesson = get_lesson(topic_key)
    
    # Update session
    session_manager.update_session(session_id, topic=topic_key)
    
    # Queue SMS delivery (non-blocking)
    background_tasks.add_task(
        sms_service.send_lesson,
        phone_number,
        lesson
    )
    
    return (
        f"END 📚 {topic_name} Lesson\n\n"
        f"Your lesson is being sent\n"
        f"via SMS right now!\n\n"
        f"Check your messages.\n"
        f"Dial back for a quiz!"
    )


# =============================================================================
# QUIZ PATH
# =============================================================================

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

        # Show first question
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


def show_question(session_id: str) -> str:
    """Display current quiz question."""
    q_data = session_manager.get_current_question(session_id)
    
    if not q_data:
        return "END Quiz error. Please try again."
    
    q = q_data["question"]
    num = q_data["number"]
    total = q_data["total"]
    
    return (
        f"CON Q{num} of {total}\n\n"
        f"{q['question']}\n\n"
        f"Enter your answer:"
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
    
    # Build feedback message
    if result["correct"]:
        feedback = "✓ Correct!"
    else:
        feedback = f"✗ Wrong. Answer: {result['correct_answer']}"
    
    # Check if quiz is complete
    if result["is_complete"]:
        # Quiz done - send results via SMS
        quiz_results = session_manager.get_quiz_results(session_id)
        
        background_tasks.add_task(
            sms_service.send_quiz_results,
            phone_number,
            quiz_results
        )
        
        score = result["score"]
        total = result["total"]
        pct = round((score / total) * 100)
        
        # Emoji based on performance
        if pct >= 80:
            emoji = "⭐"
        elif pct >= 60:
            emoji = "👍"
        else:
            emoji = "📚"
        
        return (
            f"END {feedback}\n\n"
            f"Quiz Complete! {emoji}\n"
            f"Score: {score}/{total} ({pct}%)\n\n"
            f"Full results sent via SMS!"
        )
    
    # More questions remain - show next
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


# =============================================================================
# EXIT HANDLER
# =============================================================================

def handle_exit(
    session: dict,
    session_id: str,
    phone_number: str,
    background_tasks: BackgroundTasks
) -> str:
    """Handle session exit - send summary if applicable."""
    
    # Gather session data
    quiz_results = session_manager.get_quiz_results(session_id)
    chat_history = session_manager.get_chat_history(session_id)
    lesson_topic = session.get("topic")
    
    # Send summary if there's anything to send
    if quiz_results or chat_history or lesson_topic:
        background_tasks.add_task(
            sms_service.send_session_summary,
            phone_number,
            lesson_topic,
            quiz_results,
            chat_history
        )
        
        return (
            "END Thanks for using EduBot!\n\n"
            "Session summary sent\n"
            "to your phone via SMS.\n\n"
            "Dial back anytime! 📚"
        )
    
    return (
        "END Thanks for using EduBot!\n\n"
        "Dial back anytime\n"
        "to learn more! 📚"
    )


# =============================================================================
# CHAT PATH (Phase 3)
# =============================================================================

async def handle_chat_path(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """
    Handle the Chat with AI Tutor path.

    Flow:
    3 → Show topics
    3*1 → Select topic, show conversation types
    3*1*4 → Select type (free chat), prompt for question
    3*1*4*question → Process with LLM, show answer
    3*1*4*q*1 → Ask another question
    3*1*4*q*2 → Change topic
    3*1*4*q*0 → Exit chat (send SMS summary)
    """

    # Check if chat is already active
    chat_state = session.get("chat_state")

    if chat_state and chat_state.get("active"):
        # Chat already started - handle ongoing conversation
        return await handle_chat_active(
            session, session_id, phone_number,
            sub_input, background_tasks
        )

    # Step 1: Show topic selection
    if not sub_input or sub_input == ['']:
        return chat_topic_menu()

    topic_choice = sub_input[0]

    # Handle back
    if topic_choice == '0':
        return main_menu()

    # Invalid topic
    if topic_choice not in TOPICS:
        return chat_topic_menu()

    topic_key = TOPICS[topic_choice]["key"]
    topic_name = TOPICS[topic_choice]["name"]

    # Step 2: Show conversation type selection
    if len(sub_input) == 1:
        return chat_type_menu(topic_name)

    # Step 3: Start chat with selected type
    if len(sub_input) == 2:
        type_choice = sub_input[1]

        # Map choice to conversation type
        type_map = {
            "1": "explain",
            "2": "example",
            "3": "solve",
            "4": "free"
        }

        # Handle back
        if type_choice == '0':
            return chat_topic_menu()

        # Invalid type
        if type_choice not in type_map:
            return chat_type_menu(topic_name)

        conversation_type = type_map[type_choice]

        # Initialize chat session
        session_manager.start_chat(session_id, topic_key)
        session_manager.set_conversation_type(session_id, conversation_type)

        # Show question prompt
        return chat_question_prompt(topic_name, conversation_type)

    # Step 4+: Process question
    question = sub_input[-1]

    # Refresh session to get updated chat_state
    session = session_manager.get_session(session_id)

    return await process_chat_question(
        session, session_id, phone_number,
        question, background_tasks
    )


async def handle_chat_active(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """Handle input when chat is already active."""

    # Refresh session to get latest chat_state
    session = session_manager.get_session(session_id) or session
    chat_state = session.get("chat_state", {})

    # No input = show prompt again
    if not sub_input or sub_input == ['']:
        topic_key = chat_state.get("topic", "addition")
        topic_name = get_topic_name(topic_key)
        conv_type = chat_state.get("conversation_type", "free")
        return chat_question_prompt(topic_name, conv_type)

    # Get last input (could be question or menu action)
    last_input = sub_input[-1]

    # Check if it's a menu action (1=another, 2=change topic, 0=exit)
    if last_input in ['0', '1', '2']:
        return await handle_chat_menu_action(
            session, session_id, phone_number,
            last_input, background_tasks
        )

    # Otherwise it's a question
    return await process_chat_question(
        session, session_id, phone_number,
        last_input, background_tasks
    )


async def process_chat_question(
    session: dict,
    session_id: str,
    phone_number: str,
    question: str,
    background_tasks: BackgroundTasks
) -> str:
    """
    Process a chat question with LLM and display answer.
    """
    from app.services.chat import chat_service

    # Refresh session to get latest chat_state
    session = session_manager.get_session(session_id) or session
    chat_state = session.get("chat_state") or {}
    topic_key = chat_state.get("topic", "addition")
    topic_name = get_topic_name(topic_key)
    conversation_type = chat_state.get("conversation_type", "free")

    # Validate question (not empty, not too short)
    if not question or len(question.strip()) < 2:
        from app.data.content import CHAT_FALLBACKS
        fallback = CHAT_FALLBACKS.get("empty", "Type a maths question and I'll help!")
        return f"CON {fallback}\n\nTry again:"

    # Call chat service to get LLM response
    response = await chat_service.process_question(
        question=question,
        topic=topic_key,
        conversation_type=conversation_type,
        session_id=session_id,
        phone_number=phone_number,
        background_tasks=background_tasks
    )

    # Update session with the Q&A turn
    session_manager.add_chat_turn(
        session_id=session_id,
        question=question,
        answer_short=response.answer_short,
        answer_full=response.answer_full,
        was_truncated=response.was_truncated,
        was_timeout=response.was_timeout
    )

    # Build response message
    answer_display = response.answer_short

    # Add indicators if needed
    indicators = []
    if response.was_truncated:
        indicators.append("Full answer via SMS")
    if response.sms_queued:
        indicators.append("Check SMS shortly")

    indicator_text = f"\n({', '.join(indicators)})" if indicators else ""

    # Show answer with menu options
    return (
        f"CON {answer_display}{indicator_text}\n\n"
        f"1. Ask another\n"
        f"2. Change topic\n"
        f"0. Exit chat"
    )


async def handle_chat_menu_action(
    session: dict,
    session_id: str,
    phone_number: str,
    action: str,
    background_tasks: BackgroundTasks
) -> str:
    """Handle menu actions during chat (1=another, 2=change topic, 0=exit)."""

    # Refresh session to get latest chat_state
    session = session_manager.get_session(session_id) or session
    chat_state = session.get("chat_state", {})
    topic_key = chat_state.get("topic", "addition")
    topic_name = get_topic_name(topic_key)
    conversation_type = chat_state.get("conversation_type", "free")

    if action == '1':
        # Ask another question (same topic/type)
        return chat_question_prompt(topic_name, conversation_type)

    elif action == '2':
        # Change topic - reset chat state and show topic menu
        # This requires deactivating the chat to allow topic reselection
        session["chat_state"] = {
            "active": False,
            "topic": None,
            "conversation_type": None,
            "context_window": [],
            "full_history": chat_state.get("full_history", []),
            "turn_count": 0,
            "timeout_count": 0,
            "started_at": chat_state.get("started_at", "")
        }
        session_manager.save_session(session_id, session)
        return chat_topic_menu()

    elif action == '0':
        # Exit chat - send SMS summary
        return await handle_chat_exit(
            session, session_id, phone_number, background_tasks
        )

    else:
        # Invalid action - show prompt again
        return chat_question_prompt(topic_name, conversation_type)


async def handle_chat_exit(
    session: dict,
    session_id: str,
    phone_number: str,
    background_tasks: BackgroundTasks
) -> str:
    """
    Handle chat exit - send SMS with full conversation history.
    """

    # Refresh session to get latest state
    session = session_manager.get_session(session_id) or session

    # Get chat summary
    chat_summary = session_manager.get_chat_summary(session_id)

    if chat_summary and chat_summary.get("turn_count", 0) > 0:
        # Queue SMS with full chat history
        background_tasks.add_task(
            sms_service.send_session_summary,
            phone_number,
            lesson_topic=None,
            quiz_results=None,
            chat_history=chat_summary
        )

        turns = chat_summary["turn_count"]
        topic = get_topic_name(session.get("chat_state", {}).get("topic", ""))

        return (
            "END Chat ended!\n\n"
            f"{turns} Q&A on {topic}\n"
            "Full conversation sent\n"
            "via SMS.\n\n"
            "Dial back anytime!"
        )

    return (
        "END Chat ended!\n\n"
        "Dial back anytime\n"
        "to continue learning!"
    )


# =============================================================================
# CHAT HELPER FUNCTIONS
# =============================================================================

def chat_topic_menu() -> str:
    """Display topic selection for chat."""
    return (
        "CON Select topic to chat about:\n\n"
        "1. Addition\n"
        "2. Subtraction\n"
        "3. Multiplication\n"
        "4. Division\n"
        "0. Back"
    )


def chat_type_menu(topic_name: str) -> str:
    """Display conversation type selection."""
    return (
        f"CON {topic_name} Chat\n\n"
        "How can I help?\n\n"
        "1. Explain concept\n"
        "2. Show example\n"
        "3. Solve problem\n"
        "4. Free chat\n"
        "0. Back"
    )


def chat_question_prompt(topic_name: str, conversation_type: str) -> str:
    """Display question prompt based on conversation type."""

    # Map conversation types to prompts
    prompts = {
        "explain": f"What about {topic_name}\nshould I explain?\n\nType your question:",
        "example": f"What {topic_name} example\ndo you need?\n\nType your request:",
        "solve": f"Type the {topic_name}\nproblem to solve:",
        "free": f"Ask me anything about\n{topic_name}:"
    }

    prompt = prompts.get(conversation_type, prompts["free"])

    return f"CON {prompt}"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def topic_menu(context: str = "lesson") -> str:
    """Display topic selection menu."""
    action = "learn" if context == "lesson" else "quiz on"
    return (
        f"CON Select topic to {action}:\n\n"
        "1. Addition\n"
        "2. Subtraction\n"
        "3. Multiplication\n"
        "4. Division\n"
        "0. Back"
    )
