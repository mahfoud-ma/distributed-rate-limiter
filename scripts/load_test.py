#!/usr/bin/env python3
"""Load testing script for the rate limiting service.

This script sends concurrent requests to the API and measures performance metrics.

Usage:
    python scripts/load_test.py --requests 1000 --concurrent 50 --url http://localhost:8000
"""

import asyncio
import aiohttp
import argparse
import time
from typing import List, Dict
from datetime import datetime
import statistics


class LoadTestResult:
    """Container for load test results."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limited_requests = 0
        self.latencies: List[float] = []
        self.start_time = None
        self.end_time = None

    def add_result(self, status_code: int, latency: float):
        """Add a request result."""
        self.total_requests += 1
        self.latencies.append(latency)

        if status_code == 200:
            self.successful_requests += 1
        elif status_code == 429:
            self.rate_limited_requests += 1
        else:
            self.failed_requests += 1

    def print_summary(self):
        """Print test results summary."""
        duration = self.end_time - self.start_time

        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)

        print(f"\nTest Configuration:")
        print(f"  Total requests:     {self.total_requests}")
        print(f"  Duration:           {duration:.2f}s")
        print(f"  Throughput:         {self.total_requests / duration:.2f} req/s")

        print(f"\nRequest Results:")
        success_pct = (self.successful_requests / self.total_requests) * 100
        rate_limited_pct = (self.rate_limited_requests / self.total_requests) * 100
        failed_pct = (self.failed_requests / self.total_requests) * 100

        print(f"  ✓ Success:          {self.successful_requests} ({success_pct:.1f}%)")
        print(f"  ⚠ Rate limited:     {self.rate_limited_requests} ({rate_limited_pct:.1f}%)")
        print(f"  ✗ Failed:           {self.failed_requests} ({failed_pct:.1f}%)")

        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            print(f"\nLatency Metrics (milliseconds):")
            print(f"  Average:            {statistics.mean(self.latencies) * 1000:.2f}ms")
            print(f"  Median (P50):       {statistics.median(self.latencies) * 1000:.2f}ms")
            print(f"  P95:                {sorted_latencies[int(len(sorted_latencies) * 0.95)] * 1000:.2f}ms")
            print(f"  P99:                {sorted_latencies[int(len(sorted_latencies) * 0.99)] * 1000:.2f}ms")
            print(f"  Min:                {min(self.latencies) * 1000:.2f}ms")
            print(f"  Max:                {max(self.latencies) * 1000:.2f}ms")

        print("\n" + "=" * 60 + "\n")


async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    user_id: str,
    result: LoadTestResult,
) -> None:
    """Make a single HTTP request and record the result.

    Args:
        session: aiohttp session
        url: API endpoint URL
        user_id: User identifier for the request
        result: LoadTestResult to store the result
    """
    headers = {
        "X-API-Key": user_id,
        "Content-Type": "application/json",
    }
    data = {"action": "load_test", "data": {"timestamp": datetime.now().isoformat()}}

    start_time = time.time()

    try:
        async with session.post(url, json=data, headers=headers) as response:
            await response.text()  # Consume response body
            latency = time.time() - start_time
            result.add_result(response.status, latency)

    except Exception as e:
        latency = time.time() - start_time
        result.add_result(0, latency)
        print(f"Request failed: {e}")


async def run_load_test(
    url: str,
    total_requests: int,
    concurrent_requests: int,
    unique_users: int,
) -> LoadTestResult:
    """Run the load test with specified parameters.

    Args:
        url: API endpoint URL
        total_requests: Total number of requests to send
        concurrent_requests: Number of concurrent requests
        unique_users: Number of unique user IDs to simulate

    Returns:
        LoadTestResult with test results
    """
    result = LoadTestResult()
    result.start_time = time.time()

    # Create aiohttp session with connection pooling
    connector = aiohttp.TCPConnector(limit=concurrent_requests)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Generate user IDs
        user_ids = [f"loadtest_user_{i % unique_users}" for i in range(total_requests)]

        # Create tasks
        tasks = []
        for i, user_id in enumerate(user_ids):
            task = make_request(session, url, user_id, result)
            tasks.append(task)

            # Limit concurrent requests
            if len(tasks) >= concurrent_requests or i == len(user_ids) - 1:
                await asyncio.gather(*tasks)
                tasks = []

                # Progress indicator
                if (i + 1) % 100 == 0:
                    print(f"Progress: {i + 1}/{total_requests} requests sent...")

    result.end_time = time.time()
    return result


def main():
    """Main entry point for the load testing script."""
    parser = argparse.ArgumentParser(
        description="Load test the distributed rate limiting service"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="Total number of requests to send (default: 1000)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=50,
        help="Number of concurrent requests (default: 50)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of unique users to simulate (default: 10)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000/api/resource",
        help="API endpoint URL (default: http://localhost:8000/api/resource)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("DISTRIBUTED RATE LIMITER - LOAD TEST")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Target URL:         {args.url}")
    print(f"  Total requests:     {args.requests}")
    print(f"  Concurrent:         {args.concurrent}")
    print(f"  Unique users:       {args.users}")
    print(f"\nStarting load test...\n")

    # Run the load test
    result = asyncio.run(
        run_load_test(
            url=args.url,
            total_requests=args.requests,
            concurrent_requests=args.concurrent,
            unique_users=args.users,
        )
    )

    # Print results
    result.print_summary()


if __name__ == "__main__":
    main()
