# Quickstart - 5 Minutes

Get the rate limiter running with minimal setup. For detailed explanations, see [GETTING_STARTED.md](GETTING_STARTED.md).

## Option 1: Docker (Recommended)

```bash
# Clone and start
git clone https://github.com/mahfoud-ma/distributed-rate-limiter.git
cd distributed-rate-limiter
docker-compose up -d

# Test
curl -X POST http://localhost:8000/api/resource -H "X-API-Key: myuser"

# View docs
open http://localhost:8000/docs
```

## Option 2: Local Development

```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Setup Python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run app
uvicorn app.main:app --reload

# Test (in another terminal)
curl -X POST http://localhost:8000/api/resource -H "X-API-Key: myuser"
```

## Option 3: Using Helper Scripts

```bash
# Start everything
./start.sh

# Run tests
./run_tests.sh
```

## Test Rate Limiting

```bash
# Send 25 requests (limit is 20/min)
for i in {1..25}; do
  curl -s -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: test" -w " %{http_code}\n"
done
# You'll see: 200 200 200... (20x) then 429 429 429... (5x)
```

## Check Status

```bash
curl http://localhost:8000/rate-limit/status -H "X-API-Key: test"
```

## Common Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart
docker-compose restart

# Access Redis CLI
docker exec -it rate_limiter_redis redis-cli
```

## Troubleshooting

**Port in use?** Edit `docker-compose.yml` and change `"8000:8000"` to `"8001:8000"`

**Redis error?** Check: `docker ps | grep redis`

**Need help?** See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed guide.

---

**Next Steps:**
- [TESTING.md](TESTING.md) - Run comprehensive tests
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deploy to production
- [README.md](README.md) - Full documentation
