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
