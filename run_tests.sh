#!/bin/bash

# Comprehensive Test Suite for Distributed Rate Limiter
# Clean, professional output with visual indicators

# Color codes for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Test configuration
BASE_URL="http://localhost:8000"
PASS_COUNT=0
FAIL_COUNT=0

# Helper functions
print_header() {
    echo ""
    echo "================================================================"
    echo -e "${BOLD}$1${NC}"
    echo "================================================================"
    echo ""
}

print_test() {
    echo -e "${BLUE}TEST $1:${NC} $2"
    echo "----------------------------------------------------------------"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS_COUNT++))
}

print_failure() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAIL_COUNT++))
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Start tests
clear
print_header "DISTRIBUTED RATE LIMITER - COMPREHENSIVE TEST SUITE"

# TEST 1: Health Check
print_test "1" "Health Check"
HEALTH_RESPONSE=$(curl -s $BASE_URL/health)
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
    print_success "Service is healthy"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool
else
    print_failure "Service health check failed"
fi
echo ""

# TEST 2: Root Endpoint Information
print_test "2" "Service Information (Root Endpoint)"
ROOT_RESPONSE=$(curl -s $BASE_URL/)
if echo "$ROOT_RESPONSE" | grep -q '"service"'; then
    print_success "Root endpoint returns service information"
    echo "$ROOT_RESPONSE" | python3 -m json.tool
else
    print_failure "Root endpoint failed"
fi
echo ""

# TEST 3: Successful Request with API Key
print_test "3" "Protected Resource Access (with API Key)"
API_RESPONSE=$(curl -s -X POST $BASE_URL/api/resource \
    -H "X-API-Key: test_user_001" \
    -H "Content-Type: application/json" \
    -d '{"action": "process", "data": {"key": "value"}}')
if echo "$API_RESPONSE" | grep -q '"message":"Request successful"'; then
    print_success "Request processed successfully"
    echo "$API_RESPONSE" | python3 -m json.tool
else
    print_failure "Request failed"
fi
echo ""

# TEST 4: Empty JSON Handling
print_test "4" "Empty JSON Body Handling"
print_info "Testing with empty JSON object: {}"
EMPTY_CODES=""
for i in {1..3}; do
    CODE=$(curl -s -X POST $BASE_URL/api/resource \
        -H "X-API-Key: test_empty_$i" \
        -H "Content-Type: application/json" \
        -d '{}' \
        -o /dev/null -w "%{http_code}")
    EMPTY_CODES="$EMPTY_CODES $CODE"
done
echo "Response codes: $EMPTY_CODES"
if [[ "$EMPTY_CODES" =~ "200 200 200" ]]; then
    print_success "All empty JSON requests succeeded (200 OK)"
else
    print_failure "Empty JSON handling failed - got: $EMPTY_CODES"
fi
echo ""

# TEST 5: No Body Handling
print_test "5" "No Request Body Handling"
print_info "Testing without request body"
NO_BODY_CODES=""
for i in {1..3}; do
    CODE=$(curl -s -X POST $BASE_URL/api/resource \
        -H "X-API-Key: test_nobody_$i" \
        -o /dev/null -w "%{http_code}")
    NO_BODY_CODES="$NO_BODY_CODES $CODE"
done
echo "Response codes: $NO_BODY_CODES"
if [[ "$NO_BODY_CODES" =~ "200 200 200" ]]; then
    print_success "All no-body requests succeeded (200 OK)"
else
    print_failure "No-body handling failed - got: $NO_BODY_CODES"
fi
echo ""

# TEST 6: Rate Limiting in Action
print_test "6" "Rate Limiting (20 requests/minute)"
print_info "Sending 25 requests to test rate limit..."
RATE_CODES=""
for i in {1..25}; do
    CODE=$(curl -s -X POST $BASE_URL/api/resource \
        -H "X-API-Key: rate_test_user" \
        -o /dev/null -w "%{http_code}")
    RATE_CODES="$RATE_CODES$CODE "
done
echo "Response codes:"
echo "$RATE_CODES"

# Count 200s and 429s
COUNT_200=$(echo "$RATE_CODES" | grep -o "200" | wc -l)
COUNT_429=$(echo "$RATE_CODES" | grep -o "429" | wc -l)

echo ""
echo "Summary: $COUNT_200 successful (200), $COUNT_429 rate-limited (429)"

if [ "$COUNT_200" -eq 20 ] && [ "$COUNT_429" -eq 5 ]; then
    print_success "Rate limiting working correctly (20 allowed, 5 blocked)"
else
    print_failure "Rate limiting not working as expected"
fi
echo ""

# TEST 7: Rate Limit Status Endpoint
print_test "7" "Rate Limit Status Check"
STATUS_RESPONSE=$(curl -s $BASE_URL/rate-limit/status -H "X-API-Key: rate_test_user")
if echo "$STATUS_RESPONSE" | grep -q '"identifier"'; then
    print_success "Status endpoint returns proper format"
    echo "$STATUS_RESPONSE" | python3 -m json.tool
else
    print_failure "Status endpoint failed"
fi
echo ""

# TEST 8: Rate Limit Headers
print_test "8" "RFC 6585 Rate Limit Headers"
print_info "Checking response headers for rate limit information"
HEADERS=$(curl -s -i -X POST $BASE_URL/api/resource -H "X-API-Key: header_test" 2>&1)
echo "$HEADERS" | grep -iE "(HTTP/|x-ratelimit-)"
if echo "$HEADERS" | grep -qi "x-ratelimit-limit"; then
    print_success "Rate limit headers present"
else
    print_failure "Rate limit headers missing"
fi
echo ""

# TEST 9: IP-Based Rate Limiting (No API Key)
print_test "9" "IP-Based Rate Limiting (Fallback)"
print_info "Sending requests without X-API-Key header (falls back to IP-based limiting)"
IP_CODES=""
for i in {1..25}; do
    CODE=$(curl -s -X POST $BASE_URL/api/resource \
        -o /dev/null -w "%{http_code}")
    IP_CODES="$IP_CODES$CODE "
done
echo "Response codes:"
echo "$IP_CODES"

COUNT_200_IP=$(echo "$IP_CODES" | grep -o "200" | wc -l)
COUNT_429_IP=$(echo "$IP_CODES" | grep -o "429" | wc -l)

echo ""
echo "Summary: $COUNT_200_IP successful (200), $COUNT_429_IP rate-limited (429)"

if [ "$COUNT_429_IP" -gt 0 ]; then
    print_success "IP-based rate limiting is active"
else
    print_failure "IP-based rate limiting not working"
fi
echo ""

# TEST 10: Redis Connectivity
print_test "10" "Redis Backend Verification"
REDIS_CHECK=$(curl -s $BASE_URL/health | python3 -c "import sys, json; print(json.load(sys.stdin).get('redis', 'unknown'))")
if [ "$REDIS_CHECK" = "connected" ]; then
    print_success "Redis is connected and operational"
else
    print_failure "Redis connection issue: $REDIS_CHECK"
fi
echo ""

# TEST 11: Status Endpoint Doesn't Consume Requests
print_test "11" "Status Endpoint Non-Consumption Verification"
print_info "Verifying status checks don't count against rate limit"

# Fresh user
BEFORE=$(curl -s $BASE_URL/rate-limit/status -H "X-API-Key: fresh_test_user" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['current_count'])")
echo "Before any requests: count=$BEFORE"

# Make actual request
curl -s -X POST $BASE_URL/api/resource -H "X-API-Key: fresh_test_user" -o /dev/null

AFTER=$(curl -s $BASE_URL/rate-limit/status -H "X-API-Key: fresh_test_user" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['current_count'])")
echo "After 1 request: count=$AFTER"

# Check status multiple times
curl -s $BASE_URL/rate-limit/status -H "X-API-Key: fresh_test_user" -o /dev/null
curl -s $BASE_URL/rate-limit/status -H "X-API-Key: fresh_test_user" -o /dev/null
AFTER_STATUS=$(curl -s $BASE_URL/rate-limit/status -H "X-API-Key: fresh_test_user" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['current_count'])")
echo "After 3 status checks: count=$AFTER_STATUS"

if [ "$AFTER" = "$AFTER_STATUS" ]; then
    print_success "Status endpoint does not consume requests"
else
    print_failure "Status endpoint incorrectly consuming requests"
fi
echo ""

# TEST 12: Partial JSON Handling
print_test "12" "Partial JSON Body Handling"
print_info "Testing with partial JSON: {\"action\":\"custom\"}"
PARTIAL_RESPONSE=$(curl -s -X POST $BASE_URL/api/resource \
    -H "X-API-Key: partial_test" \
    -H "Content-Type: application/json" \
    -d '{"action":"custom"}')
if echo "$PARTIAL_RESPONSE" | grep -q '"action":"custom"'; then
    print_success "Partial JSON handled correctly"
    echo "$PARTIAL_RESPONSE" | python3 -m json.tool
else
    print_failure "Partial JSON handling failed"
fi
echo ""

# Final Summary
print_header "TEST SUMMARY"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo -e "${BOLD}Total Tests:${NC} $TOTAL"
echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
echo -e "${RED}Failed:${NC} $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}${BOLD}ALL TESTS PASSED!${NC}"
else
    echo -e "${YELLOW}${BOLD}SOME TESTS FAILED - PLEASE REVIEW${NC}"
fi

echo ""
echo "================================================================"
echo -e "${BOLD}Additional Resources:${NC}"
echo "----------------------------------------------------------------"
echo "Interactive API Documentation: $BASE_URL/docs"
echo "ReDoc Documentation: $BASE_URL/redoc"
echo "Health Check: $BASE_URL/health"
echo "Rate Limit Status: $BASE_URL/rate-limit/status"
echo "================================================================"
echo ""
