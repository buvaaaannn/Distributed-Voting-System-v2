"""Load testing script for the voting system.

This script provides both Locust-based and custom async load testing
capabilities to measure system performance under high load.

Usage:
    # Using Locust (recommended for web UI and distributed testing)
    locust -f load_test.py --host=http://localhost:8000

    # Using custom async script
    python load_test.py --votes 10000 --rate 100 --duration 60

Performance Targets:
    - Throughput: 1000 votes/second sustained
    - Latency: p95 < 100ms for vote submission
    - Error Rate: < 0.1%
    - Success Rate: > 99.9%
"""

import argparse
import asyncio
import hashlib
import json
import random
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import httpx
import string

# Try to import Locust (optional)
try:
    from locust import HttpUser, TaskSet, task, between, events
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    print("⚠️  Locust not installed. Only custom async load test available.")
    print("   Install with: pip install locust")


# ============================================================================
# LOCUST LOAD TESTS (Web UI + Distributed Testing)
# ============================================================================

if LOCUST_AVAILABLE:
    class VotingTaskSet(TaskSet):
        """Task set for simulating voter behavior."""

        def on_start(self):
            """Initialize on user start."""
            self.law_ids = ["L2025-001", "L2025-002", "L2025-003"]
            self.vote_count = 0

        def generate_unique_vote(self) -> dict:
            """Generate a unique vote payload."""
            # Generate unique NAS and code
            timestamp = int(time.time() * 1000000)
            random_suffix = random.randint(0, 999999)
            unique_id = f"{timestamp}{random_suffix}"

            nas = f"{hash(unique_id) % 1000000000:09d}"
            code = f"LOAD{random.randint(0, 999999):06d}"
            law_id = random.choice(self.law_ids)
            vote = random.choice(["oui", "non"])

            return {
                "nas": nas,
                "code": code,
                "law_id": law_id,
                "vote": vote
            }

        @task(10)
        def submit_vote(self):
            """Submit a vote (primary task, weight=10)."""
            vote = self.generate_unique_vote()

            with self.client.post(
                "/api/v1/vote",
                json=vote,
                catch_response=True,
                name="/api/v1/vote"
            ) as response:
                if response.status_code in [200, 202]:
                    response.success()
                    self.vote_count += 1
                else:
                    response.failure(f"Got status {response.status_code}")

        @task(2)
        def get_results(self):
            """Query results (secondary task, weight=2)."""
            law_id = random.choice(self.law_ids)

            with self.client.get(
                f"/api/v1/results/{law_id}",
                catch_response=True,
                name="/api/v1/results/{law_id}"
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Got status {response.status_code}")

        @task(1)
        def health_check(self):
            """Check API health (occasional task, weight=1)."""
            with self.client.get(
                "/api/v1/health",
                catch_response=True,
                name="/api/v1/health"
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Got status {response.status_code}")

    class VotingUser(HttpUser):
        """Simulated user for load testing."""
        tasks = [VotingTaskSet]
        wait_time = between(0.1, 2.0)  # Wait 0.1-2 seconds between tasks

        # Connection pool settings for better performance
        pool_manager_kwargs = {
            "maxsize": 1000,
            "max_retries": 3,
        }


    # Event handlers for custom metrics
    @events.test_start.add_listener
    def on_test_start(environment, **kwargs):
        """Called when test starts."""
        print("\n" + "="*70)
        print("🚀 Starting Voting System Load Test")
        print("="*70)
        print(f"Target: {environment.host}")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")


    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """Called when test stops."""
        print("\n" + "="*70)
        print("🏁 Load Test Completed")
        print("="*70)
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n📊 Check Locust web UI for detailed results")
        print("="*70 + "\n")


# ============================================================================
# CUSTOM ASYNC LOAD TEST (Programmatic Testing)
# ============================================================================

class LoadTestMetrics:
    """Collect and report load test metrics."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.latencies: List[float] = []
        self.errors: Dict[str, int] = defaultdict(int)
        self.start_time = None
        self.end_time = None

    def record_request(self, latency: float, success: bool, error: str = None):
        """Record a request."""
        self.total_requests += 1
        self.latencies.append(latency)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error:
                self.errors[error] += 1

    def calculate_percentile(self, percentile: float) -> float:
        """Calculate latency percentile."""
        if not self.latencies:
            return 0.0

        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * (percentile / 100.0))
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]

    def generate_report(self) -> str:
        """Generate test report."""
        duration = self.end_time - self.start_time if self.end_time else 0

        report = [
            "\n" + "="*70,
            "📊 LOAD TEST RESULTS",
            "="*70,
            f"\n⏱️  Duration: {duration:.2f} seconds",
            f"📈 Total Requests: {self.total_requests:,}",
            f"✅ Successful: {self.successful_requests:,} ({self.success_rate:.2f}%)",
            f"❌ Failed: {self.failed_requests:,} ({self.failure_rate:.2f}%)",
            f"\n🚀 Throughput:",
            f"   - Requests/sec: {self.requests_per_second:.2f}",
            f"   - Votes/sec: {self.requests_per_second:.2f}",
            f"\n⏲️  Latency (ms):",
            f"   - Min: {self.min_latency * 1000:.2f}",
            f"   - Max: {self.max_latency * 1000:.2f}",
            f"   - Mean: {self.mean_latency * 1000:.2f}",
            f"   - Median (p50): {self.calculate_percentile(50) * 1000:.2f}",
            f"   - p95: {self.calculate_percentile(95) * 1000:.2f}",
            f"   - p99: {self.calculate_percentile(99) * 1000:.2f}",
        ]

        if self.errors:
            report.append(f"\n❗ Errors:")
            for error, count in sorted(self.errors.items(), key=lambda x: -x[1]):
                report.append(f"   - {error}: {count}")

        # Performance assessment
        report.append(f"\n🎯 Performance Assessment:")
        if self.requests_per_second >= 1000:
            report.append("   ✅ Throughput: EXCELLENT (≥1000 req/s)")
        elif self.requests_per_second >= 500:
            report.append("   ✅ Throughput: GOOD (≥500 req/s)")
        else:
            report.append("   ⚠️  Throughput: NEEDS IMPROVEMENT (<500 req/s)")

        p95_latency_ms = self.calculate_percentile(95) * 1000
        if p95_latency_ms < 100:
            report.append("   ✅ Latency (p95): EXCELLENT (<100ms)")
        elif p95_latency_ms < 200:
            report.append("   ✅ Latency (p95): GOOD (<200ms)")
        else:
            report.append("   ⚠️  Latency (p95): NEEDS IMPROVEMENT (≥200ms)")

        if self.success_rate >= 99.9:
            report.append("   ✅ Success Rate: EXCELLENT (≥99.9%)")
        elif self.success_rate >= 99.0:
            report.append("   ✅ Success Rate: GOOD (≥99%)")
        else:
            report.append("   ⚠️  Success Rate: NEEDS IMPROVEMENT (<99%)")

        report.append("="*70 + "\n")

        return "\n".join(report)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate

    @property
    def min_latency(self) -> float:
        """Get minimum latency."""
        return min(self.latencies) if self.latencies else 0.0

    @property
    def max_latency(self) -> float:
        """Get maximum latency."""
        return max(self.latencies) if self.latencies else 0.0

    @property
    def mean_latency(self) -> float:
        """Get mean latency."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second."""
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 1
        return self.total_requests / duration if duration > 0 else 0.0


async def submit_vote_async(
    client: httpx.AsyncClient,
    vote: dict,
    metrics: LoadTestMetrics
):
    """Submit a single vote and record metrics."""
    start_time = time.time()

    try:
        response = await client.post("/api/v1/vote", json=vote, timeout=10.0)
        latency = time.time() - start_time

        success = response.status_code in [200, 202]
        error = None if success else f"HTTP {response.status_code}"

        metrics.record_request(latency, success, error)

    except Exception as e:
        latency = time.time() - start_time
        metrics.record_request(latency, False, str(type(e).__name__))


def load_test_votes(filename: str = 'test_votes.txt'):
    """Load pre-generated test votes from file."""
    votes = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                nas, code, law_id, vote = line.strip().split('|')
                votes.append({
                    'nas': nas,
                    'code': code,
                    'law_id': law_id,
                    'vote': vote
                })
        print(f"✅ Loaded {len(votes):,} pre-generated votes with valid hashes\n")
        return votes
    except FileNotFoundError:
        print(f"⚠️  File {filename} not found. Run scripts/preload_test_hashes.py first!")
        return None

async def generate_load(
    base_url: str,
    total_votes: int,
    target_rate: int,
    duration: int = None
):
    """Generate load by submitting votes at target rate.

    Args:
        base_url: API base URL
        total_votes: Total number of votes to submit
        target_rate: Target requests per second
        duration: Maximum test duration in seconds (optional)
    """
    # Load pre-generated votes
    preloaded_votes = load_test_votes()
    if not preloaded_votes:
        print("ERROR: Cannot run test without valid votes!")
        return

    metrics = LoadTestMetrics()
    metrics.start_time = time.time()

    print(f"\n🚀 Starting Custom Async Load Test WITH VALID VOTES")
    print(f"   Target: {base_url}")
    print(f"   Total Votes: {min(total_votes, len(preloaded_votes)):,}")
    print(f"   Target Rate: {target_rate} votes/sec")
    if duration:
        print(f"   Max Duration: {duration} seconds")
    print("\n   Press Ctrl+C to stop...\n")

    total_votes = min(total_votes, len(preloaded_votes))

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Calculate batch size and delay
        batch_size = min(target_rate, 100)  # Process in batches
        batch_delay = batch_size / target_rate  # Delay between batches

        vote_count = 0
        start_time = time.time()

        try:
            while vote_count < total_votes:
                # Check duration limit
                if duration and (time.time() - start_time) >= duration:
                    print(f"\n⏱️  Duration limit reached ({duration}s)")
                    break

                # Get batch of votes from pre-loaded list
                batch_votes = []
                for i in range(batch_size):
                    if vote_count >= total_votes:
                        break

                    # Use pre-loaded vote (with valid hash in Redis)
                    vote = preloaded_votes[vote_count]
                    batch_votes.append(vote)
                    vote_count += 1

                # Submit batch concurrently
                tasks = [
                    submit_vote_async(client, vote, metrics)
                    for vote in batch_votes
                ]
                await asyncio.gather(*tasks)

                # Progress update
                if vote_count % (target_rate * 5) == 0:  # Every 5 seconds
                    elapsed = time.time() - start_time
                    current_rate = vote_count / elapsed if elapsed > 0 else 0
                    print(f"   Progress: {vote_count:,}/{total_votes:,} votes "
                          f"({current_rate:.1f} votes/sec)")

                # Rate limiting delay
                await asyncio.sleep(batch_delay)

        except KeyboardInterrupt:
            print(f"\n\n⚠️  Test interrupted by user")

    metrics.end_time = time.time()

    # Print report
    print(metrics.generate_report())

    # Save detailed results to JSON
    save_results(metrics, total_votes, target_rate)


def save_results(metrics: LoadTestMetrics, total_votes: int, target_rate: int):
    """Save test results to JSON file."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_config": {
            "total_votes": total_votes,
            "target_rate": target_rate,
        },
        "metrics": {
            "duration_seconds": metrics.end_time - metrics.start_time,
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate_percent": metrics.success_rate,
            "requests_per_second": metrics.requests_per_second,
            "latency_ms": {
                "min": metrics.min_latency * 1000,
                "max": metrics.max_latency * 1000,
                "mean": metrics.mean_latency * 1000,
                "p50": metrics.calculate_percentile(50) * 1000,
                "p95": metrics.calculate_percentile(95) * 1000,
                "p99": metrics.calculate_percentile(99) * 1000,
            },
            "errors": dict(metrics.errors)
        }
    }

    filename = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"📁 Detailed results saved to: {filename}\n")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Load test the voting system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Custom async load test
  python load_test.py --votes 10000 --rate 100

  # Test for specific duration
  python load_test.py --votes 100000 --rate 500 --duration 60

  # Using Locust (if installed)
  locust -f load_test.py --host=http://localhost:8000 --users 100 --spawn-rate 10
        """
    )

    parser.add_argument(
        '--votes',
        type=int,
        default=1000,
        help='Total number of votes to submit (default: 1000)'
    )

    parser.add_argument(
        '--rate',
        type=int,
        default=100,
        help='Target votes per second (default: 100)'
    )

    parser.add_argument(
        '--duration',
        type=int,
        default=None,
        help='Maximum test duration in seconds (optional)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='http://localhost:8000',
        help='API host URL (default: http://localhost:8000)'
    )

    args = parser.parse_args()

    # Run custom async load test
    asyncio.run(generate_load(
        base_url=args.host,
        total_votes=args.votes,
        target_rate=args.rate,
        duration=args.duration
    ))


if __name__ == "__main__":
    main()
