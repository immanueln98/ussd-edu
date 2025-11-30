"""
Pre-stored educational content for demo.
This eliminates LLM dependency for Phase 1.

Structure:
- LESSONS: Topic-based lesson content for SMS delivery
- QUIZZES: Pre-generated quiz questions per topic
"""

# =============================================================================
# LESSON CONTENT (Delivered via SMS)
# =============================================================================

LESSONS = {
    "addition": {
        "title": "Addition (Grade 1-3)",
        "content": """ADDITION LESSON (Gr 1-3)

Addition = putting numbers together for a TOTAL. Use the + sign.

EXAMPLES:
2+3=5 (two plus three equals five)
4+1=5
7+2=9

TIPS:
- Count on fingers
- Draw dots to help
- Start with bigger number

PRACTICE:
1) 3+2=?  2) 5+4=?  3) 6+3=?
Answers: 5, 9, 9

Dial back for a quiz!"""
    },

    "subtraction": {
        "title": "Subtraction (Grade 1-3)",
        "content": """SUBTRACTION LESSON (Gr 1-3)

Subtraction = taking away to find what's LEFT. Use the - sign.

EXAMPLES:
5-2=3 (five minus two equals three)
8-3=5
9-4=5

TIPS:
- Start with big number
- Count backwards
- Think "how many left?"

PRACTICE:
1) 7-3=?  2) 9-5=?  3) 6-2=?
Answers: 4, 4, 4

Dial back for a quiz!"""
    },

    "multiplication": {
        "title": "Multiplication (Grade 2-4)",
        "content": """MULTIPLICATION LESSON (Gr 2-4)

Multiplication = REPEATED ADDITION. Use the x sign.

EXAMPLE: 3x4 means add 3 four times
3+3+3+3=12, so 3x4=12

MORE EXAMPLES:
2x5=10 (two groups of five)
4x3=12 (four groups of three)
5x2=10

TRICKS:
- x2 = double the number
- x5 = count by 5s
- x10 = add a zero

PRACTICE:
1) 2x4=?  2) 3x3=?  3) 5x3=?
Answers: 8, 9, 15

Dial back for a quiz!"""
    },

    "division": {
        "title": "Division (Grade 3-4)",
        "content": """DIVISION LESSON (Gr 3-4)

Division = SHARING EQUALLY. Use the / sign.

EXAMPLE: 12/3=4 means share 12 into 3 equal groups. Each group gets 4.

MORE EXAMPLES:
10/2=5
15/3=5
20/4=5

TIPS:
- Division is opposite of x
- If 3x4=12, then 12/3=4
- Share equally!

PRACTICE:
1) 8/2=?  2) 9/3=?  3) 12/4=?
Answers: 4, 3, 3

Dial back for a quiz!"""
    }
}


# =============================================================================
# QUIZ QUESTIONS (Served during USSD session)
# =============================================================================

QUIZZES = {
    "addition": [
        {"question": "What is 2 + 3?", "answer": "5"},
        {"question": "What is 4 + 5?", "answer": "9"},
        {"question": "What is 7 + 2?", "answer": "9"},
        {"question": "What is 3 + 6?", "answer": "9"},
        {"question": "What is 8 + 4?", "answer": "12"},
        {"question": "What is 5 + 5?", "answer": "10"},
        {"question": "What is 6 + 7?", "answer": "13"},
        {"question": "What is 9 + 3?", "answer": "12"},
        {"question": "What is 1 + 8?", "answer": "9"},
        {"question": "What is 4 + 4?", "answer": "8"},
    ],
    
    "subtraction": [
        {"question": "What is 5 - 2?", "answer": "3"},
        {"question": "What is 8 - 3?", "answer": "5"},
        {"question": "What is 9 - 4?", "answer": "5"},
        {"question": "What is 7 - 5?", "answer": "2"},
        {"question": "What is 10 - 6?", "answer": "4"},
        {"question": "What is 6 - 1?", "answer": "5"},
        {"question": "What is 12 - 5?", "answer": "7"},
        {"question": "What is 15 - 8?", "answer": "7"},
        {"question": "What is 9 - 9?", "answer": "0"},
        {"question": "What is 11 - 4?", "answer": "7"},
    ],
    
    "multiplication": [
        {"question": "What is 2 × 3?", "answer": "6"},
        {"question": "What is 4 × 2?", "answer": "8"},
        {"question": "What is 3 × 3?", "answer": "9"},
        {"question": "What is 5 × 2?", "answer": "10"},
        {"question": "What is 2 × 6?", "answer": "12"},
        {"question": "What is 4 × 4?", "answer": "16"},
        {"question": "What is 3 × 5?", "answer": "15"},
        {"question": "What is 2 × 7?", "answer": "14"},
        {"question": "What is 5 × 5?", "answer": "25"},
        {"question": "What is 3 × 4?", "answer": "12"},
    ],
    
    "division": [
        {"question": "What is 6 ÷ 2?", "answer": "3"},
        {"question": "What is 8 ÷ 4?", "answer": "2"},
        {"question": "What is 9 ÷ 3?", "answer": "3"},
        {"question": "What is 10 ÷ 2?", "answer": "5"},
        {"question": "What is 12 ÷ 3?", "answer": "4"},
        {"question": "What is 15 ÷ 5?", "answer": "3"},
        {"question": "What is 20 ÷ 4?", "answer": "5"},
        {"question": "What is 16 ÷ 2?", "answer": "8"},
        {"question": "What is 18 ÷ 3?", "answer": "6"},
        {"question": "What is 14 ÷ 2?", "answer": "7"},
    ]
}


# =============================================================================
# MENU STRUCTURE
# =============================================================================

TOPICS = {
    "1": {"name": "Addition", "key": "addition"},
    "2": {"name": "Subtraction", "key": "subtraction"},
    "3": {"name": "Multiplication", "key": "multiplication"},
    "4": {"name": "Division", "key": "division"},
}


def get_lesson(topic_key: str) -> dict:
    """Get lesson content by topic key."""
    return LESSONS.get(topic_key, {
        "title": "Not Found",
        "content": "Lesson not available. Please try another topic."
    })


def get_quiz_questions(topic_key: str, count: int = 5) -> list:
    """Get quiz questions for a topic."""
    import random
    questions = QUIZZES.get(topic_key, [])
    if len(questions) <= count:
        return questions.copy()
    return random.sample(questions, count)


def get_topic_name(topic_key: str) -> str:
    """Get human-readable topic name."""
    for _, topic in TOPICS.items():
        if topic["key"] == topic_key:
            return topic["name"]
    return "Unknown"
