# 📚 EduBot - USSD Educational Platform

> An AI-powered USSD-based educational chatbot for primary school mathematics in Botswana, delivering lessons and quizzes via SMS with cost-optimized delivery.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 🌟 Features

### ✅ Phase 1: Core USSD Experience (Complete)
- **📖 Learn Mode**: Browse math topics (Addition, Subtraction, Multiplication, Division)
- **✏️ Quiz Mode**: Interactive quizzes via USSD with instant feedback
- **📱 SMS Delivery**: Lessons and quiz results sent via optimized SMS
- **💾 Session Management**: Redis-based state persistence for seamless conversations
- **🔄 Session Summary**: Complete activity summary on exit

### ✅ Phase 2: LLM Integration (Complete)
- **🤖 AI Quiz Generation**: Dynamic quiz questions using Groq's Llama 3.1 8B model
- **⚡ Fast Inference**: <5 second quiz generation (within USSD 15s timeout)
- **🛡️ Graceful Fallback**: Automatic switch to pre-stored questions if LLM fails
- **📊 Dual Source Tracking**: Monitors whether questions are LLM-generated or static

### 💰 SMS Cost Optimization
- **📉 60-70% Cost Reduction**: Optimized formatting reduces SMS count dramatically
- **🔤 GSM-7 Encoding**: No emojis = 160 chars/SMS instead of 70 chars/SMS (Unicode)
- **🎯 Smart Results**: Shows only incorrect answers to minimize message length
- **📦 Compact Lessons**: Condensed content maintains educational value in fewer SMS

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   USSD      │      │   FastAPI   │      │   Africa's  │
│  *384*...#  │─────▶│   Backend   │─────▶│   Talking   │
└─────────────┘      └─────────────┘      │   SMS API   │
                            │              └─────────────┘
                            │
                     ┌──────┴──────┐
                     │             │
              ┌──────▼─────┐ ┌────▼─────┐
              │   Redis    │ │   Groq   │
              │  Sessions  │ │  LLM API │
              └────────────┘ └──────────┘
```

### USSD Flow Diagram
```
*384*20251129#
    │
    ├─── [1] Learn a Topic
    │       ├─ [1] Addition ──────────────► SMS: Lesson (2 SMS)
    │       ├─ [2] Subtraction ───────────► SMS: Lesson (2 SMS)
    │       ├─ [3] Multiplication ────────► SMS: Lesson (2 SMS)
    │       ├─ [4] Division ──────────────► SMS: Lesson (2 SMS)
    │       └─ [0] Back to Main Menu
    │
    ├─── [2] Take a Quiz
    │       ├─ Select topic (1-4)
    │       ├─ Choose count (3, 5, 10)
    │       ├─ Answer Q1, Q2, Q3...
    │       └─ Complete ──────────────────► SMS: Results (1-2 SMS)
    │
    └─── [3] Exit ────────────────────────► SMS: Session Summary (1 SMS)
```

## 🚀 Quick Start

### Prerequisites

Ensure you have the following installed:

```bash
# Python 3.11+ (3.13 recommended)
python --version  # Should be 3.11.0 or higher

# Redis (session storage)
redis-server --version  # Install via: brew install redis (Mac)

# ngrok (local tunnel for USSD callbacks)
ngrok version  # Install via: brew install ngrok (Mac)
```

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/immanueln98/ussd-edu.git
cd ussd-edu
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# or: venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

Required `.env` configuration:
```env
# Africa's Talking Credentials
AT_USERNAME=sandbox
AT_API_KEY=your_api_key_here

# Groq API (for LLM quiz generation)
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.1-8b-instant

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# App Settings
DEBUG=true
USE_LLM_QUIZ=true

# USSD Service Code
USSD_SERVICE_CODE=*384*20251129#
```

### Running the Application

You need **3 terminal windows** running simultaneously:

**Terminal 1: Start Redis**
```bash
redis-server
```

**Terminal 2: Start FastAPI Backend**
```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 3: Expose with ngrok**
```bash
ngrok http 8000
```

Copy the ngrok HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Africa's Talking Setup

1. Sign up at [Africa's Talking](https://account.africastalking.com)
2. Go to **Sandbox** mode
3. Navigate to **USSD** → **Create Channel**
   - Service Code: `*384*20251129#` (or any available code)
   - Callback URL: `https://YOUR-NGROK-URL/ussd/callback`
4. Go to **Settings** → **API Key** → Generate/Copy
5. Update `.env` with your `AT_API_KEY`

### Get Groq API Key (for LLM features)

1. Sign up at [Groq Console](https://console.groq.com)
2. Navigate to **API Keys** → **Create API Key**
3. Copy the key and add to `.env` as `GROQ_API_KEY`

### Testing in Simulator

1. In Africa's Talking dashboard, click **Launch Simulator**
2. Enter a phone number (format: `+267XXXXXXXX` for Botswana)
3. Dial your USSD code (e.g., `*384*20251129#`)
4. Navigate through menus and complete a quiz!

## 🧪 Local Testing (Without Simulator)

Test the USSD logic locally using curl:

### Main Menu
```bash
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text="
```

### Learn Mode Flow
```bash
# Select "Learn" (option 1)
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=1"

# Select "Addition" (option 1)
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=test-123" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=1*1"
```

### Quiz Mode Flow
```bash
# Start quiz (option 2)
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2"

# Select Addition (option 1)
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

# Answer first question (e.g., "7")
curl -X POST http://localhost:8000/ussd/callback \
  -d "sessionId=quiz-456" \
  -d "phoneNumber=+26771234567" \
  -d "serviceCode=*384*20251129#" \
  -d "text=2*1*5*7"
```

## 📁 Project Structure

```
ussd-edu-demo/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application & endpoints
│   ├── config.py               # Pydantic settings (env vars)
│   │
│   ├── routers/
│   │   └── ussd.py             # USSD callback handler & menu logic
│   │
│   ├── services/
│   │   ├── session.py          # Redis session management
│   │   ├── sms.py              # Africa's Talking SMS (optimized)
│   │   ├── llm.py              # Groq LLM integration (quiz gen)
│   │   └── quiz.py             # Quiz service (LLM + fallback)
│   │
│   └── data/
│       └── content.py          # Pre-stored lessons & quiz bank
│
├── test_llm.py                 # LLM service testing script
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and status |
| `/` | POST | USSD callback fallback (Africa's Talking) |
| `/health` | GET | Health check |
| `/health/llm` | GET | LLM service health & latency |
| `/ussd/callback` | POST | Main USSD webhook (Africa's Talking) |
| `/test-sms/{phone}` | GET | Test SMS delivery (debug mode) |
| `/simulate` | GET | USSD simulation examples |
| `/docs` | GET | Interactive API docs (debug mode) |

### Example: Test LLM Health
```bash
curl http://localhost:8000/health/llm
```

Response:
```json
{
  "status": "healthy",
  "healthy": true,
  "response_time_ms": 1847,
  "model": "llama-3.1-8b-instant"
}
```

## ⚙️ Configuration

All settings are managed via `.env` file using Pydantic Settings:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AT_USERNAME` | Africa's Talking username | `sandbox` | ✅ |
| `AT_API_KEY` | Africa's Talking API key | - | ✅ |
| `GROQ_API_KEY` | Groq API key (LLM) | - | ⚠️ Optional* |
| `LLM_MODEL` | Groq model name | `llama-3.1-8b-instant` | No |
| `LLM_TIMEOUT` | LLM timeout (seconds) | `10` | No |
| `LLM_MAX_TOKENS` | Max tokens per LLM response | `500` | No |
| `REDIS_HOST` | Redis server host | `localhost` | ✅ |
| `REDIS_PORT` | Redis server port | `6379` | ✅ |
| `REDIS_DB` | Redis database number | `0` | No |
| `DEBUG` | Enable debug mode | `true` | No |
| `SESSION_TIMEOUT` | Session timeout (seconds) | `300` | No |
| `USE_LLM_QUIZ` | Enable LLM quiz generation | `true` | No |
| `USSD_SERVICE_CODE` | USSD service code | `*384*123#` | No |

*If `GROQ_API_KEY` is not set, quizzes will use pre-stored questions (static fallback).

## 🧠 LLM Integration Details

### Quiz Generation Flow

1. **User selects quiz** → Topic + Question count
2. **LLM Service called** → Groq API with structured prompt
3. **Response parsing** → JSON validation with Pydantic
4. **Fallback handling** → If LLM fails, use static questions
5. **Session tracking** → Stores quiz source (LLM vs static)

### Prompt Engineering

The system uses carefully crafted prompts with:
- **Clear role definition**: "You are a primary school maths teacher"
- **Explicit output format**: JSON schema with examples
- **Topic-specific guidance**: Number ranges, difficulty constraints
- **Strict instructions**: "Output ONLY valid JSON"

Example prompt snippet:
```python
"""Generate exactly 5 addition questions for primary school students.

RULES:
- Use numbers between 1-20. Answers should be under 30.
- Answers must be single numbers (no fractions)
- Questions should be clear and simple

OUTPUT FORMAT:
{"questions": [{"question": "What is 2 + 3?", "answer": "5"}]}
"""
```

### Performance Metrics

- **Typical LLM response time**: 2-4 seconds
- **Total quiz generation**: <5 seconds
- **USSD timeout budget**: 15 seconds (safe margin)
- **Fallback activation time**: <100ms

## 💰 SMS Cost Optimization Strategy

### Before Optimization (Quiz Results Example)
```
📝 QUIZ RESULTS

Topic: Addition
Score: 3/5 (60%)

👍 Good job!

Q1: What is 3 + 4?
Your answer: 7 ✓

Q2: What is 5 + 8?
Your answer: 10 ✗
Correct: 13
...
```
**Cost**: ~4-5 SMS (Unicode encoding due to emojis: 70 chars/SMS)

### After Optimization
```
QUIZ RESULTS - Addition
Score: 3/5 (60%)
Good job!

Review these:
Q2: 5+8=?
You:10 Ans:13
Q4: 9+6=?
You:14 Ans:15

Dial back to practice more!
```
**Cost**: ~1-2 SMS (GSM-7 encoding: 160 chars/SMS)

### Optimization Techniques
1. **Remove emojis** → Force GSM-7 encoding (160 vs 70 chars)
2. **Show only wrong answers** → Reduce content by 60-80%
3. **Compact operators** → `3+4=7` instead of `3 + 4 = 7`
4. **Minimize whitespace** → Fewer blank lines
5. **Condensed practice questions** → All on one line

**Result**: 60-70% reduction in SMS costs while maintaining clarity!

## 🔍 Testing LLM Features

Run the included test script to verify LLM integration:

```bash
python test_llm.py
```

Expected output:
```
==================================================
Testing LLM Service
==================================================

1. Health Check:
   Status: healthy
   Response time: 1847ms

2. Generate Addition Quiz (5 questions):
   Time: 3.21s
   ✓ Generated 5 questions:
      Q1: What is 2 + 3? = 5
      Q2: What is 7 + 4? = 11
      Q3: What is 5 + 6? = 11
      Q4: What is 3 + 9? = 12
      Q5: What is 8 + 5? = 13

✓ All tests complete!
```

## 🐛 Troubleshooting

### "Connection refused" to Redis
**Solution**: Start Redis server
```bash
redis-server
```

### USSD timeout (>15 seconds)
**Causes**:
- Slow LLM response (network latency)
- Redis not running locally
- ngrok tunnel instability

**Solutions**:
- Check ngrok logs: `http://localhost:4040`
- Ensure Redis is local (not remote)
- Verify Groq API key is valid

### SMS not received in sandbox
**Causes**:
- Invalid phone number format
- Africa's Talking API key missing/wrong
- Sandbox limitations

**Solutions**:
- Use test format: `+254711XXXXXX` (Kenya sandbox)
- Check Africa's Talking logs in dashboard
- Verify `AT_API_KEY` in `.env`

### LLM validation error
**Error**: `Input should be a valid string`

**Cause**: LLM returning integers as answers

**Solution**: Already handled! The `QuizQuestion` model uses `Union[str, int]` with automatic conversion.

### Session not persisting between requests
**Causes**:
- Different `sessionId` used across requests
- Redis session expired (5 min default)
- Redis server not running

**Solutions**:
- Use same `sessionId` for conversation flow
- Increase `SESSION_TIMEOUT` in `.env`
- Verify Redis: `redis-cli ping` (should return `PONG`)

## 🚦 Development Workflow

### Running in development
```bash
# Terminal 1
redis-server

# Terminal 2
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3
ngrok http 8000
```

### Running tests
```bash
# Test LLM integration
python test_llm.py

# Test SMS formatting (debug mode)
curl http://localhost:8000/test-sms/+26771234567
```

### Monitoring logs
```bash
# FastAPI logs
# Watch Terminal 2 for request logs

# ngrok requests
# Open http://localhost:4040 in browser

# Redis commands
redis-cli monitor
```

## 🛣️ Roadmap

### ✅ Completed
- [x] Core USSD menu system
- [x] Redis session management
- [x] Africa's Talking SMS integration
- [x] Static quiz bank (4 topics, 10 questions each)
- [x] LLM quiz generation (Groq integration)
- [x] SMS cost optimization (60-70% reduction)
- [x] Graceful LLM fallback

### 🔜 Future Enhancements (Phase 3)
- [ ] Live chat mode (student asks questions via USSD)
- [ ] Multi-language support (English + Setswana)
- [ ] Progress tracking (student performance analytics)
- [ ] Teacher dashboard (monitor student activity)
- [ ] Advanced topics (fractions, decimals, word problems)
- [ ] WhatsApp integration (alternative to SMS)

## 📊 Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) 0.115.6 (async Python web framework)
- **Session Store**: [Redis](https://redis.io/) 7.0+ (in-memory data store)
- **LLM**: [Groq](https://groq.com/) with Llama 3.1 8B Instant
- **SMS Gateway**: [Africa's Talking](https://africastalking.com/) API
- **Validation**: [Pydantic](https://pydantic.dev/) 2.10.5 (data validation)
- **HTTP Client**: [httpx](https://www.python-httpx.org/) (async requests)
- **Dev Tools**: ngrok, uvicorn, python-dotenv

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Immanuel Nanyaro**
- Email: nnyimm001@myuct.ac.za
- GitHub: [@immanueln98](https://github.com/immanueln98)

## 🙏 Acknowledgments

- [Africa's Talking](https://africastalking.com/) for USSD/SMS infrastructure
- [Groq](https://groq.com/) for ultra-fast LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent async framework
- Built with assistance from [Claude Code](https://claude.com/claude-code)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/immanueln98/ussd-edu/issues)
- Email: nnyimm001@myuct.ac.za

---

**Built for Education. Optimized for Africa. Powered by AI.**
