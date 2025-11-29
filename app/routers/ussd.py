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
    response = route_request(
        session=session,
        session_id=sessionId,
        phone_number=phoneNumber,
        user_input=user_input,
        background_tasks=background_tasks
    )
    
    return response


def route_request(
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
        return handle_quiz_path(
            session, session_id, phone_number,
            user_input[1:], background_tasks
        )
    
    elif first_choice == '3':
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
        "CON 📚 Welcome to EduBot!\n"
        "Primary School Maths\n\n"
        "1. Learn a Topic\n"
        "2. Take a Quiz\n"
        "3. Exit"
    )


def invalid_choice_main() -> str:
    """Invalid main menu choice."""
    return (
        "CON Invalid choice.\n\n"
        "1. Learn a Topic\n"
        "2. Take a Quiz\n"
        "3. Exit"
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

def handle_quiz_path(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """
    Handle the Quiz path.
    
    Flow:
    2 → Show topics
    2*1 → Select topic, ask question count
    2*1*5 → Start quiz with 5 questions
    2*1*5*7 → Answer first question with "7"
    ... continue until complete
    """
    
    # Check if quiz is already in progress
    if session.get("quiz_state"):
        return handle_quiz_in_progress(
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
    
    # Step 3: Start quiz with specified count
    if len(sub_input) == 2:
        try:
            count = int(sub_input[1])
            if count not in [3, 5, 10]:
                count = 5  # Default
        except ValueError:
            count = 5
        
        # Get questions and start quiz
        questions = get_quiz_questions(topic_key, count)
        session = session_manager.start_quiz(session_id, topic_key, questions)
        
        # Show first question
        return show_question(session_id)
    
    # Step 4+: Process answer
    return process_quiz_answer(
        session, session_id, phone_number,
        sub_input[-1], background_tasks
    )


def handle_quiz_in_progress(
    session: dict,
    session_id: str,
    phone_number: str,
    sub_input: list,
    background_tasks: BackgroundTasks
) -> str:
    """Handle input when quiz is already active."""
    
    if not sub_input or sub_input == ['']:
        return show_question(session_id)
    
    # Latest input is the answer
    answer = sub_input[-1]
    
    return process_quiz_answer(
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


def process_quiz_answer(
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
