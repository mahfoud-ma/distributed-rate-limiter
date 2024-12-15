# Testing Guide

How to test the rate limiter and verify it's working correctly.

> **Note:** The service needs to be running first. See [QUICKSTART.md](QUICKSTART.md) or [GETTING_STARTED.md](GETTING_STARTED.md).

## Quick Test

```bash
./start.sh          # Start the service
./run_tests.sh      # Run test suite
```

All 12 tests should pass.

## Test Suite Overview

The `run_tests.sh` script runs 12 tests covering:

1. Health check endpoint
2. Service information and version
3. Protected resource access (with API key)
4. Empty JSON body handling
5. Missing request body handling
6. Rate limiting enforcement (20 requests/minute)
7. Rate limit status endpoint
8. RFC 6585 compliant rate limit headers
9. IP-based rate limiting (fallback when no API key)
10. Redis backend verification
11. Status endpoint doesn't consume quota
12. Partial JSON body handling

## Manual Testing

Sometimes you want to test specific scenarios yourself.

### Basic Request

```bash
curl -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: test" \
  -H "Content-Type: application/json" \
  -d '{"action": "process"}'
```

### Edge Cases

**Empty JSON:**
```bash
curl -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: test" \
  -H "Content-Type: application/json" \
  -d '{}'
```

This should work fine - the service handles optional fields gracefully.

**Partial JSON:**
```bash
curl -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: test" \
  -d '{"action":"custom"}'
```

Also valid - `data` field is optional.

### Rate Limiting

Hit the limit to see it in action:

```bash
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: testuser" \
    -s -o /dev/null -w "%{http_code} "
done
echo ""
```

You'll see `200` twenty times, then `429` for the remaining five requests.

### Rate Limit Headers

Check the headers being returned:

```bash
curl -i -X POST http://localhost:8000/api/resource \
  -H "X-API-Key: headertest" | grep "x-ratelimit"
```

Should show:
- `x-ratelimit-limit: 20`
- `x-ratelimit-remaining: 19` (or less)
- `x-ratelimit-reset: <timestamp>`

### Check Status Without Using Quota

```bash
curl http://localhost:8000/rate-limit/status \
  -H "X-API-Key: testuser" | python3 -m json.tool
```

This endpoint doesn't count against your rate limit, which is useful for dashboards or monitoring.

### IP-Based Limiting

If you don't provide an API key, the service falls back to IP-based limiting:

```bash
for i in {1..25}; do
  curl -X POST http://localhost:8000/api/resource \
    -s -o /dev/null -w "%{http_code} "
done
```

Same behavior - 20 allowed, then blocked.

## Unit Tests with pytest

If you want to run the actual unit tests:

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=app --cov-report=term

# Specific test file
pytest tests/test_rate_limiter.py -v

# Single test
pytest tests/test_endpoints.py::test_health_check -v
```

The unit tests mock Redis so they run fast and don't need the service running.

## Load Testing

Simulate real-world load to see how the system performs:

```bash
python scripts/load_test.py --requests 1000 --concurrent 50
```

This sends 1000 requests using 50 concurrent connections. You'll get metrics like:

```
Test Configuration:
  Total requests:     1000
  Duration:           2.34s
  Throughput:         427.35 req/s

Request Results:
  Success:            766 (76.6%)
  Rate limited:       234 (23.4%)
  Failed:             0 (0.0%)

Latency (milliseconds):
  Average:            3.24ms
  Median (P50):       2.87ms
  P95:                4.82ms
  P99:                6.15ms
```

### Custom Load Test

```bash
python scripts/load_test.py \
  --requests 5000 \
  --concurrent 100 \
  --users 20 \
  --url http://localhost:8000/api/resource
```

Adjust the parameters based on what you're testing.

## High Availability Testing

If you're running the Sentinel setup, test automatic failover:

```bash
# Start Sentinel configuration
docker-compose -f docker-compose.sentinel.yml up -d

# Run failover test
chmod +x scripts/test_failover.sh
./scripts/test_failover.sh
```

This test:
1. Pauses the Redis master
2. Waits for Sentinel to detect the failure
3. Verifies a replica gets promoted
4. Tests that the API still works with the new master
5. Cleans up

The entire failover should complete in under 10 seconds.

## Understanding Test Results

**200 OK** - Request processed successfully  
**429 Too Many Requests** - Rate limit exceeded (expected after 20 requests)  
**422 Unprocessable Entity** - Should never happen with current implementation

If you're getting unexpected 422 errors, make sure you're using the latest code that handles optional fields.

## Troubleshooting Tests

### Redis Connection Errors

```bash
# Check if Redis is running
docker ps | grep redis

# Restart it
docker-compose restart redis

# Or start manually
docker run --name redis-ratelimiter -d -p 6379:6379 redis:7-alpine
```

### Tests Timeout

Make sure the service is actually running:

```bash
curl http://localhost:8000/health
```

If that times out, check logs:
```bash
docker-compose logs -f
```

### Rate Limits Not Resetting

Keys expire after 60 seconds automatically. If you want to force a reset:

```bash
docker exec rate_limiter_redis redis-cli FLUSHALL
```

Be careful with this command - it deletes everything in Redis.

### Port Conflicts

If something else is using port 8000:

```bash
# Check what's using the port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Or change the port in docker-compose.yml
```

## Performance Benchmarks

Under normal conditions, the system should achieve:

- Average latency: < 5ms
- P95 latency: < 7ms  
- P99 latency: < 10ms
- Throughput: > 400 req/s
- Zero errors under 1000 concurrent requests

If you're seeing much worse performance, check:
- Redis latency: `docker exec rate_limiter_redis redis-cli --latency`
- System resources: `docker stats`
- Network issues: Are you running on the same machine or over a network?

## Continuous Testing

### Watch Mode (Development)

Auto-run tests when code changes:

```bash
pytest-watch tests/
```

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
pytest tests/ || exit 1
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## What to Test Before Deploying

Before pushing to production, verify:

1. All 12 integration tests pass
2. Load test shows acceptable performance
3. Rate limiting actually blocks requests after limit
4. Headers are present and correct
5. Status endpoint doesn't consume quota
6. Logs don't show errors or warnings
7. Redis is persisting data correctly

Run the full test suite one more time:
```bash
./run_tests.sh && python scripts/load_test.py --requests 1000 --concurrent 50
```

If everything passes, you're good to deploy.

---

**Related Documentation:**
- [QUICKSTART.md](QUICKSTART.md) - Getting the service running
- [GETTING_STARTED.md](GETTING_STARTED.md) - Detailed setup
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [README.md](README.md) - Full project documentation
