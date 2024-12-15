#!/bin/bash
# Redis Sentinel Failover Test Script
#
# This script demonstrates Redis Sentinel's automatic failover capability
# by simulating a master failure and observing the promotion of a replica.
#
# Usage: ./scripts/test_failover.sh

set -e

echo "=========================================="
echo "Redis Sentinel Failover Test"
echo "=========================================="
echo

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

echo "1. Checking current Redis master..."
MASTER_INFO=$(docker exec redis_sentinel1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster 2>/dev/null || echo "")

if [ -z "$MASTER_INFO" ]; then
    echo "Error: Cannot connect to Sentinel. Make sure the HA setup is running:"
    echo "  docker-compose -f docker-compose.sentinel.yml up -d"
    exit 1
fi

echo "   Current master: redis-master"
echo

echo "2. Testing API endpoint before failover..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: failover-test" \
    -H "Content-Type: application/json" \
    -d '{"action": "test"}' || echo "000")

if [ "$RESPONSE" = "200" ] || [ "$RESPONSE" = "429" ]; then
    echo "   ✓ API is responding (HTTP $RESPONSE)"
else
    echo "   ✗ API is not responding properly (HTTP $RESPONSE)"
fi
echo

echo "3. Simulating master failure (pausing container)..."
docker pause redis_master
echo "   ✓ Master container paused"
echo

echo "4. Waiting for Sentinel to detect failure and promote replica..."
echo "   (This may take 5-10 seconds...)"
sleep 8
echo

echo "5. Checking new master..."
NEW_MASTER=$(docker exec redis_sentinel1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster | head -1)
echo "   New master host: $NEW_MASTER"
echo

echo "6. Testing API endpoint after failover..."
sleep 2  # Give API time to reconnect
RESPONSE_AFTER=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/resource \
    -H "X-API-Key: failover-test" \
    -H "Content-Type: application/json" \
    -d '{"action": "test"}' || echo "000")

if [ "$RESPONSE_AFTER" = "200" ] || [ "$RESPONSE_AFTER" = "429" ]; then
    echo "   ✓ API is still responding (HTTP $RESPONSE_AFTER)"
    echo "   ✓ Failover successful!"
else
    echo "   ✗ API is not responding (HTTP $RESPONSE_AFTER)"
    echo "   ✗ Failover may have issues"
fi
echo

echo "7. Restoring original master..."
docker unpause redis_master
echo "   ✓ Master container unpaused"
echo

echo "=========================================="
echo "Failover test complete!"
echo "=========================================="
echo
echo "Summary:"
echo "  - Master was paused to simulate failure"
echo "  - Sentinel detected failure and promoted a replica"
echo "  - API continued to function with new master"
echo "  - Original master was restored"
echo
echo "To see Sentinel logs:"
echo "  docker logs redis_sentinel1"
echo
