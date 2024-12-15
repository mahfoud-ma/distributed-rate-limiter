# Deployment Guide

Different strategies for deploying the rate limiter to production.

## Quick Deployment Options

**Simple (Docker Compose)** - Good for small production deployments, development, testing  
**High Availability (Sentinel)** - For production systems that need resilience  
**Manual (systemd)** - Full control, custom environments  
**Cloud Platforms** - AWS, GCP, DigitalOcean, Kubernetes

## Docker Compose (Simple)

The easiest production deployment. One command and you're running.

### Prerequisites

- Docker 20.10+
- Docker Compose 1.29+
- A server with at least 2GB RAM

### Deploy

```bash
# Clone and configure
git clone https://github.com/yourusername/distributed-rate-limiter.git
cd distributed-rate-limiter

# Optional: Set environment variables
cp .env.example .env
nano .env

# Start services
docker-compose up -d

# Verify it's working
curl http://localhost:8000/health
```

### Check Logs

```bash
docker-compose logs -f
```

### Update Deployment

```bash
git pull origin main
docker-compose up -d --build
```

### Stop Services

```bash
docker-compose down
```

This is fine for many use cases. If you need more reliability, consider the Sentinel setup.

## High Availability with Sentinel

For production systems where downtime isn't acceptable.

### Architecture

- 1 Redis master (handles writes)
- 2 Redis replicas (read copies, can become master)
- 3 Sentinels (monitor health, handle failover)
- 1 FastAPI application

If the master fails, Sentinels automatically promote a replica. The app reconnects without manual intervention.

### Deploy

```bash
# Start HA setup
docker-compose -f docker-compose.sentinel.yml up -d

# Verify all 7 containers are running
docker-compose -f docker-compose.sentinel.yml ps

# Test failover
./scripts/test_failover.sh
```

### How Sentinel Works

Sentinels constantly ping the master. If the master stops responding for 5 seconds (configurable), they hold a vote. If 2 out of 3 agree it's down, they promote a replica to master.

The application uses Sentinel-aware Redis client, so it automatically discovers the new master.

### Configure Sentinel

Edit `sentinel.conf`:

```conf
# How many sentinels must agree master is down
sentinel monitor mymaster redis-master 6379 2

# How long to wait before declaring master down (milliseconds)
sentinel down-after-milliseconds mymaster 5000

# Timeout for failover process
sentinel failover-timeout mymaster 10000
```

### Monitor Sentinel

```bash
# Connect to any sentinel
docker exec -it redis_sentinel1 redis-cli -p 26379

# Check master status
SENTINEL master mymaster

# List sentinels
SENTINEL sentinels mymaster

# List replicas
SENTINEL replicas mymaster
```

### Failover Testing

The test script simulates master failure:

```bash
./scripts/test_failover.sh
```

It pauses the master container, waits for failover, verifies the app still works, then restores everything. Useful for verifying your setup before going live.

## Manual Deployment (systemd)

If you prefer running the service directly on your server without Docker.

### Server Requirements

- Ubuntu 20.04+ / Debian 11+ / RHEL 8+
- Python 3.11+
- Redis 7.0+
- At least 2GB RAM

### Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip redis-server
```

**RHEL/CentOS:**
```bash
sudo dnf install -y python3.11 python3-pip redis
```

### Install Application

```bash
# Create dedicated user
sudo useradd -r -s /bin/bash -d /opt/rate-limiter ratelimiter

# Clone repository
sudo -u ratelimiter git clone \
  https://github.com/yourusername/distributed-rate-limiter.git \
  /opt/rate-limiter

cd /opt/rate-limiter

# Setup Python environment
sudo -u ratelimiter python3.11 -m venv venv
sudo -u ratelimiter venv/bin/pip install -r requirements.txt

# Configure
sudo -u ratelimiter cp .env.example .env
sudo -u ratelimiter nano .env
```

### Configure Redis

Edit `/etc/redis/redis.conf`:

```conf
# Memory limit (adjust based on your needs)
maxmemory 256mb
maxmemory-policy allkeys-lru

# Disable persistence (rate limiting doesn't need it)
save ""
```

Restart Redis:
```bash
sudo systemctl restart redis
```

### Create systemd Service

Create `/etc/systemd/system/rate-limiter.service`:

```ini
[Unit]
Description=Distributed Rate Limiting Service
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=ratelimiter
Group=ratelimiter
WorkingDirectory=/opt/rate-limiter
Environment="PATH=/opt/rate-limiter/venv/bin"
ExecStart=/opt/rate-limiter/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable rate-limiter
sudo systemctl start rate-limiter

# Check status
sudo systemctl status rate-limiter

# View logs
sudo journalctl -u rate-limiter -f
```

### Nginx Reverse Proxy (Optional)

If you want to expose the service through Nginx:

Create `/etc/nginx/sites-available/rate-limiter`:

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/rate-limiter /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Cloud Platforms

### AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p docker rate-limiter

# Create environment
eb create rate-limiter-prod

# Deploy updates
eb deploy
```

### Google Cloud Run

```bash
# Build image
gcloud builds submit --tag gcr.io/PROJECT_ID/rate-limiter

# Deploy
gcloud run deploy rate-limiter \
  --image gcr.io/PROJECT_ID/rate-limiter \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### DigitalOcean App Platform

1. Connect your GitHub repository
2. Select "Dockerfile" as build method
3. Set environment variables
4. Click "Deploy"

DigitalOcean handles everything else.

### Kubernetes

Create `kubernetes/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rate-limiter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rate-limiter
  template:
    metadata:
      labels:
        app: rate-limiter
    spec:
      containers:
      - name: rate-limiter
        image: yourusername/rate-limiter:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_HOST
          value: redis-service
        - name: LOG_LEVEL
          value: INFO
---
apiVersion: v1
kind: Service
metadata:
  name: rate-limiter-service
spec:
  selector:
    app: rate-limiter
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

Apply:
```bash
kubectl apply -f kubernetes/deployment.yaml
```

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Redis health
redis-cli ping
```

Set up automated health checks to restart the service if it becomes unhealthy.

### Logs

**Docker:**
```bash
docker-compose logs -f
```

**systemd:**
```bash
journalctl -u rate-limiter -f
```

**Kubernetes:**
```bash
kubectl logs -f deployment/rate-limiter
```

### Metrics (Not Yet Implemented)

Consider adding Prometheus metrics for production monitoring:

```python
# Future enhancement in app/main.py
from prometheus_client import Counter, Histogram

rate_limit_requests = Counter('rate_limit_requests_total', 'Total requests checked')
rate_limit_exceeded = Counter('rate_limit_exceeded_total', 'Total rate limits hit')
request_latency = Histogram('request_latency_seconds', 'Request latency')
```

Then expose `/metrics` endpoint for Prometheus to scrape.

## Security

### Production Checklist

Before going live:

- Set `ENVIRONMENT=production`
- Use strong Redis password: `REDIS_PASSWORD=<generate-strong-password>`
- Enable TLS/SSL for Redis (especially if not on localhost)
- Use HTTPS for API (configure reverse proxy)
- Implement proper authentication (JWT, OAuth2, etc.)
- Configure firewall to only expose necessary ports
- Set up log rotation
- Enable automatic security updates
- Back up Redis data if persistence is needed
- Review rate limits for your use case

### Redis Security

Edit `redis.conf`:

```conf
requirepass your-strong-password-here
bind 127.0.0.1  # Only accept local connections
protected-mode yes
```

### Firewall

Using UFW on Ubuntu:

```bash
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 22/tcp    # SSH (be careful!)
sudo ufw enable
```

Don't expose Redis port (6379) to the internet unless absolutely necessary and properly secured.

## Backup and Recovery

### Redis Backup

Rate limiting data is ephemeral (expires after 60 seconds), so backups aren't critical. But if you need them:

```bash
# Manual backup
redis-cli SAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# Restore
sudo systemctl stop redis
cp /backup/redis-backup.rdb /var/lib/redis/dump.rdb
sudo systemctl start redis
```

### Application Backup

Back up your configuration:

```bash
tar -czf rate-limiter-config-$(date +%Y%m%d).tar.gz \
  .env \
  docker-compose.yml \
  sentinel.conf
```

Keep these backups somewhere safe. The code is in git, but your specific configuration isn't.

## Common Deployment Issues

### Service Won't Start

Check logs:
```bash
docker-compose logs api
```

Test Redis connectivity from the app:
```bash
docker-compose exec api python -c "from app.redis_client import get_redis_client; print(get_redis_client().ping())"
```

### High Memory Usage

Check Redis memory:
```bash
redis-cli INFO memory
```

If it's growing unbounded, verify TTL is set correctly on keys:
```bash
redis-cli TTL rate:user:someuser:<timestamp>
```

Should show a value between 0-60 seconds. If it shows -1, keys aren't expiring.

### Slow Response Times

Check Redis latency:
```bash
redis-cli --latency
```

Check for slow queries:
```bash
redis-cli SLOWLOG GET 10
```

If Redis is slow, you might need to:
- Increase server resources
- Move Redis to a dedicated server
- Use Redis Cluster for horizontal scaling

### Network Issues

Make sure containers can communicate:
```bash
docker-compose exec api ping redis
```

If running on different servers, check firewall rules and network connectivity.

## Scaling Considerations

**Current setup handles:**
- 400+ requests/second
- 1000+ concurrent connections
- Tens of thousands of unique users

**When you need to scale beyond this:**

1. Use Redis Cluster (horizontal scaling, not just replication)
2. Run multiple API instances behind a load balancer
3. Consider a CDN for static content
4. Move to a managed Redis service (AWS ElastiCache, Redis Cloud)
5. Implement response caching where appropriate

For most use cases, a single instance is sufficient.

## Next Steps After Deployment

1. Set up monitoring and alerts
2. Configure automated backups (if needed)
3. Test failover procedures (if using HA setup)
4. Document your deployment for the team
5. Create a runbook for common issues
6. Set up automated deployments (CI/CD)

If something breaks in production, check logs first. Most issues are configuration-related.

---

For questions about specific deployment scenarios, open an issue on GitHub or check the [README](README.md) for more details.
