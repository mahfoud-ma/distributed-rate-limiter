# Deployment Guide

This guide covers different deployment strategies for the distributed rate limiting service.

## Table of Contents

- [Docker Compose (Simple)](#docker-compose-simple)
- [Docker Compose with Sentinel (HA)](#docker-compose-with-sentinel-ha)
- [Manual Deployment](#manual-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring & Observability](#monitoring--observability)

## Docker Compose (Simple)

Best for: Development, testing, small production deployments

### Prerequisites

- Docker 20.10+
- Docker Compose 1.29+

### Deployment Steps

```bash
# 1. Clone repository
git clone https://github.com/mahfoud-ma/distributed-rate-limiter.git
cd distributed-rate-limiter

# 2. Configure environment (optional)
cp .env.example .env
# Edit .env with your settings

# 3. Start services
docker-compose up -d

# 4. Verify deployment
curl http://localhost:8000/health

# 5. Check logs
docker-compose logs -f
```

### Stopping Services

```bash
docker-compose down
```

### Updating Deployment

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose up -d --build
```

## Docker Compose with Sentinel (HA)

Best for: Production deployments requiring high availability

### Architecture

- 1 Redis Master
- 2 Redis Replicas
- 3 Redis Sentinels (quorum: 2)
- 1 FastAPI application

### Deployment Steps

```bash
# 1. Configure Sentinel (if needed)
# Edit sentinel.conf to adjust settings

# 2. Start HA setup
docker-compose -f docker-compose.sentinel.yml up -d

# 3. Verify all services are running
docker-compose -f docker-compose.sentinel.yml ps

# Expected output:
# - rate_limiter_api_ha
# - redis_master
# - redis_replica1
# - redis_replica2
# - redis_sentinel1
# - redis_sentinel2
# - redis_sentinel3

# 4. Test failover capability
./scripts/test_failover.sh
```

### Sentinel Configuration

Edit `sentinel.conf` to customize:

```conf
# Quorum: Number of sentinels needed to agree on master failure
sentinel monitor mymaster redis-master 6379 2

# Time to wait before declaring master down (5 seconds)
sentinel down-after-milliseconds mymaster 5000

# Failover timeout
sentinel failover-timeout mymaster 10000
```

### Monitoring Sentinel

```bash
# Connect to Sentinel CLI
docker exec -it redis_sentinel1 redis-cli -p 26379

# Check master status
SENTINEL master mymaster

# List all sentinels
SENTINEL sentinels mymaster

# List all replicas
SENTINEL replicas mymaster
```

## Manual Deployment

Best for: Custom environments, system administrators

### Server Requirements

- Ubuntu 20.04+ / Debian 11+ / RHEL 8+
- Python 3.11+
- Redis 7.0+
- 2GB RAM (minimum)
- 10GB disk space

### Installation Steps

#### 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip redis-server

# RHEL/CentOS
sudo dnf install -y python3.11 python3-pip redis
```

#### 2. Install Application

```bash
# Create application user
sudo useradd -r -s /bin/bash -d /opt/rate-limiter ratelimiter

# Clone repository
sudo -u ratelimiter git clone https://github.com/mahfoud-ma/distributed-rate-limiter.git /opt/rate-limiter
cd /opt/rate-limiter

# Create virtual environment
sudo -u ratelimiter python3.11 -m venv venv
sudo -u ratelimiter venv/bin/pip install -r requirements.txt

# Configure environment
sudo -u ratelimiter cp .env.example .env
sudo -u ratelimiter nano .env  # Edit settings
```

#### 3. Configure Redis

```bash
# Edit Redis configuration
sudo nano /etc/redis/redis.conf

# Recommended settings:
maxmemory 256mb
maxmemory-policy allkeys-lru
save ""  # Disable persistence for rate limiting

# Restart Redis
sudo systemctl restart redis
```

#### 4. Create Systemd Service

```bash
sudo nano /etc/systemd/system/rate-limiter.service
```

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

#### 5. Start Service

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable rate-limiter
sudo systemctl start rate-limiter

# Check status
sudo systemctl status rate-limiter

# View logs
sudo journalctl -u rate-limiter -f
```

#### 6. Configure Nginx (Optional)

```bash
sudo nano /etc/nginx/sites-available/rate-limiter
```

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

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/rate-limiter /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Cloud Deployment

### AWS (Elastic Beanstalk)

```bash
# Install EB CLI
pip install awsebcli

# Initialize EB application
eb init -p docker rate-limiter

# Create environment
eb create rate-limiter-prod

# Deploy
eb deploy
```

### Google Cloud Platform (Cloud Run)

```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/rate-limiter

# Deploy to Cloud Run
gcloud run deploy rate-limiter \
  --image gcr.io/PROJECT_ID/rate-limiter \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### DigitalOcean App Platform

1. Connect GitHub repository
2. Select Dockerfile build
3. Set environment variables
4. Deploy

### Kubernetes

```yaml
# kubernetes/deployment.yaml
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

Apply configuration:

```bash
kubectl apply -f kubernetes/deployment.yaml
```

## Monitoring & Observability

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Redis health
redis-cli ping
```

### Logs

```bash
# Docker Compose
docker-compose logs -f

# Systemd
journalctl -u rate-limiter -f

# Kubernetes
kubectl logs -f deployment/rate-limiter
```

### Metrics (Future Enhancement)

Add Prometheus metrics endpoint:

```python
# app/main.py
from prometheus_client import Counter, Histogram, make_asgi_app

rate_limit_requests = Counter('rate_limit_requests_total', 'Total rate limit checks')
rate_limit_exceeded = Counter('rate_limit_exceeded_total', 'Total rate limits exceeded')

# Mount metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### Alerting

Set up alerts for:

- High rate limit rejection rate (>50%)
- Redis connection failures
- High API latency (>100ms)
- Service downtime

## Security Considerations

### Production Checklist

- [ ] Set `ENVIRONMENT=production` in environment variables
- [ ] Use strong Redis password: `REDIS_PASSWORD=your-secure-password`
- [ ] Enable TLS/SSL for Redis connections
- [ ] Use HTTPS for API (configure reverse proxy)
- [ ] Implement API authentication (JWT, OAuth2)
- [ ] Configure firewall rules (only expose necessary ports)
- [ ] Set up log rotation
- [ ] Regular security updates
- [ ] Backup Redis data (if needed)
- [ ] Monitor for unusual rate limit patterns

### Redis Security

```conf
# redis.conf
requirepass your-secure-password
bind 127.0.0.1
protected-mode yes
```

### Network Security

```bash
# UFW firewall rules
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

## Backup & Recovery

### Redis Backup

```bash
# Manual backup
redis-cli SAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# Restore
sudo systemctl stop redis
cp /backup/redis-backup.rdb /var/lib/redis/dump.rdb
sudo systemctl start redis
```

### Application Backup

```bash
# Backup configuration
tar -czf rate-limiter-config-$(date +%Y%m%d).tar.gz \
  .env \
  docker-compose.yml \
  sentinel.conf
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs api

# Check Redis connectivity
docker-compose exec api python -c "from app.redis_client import get_redis_client; get_redis_client().ping()"
```

### High Memory Usage

```bash
# Check Redis memory
redis-cli INFO memory

# Clear all keys (CAUTION: Only in development!)
redis-cli FLUSHALL
```

### Slow Response Times

```bash
# Check Redis latency
redis-cli --latency

# Monitor slow queries
redis-cli SLOWLOG GET 10
```

## Support

For deployment issues:

1. Check the [README.md](README.md) for common issues
2. Review application logs
3. Open an issue on GitHub
4. Contact support team

---

**Last updated:** 2025-10-24
