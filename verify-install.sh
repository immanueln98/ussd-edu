#!/bin/bash

echo "=== Verifying Prerequisites for USSD-Edu-Demo ==="
echo ""

# Check Python
echo "1. Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✓ $PYTHON_VERSION"
else
    echo "✗ Python 3 is not installed"
fi
echo ""

# Check Redis
echo "2. Checking Redis..."
if command -v redis-server &> /dev/null; then
    REDIS_VERSION=$(redis-server --version)
    echo "✓ $REDIS_VERSION"

    # Check if Redis is running
    if redis-cli ping &> /dev/null; then
        echo "✓ Redis server is running"
    else
        echo "⚠ Redis is installed but not running. Start it with: redis-server"
    fi
else
    echo "✗ Redis is not installed"
fi
echo ""

# Check ngrok
echo "3. Checking ngrok..."
if command -v ngrok &> /dev/null; then
    NGROK_VERSION=$(ngrok version)
    echo "✓ ngrok version: $NGROK_VERSION"
else
    echo "✗ ngrok is not installed"
fi
echo ""

echo "=== Summary ==="
ALL_GOOD=true

if ! command -v python3 &> /dev/null; then
    echo "⚠ Install Python: brew install python3"
    ALL_GOOD=false
fi

if ! command -v redis-server &> /dev/null; then
    echo "⚠ Install Redis: brew install redis"
    ALL_GOOD=false
fi

if ! command -v ngrok &> /dev/null; then
    echo "⚠ Install ngrok: brew install ngrok/ngrok/ngrok"
    ALL_GOOD=false
fi

if [ "$ALL_GOOD" = true ]; then
    echo "✓ All prerequisites are installed!"
    echo ""
    echo "Next steps:"
    echo "  1. Create virtual environment: python3 -m venv venv"
    echo "  2. Activate it: source venv/bin/activate"
    echo "  3. Install dependencies: pip install -r requirements.txt"
    echo "  4. Copy .env file: cp .env.example .env"
else
    echo ""
    echo "Please install missing prerequisites using the commands above."
fi
