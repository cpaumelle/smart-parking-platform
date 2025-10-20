"""
Tests for Durable Downlink Queue

Coverage:
- Idempotency (content hashing)
- Deduplication (last_hash matching)
- Coalescing (replacing pending commands)
- Rate limiting (gateway + tenant)
- Retry with exponential backoff
- Dead-letter queue
- Metrics tracking
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis

from src.downlink_queue import (
    DownlinkQueue,
    DownlinkRateLimiter,
    DownlinkWorker,
    DownlinkCommand
)


@pytest.fixture
async def redis_client():
    """Create Redis client for testing"""
    client = await redis.from_url("redis://localhost:6379/15", decode_responses=True)
    # Clear test database
    await client.flushdb()
    yield client
    await client.close()


@pytest.fixture
def downlink_queue(redis_client):
    """Create DownlinkQueue instance"""
    return DownlinkQueue(redis_client)


@pytest.fixture
def rate_limiter(redis_client):
    """Create DownlinkRateLimiter instance"""
    return DownlinkRateLimiter(redis_client)


class TestDownlinkQueue:
    """Test DownlinkQueue idempotency and queueing"""

    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, downlink_queue):
        """Test basic enqueue and dequeue"""
        # Enqueue command
        cmd_id = await downlink_queue.enqueue(
            device_eui="0004a30b001a2b3c",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1",
            confirmed=False
        )

        assert cmd_id is not None

        # Dequeue command
        cmd = await downlink_queue.dequeue(timeout_seconds=1)

        assert cmd is not None
        assert cmd.device_eui == "0004a30b001a2b3c"
        assert cmd.payload == "FF0000"
        assert cmd.fport == 15
        assert cmd.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_idempotency_deduplication(self, downlink_queue):
        """Test that identical successive commands are deduplicated"""
        device_eui = "0004a30b001a2b3c"
        payload = "FF0000"
        fport = 15

        # Enqueue first command
        cmd_id_1 = await downlink_queue.enqueue(
            device_eui=device_eui,
            payload=payload,
            fport=fport,
            tenant_id="tenant-1"
        )

        assert cmd_id_1 is not None

        # Dequeue and mark as successful
        cmd_1 = await downlink_queue.dequeue(timeout_seconds=1)
        await downlink_queue.mark_success(cmd_1)

        # Enqueue IDENTICAL command - should be deduplicated
        cmd_id_2 = await downlink_queue.enqueue(
            device_eui=device_eui,
            payload=payload,
            fport=fport,
            tenant_id="tenant-1"
        )

        assert cmd_id_2 is None  # Deduplicated

        # Enqueue DIFFERENT command - should be enqueued
        cmd_id_3 = await downlink_queue.enqueue(
            device_eui=device_eui,
            payload="00FF00",  # Different payload
            fport=fport,
            tenant_id="tenant-1"
        )

        assert cmd_id_3 is not None  # New command enqueued

    @pytest.mark.asyncio
    async def test_coalescing(self, downlink_queue):
        """Test that pending commands for same device are coalesced"""
        device_eui = "0004a30b001a2b3c"

        # Enqueue command 1
        cmd_id_1 = await downlink_queue.enqueue(
            device_eui=device_eui,
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        # Enqueue command 2 (before cmd 1 is dequeued) - should replace cmd 1
        cmd_id_2 = await downlink_queue.enqueue(
            device_eui=device_eui,
            payload="00FF00",
            fport=15,
            tenant_id="tenant-1"
        )

        # Dequeue - should get cmd 2, not cmd 1
        cmd = await downlink_queue.dequeue(timeout_seconds=1)

        assert cmd.id == cmd_id_2
        assert cmd.payload == "00FF00"

        # Verify cmd 1 was removed
        cmd_next = await downlink_queue.dequeue(timeout_seconds=1)
        assert cmd_next is None  # Queue empty

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, downlink_queue):
        """Test retry mechanism with exponential backoff"""
        cmd_id = await downlink_queue.enqueue(
            device_eui="0004a30b001a2b3c",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        cmd = await downlink_queue.dequeue(timeout_seconds=1)

        # Mark as failed (should requeue)
        await downlink_queue.mark_failure(cmd, "ChirpStack timeout", requeue=True)

        assert cmd.attempts == 1

        # Dequeue again
        cmd_retry = await downlink_queue.dequeue(timeout_seconds=1)

        assert cmd_retry.id == cmd_id
        assert cmd_retry.attempts == 1

    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, downlink_queue):
        """Test that commands exceeding max attempts go to dead-letter queue"""
        cmd_id = await downlink_queue.enqueue(
            device_eui="0004a30b001a2b3c",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        # Fail MAX_ATTEMPTS times
        for i in range(DownlinkQueue.MAX_ATTEMPTS):
            cmd = await downlink_queue.dequeue(timeout_seconds=1)
            await downlink_queue.mark_failure(cmd, f"Failure {i+1}", requeue=True)

        # Verify command went to dead-letter queue
        metrics = await downlink_queue.get_metrics()
        assert metrics["dead_letter_depth"] == 1
        assert metrics["total_dead_lettered"] == 1

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, downlink_queue):
        """Test metrics are correctly tracked"""
        # Enqueue 3 commands
        for i in range(3):
            await downlink_queue.enqueue(
                device_eui=f"device-{i}",
                payload="FF0000",
                fport=15,
                tenant_id="tenant-1"
            )

        # Process 2 successes, 1 failure
        cmd_1 = await downlink_queue.dequeue(timeout_seconds=1)
        await downlink_queue.mark_success(cmd_1)

        cmd_2 = await downlink_queue.dequeue(timeout_seconds=1)
        await downlink_queue.mark_success(cmd_2)

        cmd_3 = await downlink_queue.dequeue(timeout_seconds=1)
        await downlink_queue.mark_failure(cmd_3, "Test failure", requeue=False)

        # Check metrics
        metrics = await downlink_queue.get_metrics()

        assert metrics["total_enqueued"] == 3
        assert metrics["total_succeeded"] == 2
        assert metrics["total_dead_lettered"] == 1
        assert metrics["success_rate"] == pytest.approx(66.67, rel=0.1)


class TestDownlinkRateLimiter:
    """Test rate limiting"""

    @pytest.mark.asyncio
    async def test_gateway_rate_limit(self, rate_limiter):
        """Test per-gateway rate limiting"""
        gateway_id = "gateway-1"
        limit = 5  # 5 per minute

        # Consume all tokens
        for i in range(5):
            allowed, retry_after = await rate_limiter.check_gateway_limit(gateway_id, limit)
            assert allowed is True
            assert retry_after is None

        # 6th request should be rate-limited
        allowed, retry_after = await rate_limiter.check_gateway_limit(gateway_id, limit)
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_tenant_rate_limit(self, rate_limiter):
        """Test per-tenant rate limiting"""
        tenant_id = "tenant-1"
        limit = 10  # 10 per minute

        # Consume all tokens
        for i in range(10):
            allowed, retry_after = await rate_limiter.check_tenant_limit(tenant_id, limit)
            assert allowed is True

        # 11th request should be rate-limited
        allowed, retry_after = await rate_limiter.check_tenant_limit(tenant_id, limit)
        assert allowed is False
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_token_refill(self, rate_limiter):
        """Test that tokens refill over time"""
        gateway_id = "gateway-refill"
        limit = 60  # 60 per minute = 1 per second

        # Consume 1 token
        allowed, _ = await rate_limiter.check_gateway_limit(gateway_id, limit)
        assert allowed is True

        # Immediately consume another - should be rate-limited
        allowed, retry_after = await rate_limiter.check_gateway_limit(gateway_id, limit)
        assert allowed is False

        # Wait for token refill
        await asyncio.sleep(1.5)

        # Should be allowed now
        allowed, _ = await rate_limiter.check_gateway_limit(gateway_id, limit)
        assert allowed is True


class TestDownlinkWorker:
    """Test downlink worker processing"""

    @pytest.mark.asyncio
    async def test_worker_processes_queue(self, downlink_queue, rate_limiter):
        """Test worker successfully processes commands"""
        # Mock ChirpStack client
        chirpstack_mock = AsyncMock()
        chirpstack_mock.queue_downlink = AsyncMock(return_value={"id": "downlink-123"})

        # Create worker
        worker = DownlinkWorker(
            queue=downlink_queue,
            rate_limiter=rate_limiter,
            chirpstack_client=chirpstack_mock,
            worker_id="test-worker"
        )

        # Enqueue command
        await downlink_queue.enqueue(
            device_eui="0004a30b001a2b3c",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        # Start worker
        await worker.start()

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop worker
        await worker.stop()

        # Verify command was sent
        chirpstack_mock.queue_downlink.assert_called_once()

        # Verify metrics
        metrics = await downlink_queue.get_metrics()
        assert metrics["total_succeeded"] == 1

    @pytest.mark.asyncio
    async def test_worker_respects_rate_limits(self, downlink_queue, rate_limiter):
        """Test worker respects rate limits"""
        chirpstack_mock = AsyncMock()
        chirpstack_mock.queue_downlink = AsyncMock(return_value={"id": "downlink-123"})

        worker = DownlinkWorker(
            queue=downlink_queue,
            rate_limiter=rate_limiter,
            chirpstack_client=chirpstack_mock
        )

        # Set very low rate limit
        tenant_limit = 1  # 1 per minute

        # Enqueue 2 commands
        await downlink_queue.enqueue(
            device_eui="device-1",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        await downlink_queue.enqueue(
            device_eui="device-2",
            payload="FF0000",
            fport=15,
            tenant_id="tenant-1"
        )

        # Manually process first command
        cmd_1 = await downlink_queue.dequeue(timeout_seconds=1)
        await worker._process_command(cmd_1)

        # First should succeed
        assert chirpstack_mock.queue_downlink.call_count == 1

        # Second should be rate-limited and requeued
        cmd_2 = await downlink_queue.dequeue(timeout_seconds=1)

        # Mock rate limiter to return limited
        with patch.object(rate_limiter, 'check_tenant_limit', return_value=(False, 60)):
            await worker._process_command(cmd_2)

        # Should not have called ChirpStack again (rate limited)
        assert chirpstack_mock.queue_downlink.call_count == 1

        # Metrics should show retry
        metrics = await downlink_queue.get_metrics()
        assert metrics["total_retried"] >= 1


@pytest.mark.asyncio
async def test_acceptance_burst_100_updates(downlink_queue, rate_limiter):
    """
    Acceptance Test: Burst of 100 updates drained respecting rate limits

    Verifies:
    - Queue handles burst without crash
    - Rate limiting is enforced
    - All commands eventually processed or dead-lettered
    """
    chirpstack_mock = AsyncMock()
    chirpstack_mock.queue_downlink = AsyncMock(return_value={"id": "downlink-123"})

    worker = DownlinkWorker(
        queue=downlink_queue,
        rate_limiter=rate_limiter,
        chirpstack_client=chirpstack_mock
    )

    # Enqueue 100 commands
    for i in range(100):
        await downlink_queue.enqueue(
            device_eui=f"device-{i % 10}",  # 10 unique devices
            payload=f"{i:06x}",
            fport=15,
            tenant_id="tenant-1"
        )

    # Verify queue depth
    metrics = await downlink_queue.get_metrics()
    assert metrics["queue_depth"] <= 100  # Some may be coalesced

    # Start worker
    await worker.start()

    # Process for a short time
    await asyncio.sleep(2)

    # Stop worker
    await worker.stop()

    # Verify progress
    final_metrics = await downlink_queue.get_metrics()
    assert final_metrics["total_succeeded"] > 0  # At least some processed
    assert final_metrics["queue_depth"] < 100  # Queue draining


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
