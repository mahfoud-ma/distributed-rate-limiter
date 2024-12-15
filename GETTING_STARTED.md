# Getting Started

Detailed walkthrough to set up and understand the rate limiter. If you just want to get it running quickly, check [QUICKSTART.md](QUICKSTART.md) instead.

## Prerequisites

You'll need:
- Docker and Docker Compose ([Download](https://www.docker.com/get-started))
- Git
- Python 3.11+ (only if running locally without Docker)

## Installation

### Clone the Repository

```bash
git clone https://github.com/yourusername/distributed-rate-limiter.git
cd distributed-rate-limiter
```

### Choose Your Setup

**Docker (Recommended)**

This is the easiest way to get started. Everything runs in containers with no dependency headaches.

```bash
docker-compose up -d

# Verify it's running
docker-compose ps
```

Both containers should show "Up" status.

**Local Development**

If you prefer running the app directly on your machine:

```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start the application
uvicorn app.main:app --reload
```

**Helper Script**

There's a convenience script that handles everything:

```bash
./start.sh
```

It checks if Redis is running, activates the virtual environment, and starts the service.

## Verify Everything Works

### Health Check

```bash
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "redis": "connected",
  "version": "1.0.0"
}
```

If Redis shows "disconnected", check that the Redis container is running.

### Interactive Documentation

Open http://localhost:8000/docs in your browser. You'll see Swagger UI with all available endpoints. This is useful for testing requests without curl.

## Test the Rate Limiter

### Make a Request

```bash
curl -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: testuser" \
  -H "Content-Type: application/json" \
  -d '{"action": "test"}'
```

Look for the rate limit headers in the response:
- `x-ratelimit-limit: 20` - Maximum requests allowed per minute
- `x-ratelimit-remaining: 19` - How many you have left
- `x-ratelimit-reset: 1729783200` - Unix timestamp when the limit resets

### Check Your Status

```bash
curl http://localhost:8000/rate-limit/status -H "X-API-Key: testuser"
```

This endpoint doesn't consume your rate limit quota, so you can check it as often as you want.

### Hit the Limit

Send 25 requests to see rate limiting in action:

```bash
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: ratelimitest" \
    -s -o /dev/null -w "Request $i: %{http_code}\n"
done
```

The first 20 succeed with `200`, then you'll start getting `429 Too Many Requests`.

## Understanding the System

### How It Works

The service uses middleware to intercept every request before it reaches your endpoint. It checks a Redis counter for your identifier (from the `X-API-Key` header, or your IP address if no key is provided).

Redis operations are atomic, which prevents race conditions when multiple requests come in simultaneously. The counter has a TTL (time-to-live) that matches the rate limit window, so keys automatically expire and reset.

### Redis Key Pattern

Keys look like: `rate:user:testuser:2025-10-25-14:30`

- `rate` - prefix for all rate limit keys
- `user` - the limiter type (could also be `ip`)
- `testuser` - your identifier
- `2025-10-25-14:30` - the time window

Each window is 60 seconds. After that, the key expires and your count resets.

### Viewing Redis Keys

```bash
docker exec -it rate_limiter_redis redis-cli

# Inside Redis CLI:
KEYS rate:*                    # See all rate limit keys
GET rate:user:testuser:*       # Check a specific user's count
TTL rate:user:testuser:*       # Time until reset
exit
```

## Explore Further

### View Logs

Watch what's happening in real-time:

```bash
# Docker
docker-compose logs -f

# Local development
# Logs appear in the terminal where the app is running
```

### Run the Test Suite

```bash
./run_tests.sh
```

All 12 tests should pass. This covers health checks, rate limiting logic, headers, fallback behavior, and edge cases.

### Load Testing

See how the system performs under stress:

```bash
python scripts/load_test.py --requests 1000 --concurrent 50
```

This simulates 1000 requests with 50 concurrent users. You'll get performance metrics like average latency and throughput.

## Configuration

### Adjust Rate Limits

Edit `app/config.py`:

```python
RATE_LIMIT_STRATEGIES = {
    "user": {
        "limit": 20,   # Change this value
        "window": 60,
    },
}
```

Restart the service after changing configuration.

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=INFO       # Use WARNING in production
ENVIRONMENT=development
```

## Advanced: High Availability Setup

If you need resilience against Redis failures, use the Sentinel configuration:

```bash
# Stop the basic setup
docker-compose down

# Start HA setup (1 master, 2 replicas, 3 sentinels)
docker-compose -f docker-compose.sentinel.yml up -d

# Verify all 7 containers are running
docker-compose -f docker-compose.sentinel.yml ps

# Test automatic failover
chmod +x scripts/test_failover.sh
./scripts/test_failover.sh
```

Sentinel automatically detects when the master fails and promotes a replica. The application reconnects without manual intervention.

## Troubleshooting

**Port 8000 already in use**

Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"
```

Then access the API at `localhost:8001`.

**Docker containers won't start**

```bash
# Check what's wrong
docker-compose logs

# Try rebuilding from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Redis connection errors**

```bash
# Make sure Redis is running
docker ps | grep redis

# Restart it
docker-compose restart redis
```

**Rate limits not working**

Check that Redis is storing keys:
```bash
docker exec -it rate_limiter_redis redis-cli KEYS "rate:*"
```

If you see no keys after making requests, there's a connection issue between the app and Redis.

For more issues, see the [Common Issues section in README.md](README.md#common-issues).

## Next Steps

Now that you have the system running:

- Read [README.md](README.md) for architecture details and the algorithm explanation
- Follow [TESTING.md](TESTING.md) for comprehensive testing strategies
- Check [DEPLOYMENT.md](DEPLOYMENT.md) when you're ready to deploy to production

The service is designed to be straightforward. If something's confusing or broken, it's worth improving the documentation or code.
