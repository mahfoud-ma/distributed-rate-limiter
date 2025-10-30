# Getting Started - Complete Tutorial

Step-by-step guide to get the rate limiter running. For quick setup without explanations, see [QUICKSTART.md](QUICKSTART.md).

## Prerequisites

- [ ] Docker & Docker Compose installed ([Download](https://www.docker.com/get-started))
- [ ] Git installed
- [ ] Terminal/command prompt access
- [ ] **Optional:** Python 3.11+ for local development

## Step 1: Get the Code

```bash
git clone https://github.com/mahfoud-ma/distributed-rate-limiter.git
cd distributed-rate-limiter
```

- [ ] Repository cloned successfully

## Step 2: Choose Deployment Method

### Option A: Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# Verify containers are running
docker-compose ps
# Expected: rate_limiter_api and rate_limiter_redis both "Up"
```

- [ ] Docker containers started
- [ ] Both containers showing status "Up"

### Option B: Local Development

```bash
# 1. Start Redis
docker run -d -p 6379:6379 --name redis redis:7-alpine

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start application
uvicorn app.main:app --reload
```

- [ ] Redis container running
- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] Application started on port 8000

### Option C: Using Helper Script

```bash
./start.sh
```

This script automatically:
- Checks if Redis is running, starts it if needed
- Activates virtual environment
- Starts the FastAPI application

- [ ] Script executed successfully
- [ ] Service running on http://localhost:8000

## Step 3: Verify Installation

### Health Check

```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "version": "1.0.0",
  "timestamp": "2025-10-25T14:30:45Z"
}
```

- [ ] Health check returns "healthy"
- [ ] Redis shows "connected"

### Interactive Documentation

Open your browser to: http://localhost:8000/docs

- [ ] Swagger UI loads correctly
- [ ] Can see all 4 endpoints listed
- [ ] Can try out requests interactively

## Step 4: Test Basic Functionality

### Make a Request

```bash
curl -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: testuser" \
  -H "Content-Type: application/json" \
  -d '{"action": "test"}'
```

**Expected Response:** `200 OK` with rate limit headers

- [ ] Request successful (200 OK)
- [ ] Response includes `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset` headers

### Check Rate Limit Status

```bash
curl http://localhost:8000/rate-limit/status \
  -H "X-API-Key: testuser"
```

**Expected:** Status showing limit, remaining, and reset time

- [ ] Status endpoint works
- [ ] Shows correct rate limit (20/min)

## Step 5: Test Rate Limiting

Send 25 requests to exceed the limit (20/min):

```bash
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: ratelimitest" \
    -s -o /dev/null -w "Request $i: %{http_code}\n"
done
```

**Expected Output:**
- Requests 1-20: `200` (Success)
- Requests 21-25: `429` (Rate limited)

- [ ] First 20 requests succeeded
- [ ] Requests 21+ were rate limited (429)

## Step 6: Explore Features

### View Logs

```bash
# Docker deployment
docker-compose logs -f

# Local development
# Logs appear in terminal where app is running
```

- [ ] Can view application logs

### Access Redis CLI

```bash
docker exec -it rate_limiter_redis redis-cli

# Inside Redis CLI:
KEYS rate:*                    # List all rate limit keys
GET rate:user:testuser:*       # Get specific user's count
TTL rate:user:testuser:*       # Check time-to-live
exit
```

- [ ] Can access Redis CLI
- [ ] Can see rate limit keys

### Run Test Suite

```bash
./run_tests.sh
```

**Expected:** All 12 tests passing

- [ ] All tests pass (12/12)

### Run Load Test

```bash
python scripts/load_test.py --requests 1000 --concurrent 50
```

- [ ] Load test completes successfully
- [ ] Can see performance metrics

## Step 7: Advanced Setup (Optional)

### High Availability with Sentinel

```bash
# Stop simple setup
docker-compose down

# Start HA setup
docker-compose -f docker-compose.sentinel.yml up -d

# Verify all 7 containers running
docker-compose -f docker-compose.sentinel.yml ps

# Test failover
chmod +x scripts/test_failover.sh
./scripts/test_failover.sh
```

- [ ] HA setup running (7 containers)
- [ ] Failover test successful

### Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit configuration
nano .env  # or your favorite editor
```

**Key settings:**
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=WARNING  # WARNING for production, INFO for debug
ENVIRONMENT=production
```

- [ ] Environment file created
- [ ] Settings configured

### Adjust Rate Limits

Edit [app/config.py](app/config.py):

```python
RATE_LIMIT_STRATEGIES = {
    "user": {
        "limit": 20,   # Change this value
        "window": 60,
    },
}
```

Restart the service for changes to take effect:
```bash
docker-compose restart  # or Ctrl+C and restart if running locally
```

- [ ] Rate limits adjusted (if needed)

## Completion Checklist

You're all set if you can check all these:

- [ ] Service is running
- [ ] Health check returns "healthy"
- [ ] Can make successful API requests
- [ ] Rate limiting works (429 after 20 requests)
- [ ] Can view interactive API docs
- [ ] Test suite passes (12/12)
- [ ] Understand the architecture (see [README.md](README.md))

## Troubleshooting

### Port 8000 Already in Use

**Solution:** Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Use port 8001 instead
```

Then access at: http://localhost:8001

### Docker Containers Won't Start

```bash
# Check Docker is running
docker ps

# View error logs
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Redis Connection Error

```bash
# Check Redis is running
docker ps | grep redis

# Restart Redis
docker-compose restart redis
```

### Can't Connect to API

```bash
# Check API logs
docker-compose logs api

# Try with explicit host
curl http://127.0.0.1:8000/health
```

For more troubleshooting, see [README.md - Common Issues](README.md#common-issues).

## Next Steps

### Learn More About the System
- Read [README.md](README.md) for full documentation
- Understand the [fixed window counter algorithm](README.md#algorithm-fixed-window-counter)
- Review the [project structure](README.md#project-structure)

### Test Thoroughly
- Follow [TESTING.md](TESTING.md) for comprehensive testing
- Run load tests to see performance
- Try failover testing with Sentinel setup

### Deploy to Production
- Read [DEPLOYMENT.md](DEPLOYMENT.md) for deployment options
- Configure security settings
- Set up monitoring and alerting

### Customize
- Adjust rate limits in [app/config.py](app/config.py)
- Modify response formats in [app/models.py](app/models.py)
- Add new endpoints in [app/main.py](app/main.py)

---

**Congratulations!** You have a working distributed rate limiter. 

**Need Help?**
- Quick Commands: [QUICKSTART.md](QUICKSTART.md)
- Testing Guide: [TESTING.md](TESTING.md)
- Production Deploy: [DEPLOYMENT.md](DEPLOYMENT.md)
- Full Docs: [README.md](README.md)
