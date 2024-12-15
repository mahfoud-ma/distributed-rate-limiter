#!/bin/bash

# Startup script for Distributed Rate Limiter

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

clear
echo "================================================================"
echo -e "${BOLD}Distributed Rate Limiting Service${NC}"
echo "================================================================"
echo ""

# Check if Redis is running
echo -e "${BLUE}[1/3]${NC} Checking Redis..."
if docker ps | grep -q redis-ratelimiter; then
    echo -e "${GREEN}     Redis is already running${NC}"
else
    echo -e "${YELLOW}     Starting Redis container...${NC}"
    docker run --name redis-ratelimiter -d -p 6379:6379 --network host redis:7-alpine > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}     Redis started successfully${NC}"
    else
        # Container might already exist but stopped
        docker start redis-ratelimiter > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}     Redis started successfully${NC}"
        else
            echo -e "${RED}     Failed to start Redis${NC}"
            echo -e "${YELLOW}     Try: docker rm redis-ratelimiter${NC}"
            exit 1
        fi
    fi
    sleep 2
fi
echo ""

# Check Python virtual environment
echo -e "${BLUE}[2/3]${NC} Checking Python environment..."
if [ -d "venv" ]; then
    echo -e "${GREEN}     Virtual environment found${NC}"
else
    echo -e "${YELLOW}     Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi
echo ""

# Start the application
echo -e "${BLUE}[3/3]${NC} Starting FastAPI application..."
echo ""
echo "================================================================"
echo -e "${BOLD}Service Starting...${NC}"
echo "================================================================"
echo ""
echo -e "${GREEN}Available at:${NC}"
echo "  - API:          http://localhost:8000"
echo "  - Health:       http://localhost:8000/health"
echo "  - Docs:         http://localhost:8000/docs"
echo "  - Rate Status:  http://localhost:8000/rate-limit/status"
echo ""
echo -e "${YELLOW}To run tests:${NC} ./run_tests.sh (in another terminal)"
echo -e "${YELLOW}To stop:${NC} Ctrl+C"
echo ""
echo "================================================================"
echo ""

# Start with production logging (less verbose)
./venv/bin/uvicorn app.main_simple:app --host 0.0.0.0 --port 8000 --reload

# Cleanup on exit
echo ""
echo "Shutting down..."
