# EduBot USSD Demo

A USSD-based educational chatbot for primary school maths in Botswana.

## Features (Demo)

- **Learn Mode**: Browse maths topics, receive lesson content via SMS
- **Quiz Mode**: Interactive quiz via USSD, results sent via SMS
- **Session Summary**: Complete activity summary sent via SMS on exit

## Architecture

```
USSD Session (Interactive)          SMS (Final Delivery)
─────────────────────────           ───────────────────
*384*123#                           
    │                               
    ├── 1. Learn a Topic            
    │   └── Select topic ──────────► Lesson content SMS
    │                               
    ├── 2. Take a Quiz              
    │   ├── Select topic            
    │   ├── Choose count            
    │   └── Answer Qs ─────────────► Quiz results SMS
    │                               
    └── 3. Exit ───────────────────► Session summary SMS
```

## Quick Start

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# Redis (for session storage)
redis-server --version

# ngrok (for exposing local server)
ngrok --version
```

### 2. Setup

```bash
# Clone/navigate to project
cd ussd-edu-demo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your Africa's Talking credentials
```

### 3. Run Locally

**Terminal 1: Start Redis**
```bash
redis-server
```

**Terminal 2: Start API**
```bash
cd ussd-edu-demo
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 3: Expose with ngrok**
```bash
ngrok http 8000
```

### 4. Africa's Talking Setup

1. Go to [Africa's Talking](https://account.africastalking.com)
2. Create account / Login
3. Go to **Sandbox** mode
4. **USSD** → Create Channel
   - Service Code: `*384*123#` (or any available)
   - Callback URL: `https://YOUR-NGROK-URL/ussd/callback`
5. **Settings** → API Key → Generate/Copy
6. Update `.env` with your API key

### 5. Test in Simulator

1. In Africa's Talking dashboard, click **Launch Simulator**
2. Enter a phone number (e.g., `+254711XXXYYY`)
3. Dial your USSD code
4. Navigate through menus!

## Local Testing (Without Africa's Talking)

You can test the USSD logic locally using curl:

```bash
# Main menu
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text="

# Select "Learn" (option 1)
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*123#" \
  -d "text=1"

# Select "Addition" (option 1)
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*123#" \
  -d "text=1*1"
```

### Quiz Flow

```bash
# Start quiz
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2"

# Select Addition
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2*1"

# Choose 5 questions
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2*1*5"

# Answer first question (e.g., "5")
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2*1*5*5"

# Continue answering...
```

## Project Structure

```
ussd-edu-demo/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── routers/
│   │   └── ussd.py          # USSD callback handler
│   ├── services/
│   │   ├── session.py       # Redis session management
│   │   └── sms.py           # Africa's Talking SMS
│   └── data/
│       └── content.py       # Pre-stored lessons & quizzes
├── requirements.txt
├── .env.example
└── README.md
```

## Menu Flow

```
*384*123#
│
├── [1] Learn a Topic
│   ├── [1] Addition      → SMS: Lesson content
│   ├── [2] Subtraction   → SMS: Lesson content
│   ├── [3] Multiplication→ SMS: Lesson content
│   ├── [4] Division      → SMS: Lesson content
│   └── [0] Back
│
├── [2] Take a Quiz
│   ├── Select topic (1-4)
│   ├── Enter count (3, 5, or 10)
│   ├── Answer questions...
│   └── Complete → SMS: Quiz results
│
└── [3] Exit → SMS: Session summary
```

## Phase 2: LLM Integration

After the demo works, add these features:

1. **LLM Quiz Generation** - Generate questions on-the-fly
2. **Live Chat** - Real-time Q&A via USSD (requires Groq for speed)
3. **Personalized Content** - Adapt to student level

See `docs/phase2-llm.md` (coming soon) for details.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/ussd/callback` | POST | Africa's Talking USSD webhook |
| `/test-sms/{phone}` | GET | Test SMS (debug only) |
| `/simulate` | GET | USSD simulation examples |
| `/docs` | GET | Swagger docs (debug only) |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AT_USERNAME` | Africa's Talking username | `sandbox` |
| `AT_API_KEY` | Africa's Talking API key | - |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `DEBUG` | Enable debug mode | `true` |

## Troubleshooting

### "Connection refused" to Redis
```bash
# Start Redis
redis-server
```

### USSD timeout
- Response must be <15 seconds (Vodacom)
- Check ngrok logs for slow responses
- Ensure Redis is running locally

### SMS not received
- Check Africa's Talking sandbox logs
- Verify API key in `.env`
- Use test phone number format: `+254711XXXXXX`

### Session not persisting
- Verify Redis is running
- Check session timeout (default 5 min)
- Use same `sessionId` for subsequent requests

## License

MIT License - See LICENSE file
