# Quickstart

Get running in under 5 minutes. If you want explanations or run into issues, check [GETTING_STARTED.md](GETTING_STARTED.md).

## Docker (Recommended)

```bash
git clone https://github.com/yourusername/distributed-rate-limiter.git
cd distributed-rate-limiter
docker-compose up -d

# Test it
curl -X POST http://localhost:8000/api/resource -H "X-API-Key: myuser"
```

Open http://localhost:8000/docs to see the interactive API documentation.

## Local Development

```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Setup Python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload
```

## Quick Test

Send 25 requests to see rate limiting in action (limit is 20/min):

```bash
for i in {1..25}; do
  curl -s -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: test" -w " %{http_code}\n"
done
```

First 20 will return `200`, the rest will hit `429 Too Many Requests`.

## Useful Commands

```bash
docker-compose logs -f          # View logs
docker-compose down             # Stop everything
docker-compose restart          # Restart services
docker exec -it rate_limiter_redis redis-cli  # Access Redis
```

## Troubleshooting

**Port 8000 already in use?** 
Edit `docker-compose.yml` and change `"8000:8000"` to `"8001:8000"`, then access at `localhost:8001`.

**Redis connection errors?** 
Check if it's running: `docker ps | grep redis`

For detailed setup and explanations, see [GETTING_STARTED.md](GETTING_STARTED.md).

---

**Next steps:**
- [TESTING.md](TESTING.md) - Run the test suite
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment options
- [README.md](README.md) - Full documentation
