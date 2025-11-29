"""
EduBot USSD Application

A USSD-based educational chatbot for primary school maths
in Botswana. Uses Africa's Talking for USSD/SMS gateway.

To run:
    uvicorn app.main:app --reload --port 8000

For production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ussd
from app.config import get_settings

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="EduBot USSD API",
    description="USSD-based educational chatbot for primary school maths",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware (for development)
if settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(ussd.router, tags=["USSD"])


# =============================================================================
# HEALTH & INFO ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint - service info."""
    return {
        "service": "EduBot USSD API",
        "version": "1.0.0",
        "status": "running",
        "debug": settings.debug,
        "endpoints": {
            "ussd_callback": "/ussd/callback",
            "health": "/health",
            "docs": "/docs" if settings.debug else "disabled"
        }
    }


@app.post("/", response_class=PlainTextResponse)
async def root_post_redirect(
    background_tasks: BackgroundTasks,
    sessionId: str = Form(...),
    phoneNumber: str = Form(...),
    serviceCode: str = Form(...),
    text: str = Form("")
):
    """
    Fallback POST handler for root path.
    Some Africa's Talking configurations may send requests here.
    This redirects to the actual USSD callback handler.
    """
    from app.routers.ussd import ussd_callback
    return await ussd_callback(background_tasks, sessionId, phoneNumber, serviceCode, text)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/test-sms/{phone}")
async def test_sms(phone: str):
    """
    Test SMS endpoint (debug mode only).
    Example: /test-sms/+26771234567
    """
    if not settings.debug:
        return {"error": "Only available in debug mode"}
    
    from app.services.sms import sms_service
    
    result = await sms_service.send_sms(
        phone,
        "Test message from EduBot! 📚"
    )
    return result


# =============================================================================
# USSD SIMULATOR ENDPOINT (FOR LOCAL TESTING)
# =============================================================================

@app.get("/simulate")
async def simulate_info():
    """Info about the USSD simulator."""
    return {
        "info": "Use POST /ussd/callback to simulate USSD",
        "example": {
            "sessionId": "test-session-123",
            "phoneNumber": "+26771234567",
            "serviceCode": "*384*123#",
            "text": ""
        },
        "text_examples": {
            "main_menu": "",
            "select_learn": "1",
            "select_addition": "1*1",
            "select_quiz": "2",
            "quiz_addition": "2*1",
            "quiz_5_questions": "2*1*5",
            "answer_7": "2*1*5*7"
        }
    }


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup():
    """Run on application startup."""
    print("=" * 50)
    print("EduBot USSD API Starting...")
    print(f"Debug mode: {settings.debug}")
    print(f"Redis: {settings.redis_host}:{settings.redis_port}")
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown():
    """Run on application shutdown."""
    print("EduBot USSD API Shutting down...")
