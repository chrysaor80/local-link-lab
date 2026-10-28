package dev.locallinklab.core

import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.UUID

@OptIn(ExperimentalCoroutinesApi::class)
class DeliveryEngineTest {
    private val dbId = UUID.randomUUID().toString()
    private val endpoint = Endpoint("127.0.0.1", 8765)
    private fun order() = PendingOrder(UUID.randomUUID().toString(), dbId, Order("DEMO", 1, 3000))
    private class FakeOutbox(val accepted: List<PendingOrder>) : Outbox {
        val acked = mutableMapOf<String, String>()
        val attention = mutableSetOf<String>()
        var failAckOnce = false
        override suspend fun nextPending() = accepted.firstOrNull { it.requestId !in acked && it.requestId !in attention }
        override suspend fun acknowledge(requestId: String, receiptId: String) {
            if (failAckOnce) { failAckOnce = false; throw IOException("local disk failure") }
            acked[requestId] = receiptId
        }
        override suspend fun needsAttention(requestId: String, reason: String) { attention += requestId }
    }
    @Test fun lostAckReusesIdAndReceiptWithoutExtraPosRows() = runTest {
        val baseline = listOf(order())
        val outbox = FakeOutbox(baseline)
        val posRows = mutableMapOf<String, Pair<Order, String>>()
        val seen = mutableListOf<PendingOrder>()
        val transport = Transport { _, message ->
            val p = (message as Message.Submit).pending
            seen += p
            val row = posRows.getOrPut(p.requestId) { p.order to UUID.randomUUID().toString() }
            if (seen.size == 1) throw IOException("committed but reply lost")
            Message.Ack(p.dbId, p.requestId, row.second)
        }
        assertEquals(StopReason.EMPTY, DeliveryEngine(outbox, transport, jitter = { 0.0 }).drain(endpoint))
        assertEquals(listOf(baseline.single(), baseline.single()), seen)
        assertEquals(baseline.map { it.requestId }.toSet(), posRows.keys)
        assertEquals(posRows.values.single().second, outbox.acked.values.single())
    }
    @Test fun localAckFailureDoesNotAdvanceUntilDurableAck() = runTest {
        val outbox = FakeOutbox(listOf(order(), order())).apply { failAckOnce = true }
        val seen = mutableListOf<String>()
        val receipts = outbox.accepted.associate { it.requestId to UUID.randomUUID().toString() }
        val transport = Transport { _, message ->
            val p = (message as Message.Submit).pending; seen += p.requestId
            Message.Ack(dbId, p.requestId, receipts.getValue(p.requestId))
        }
        DeliveryEngine(outbox, transport, jitter = { 0.0 }).drain(endpoint)
        val ids = outbox.accepted.map { it.requestId }
        assertEquals(listOf(ids[0], ids[0], ids[1]), seen)
        assertEquals(receipts, outbox.acked)
    }
    @Test fun conflictRetainsOrderAndAllowsNextPending() = runTest {
        val outbox = FakeOutbox(listOf(order(), order()))
        val conflict = outbox.accepted.first().requestId
        val transport = Transport { _, message ->
            val p = (message as Message.Submit).pending
            if (p.requestId == conflict) Message.Error(dbId, p.requestId, "ID_CONFLICT")
            else Message.Ack(dbId, p.requestId, UUID.randomUUID().toString())
        }
        assertEquals(StopReason.EMPTY, DeliveryEngine(outbox, transport).drain(endpoint))
        assertEquals(setOf(conflict), outbox.attention)
        assertEquals(1, outbox.acked.size)
        assertEquals(2, outbox.accepted.size)
    }
    @Test fun wrongPosDoesNotChangeOrder() = runTest {
        val outbox = FakeOutbox(listOf(order()))
        val transport = Transport { _, message ->
            Message.Error(UUID.randomUUID().toString(), (message as Message.Submit).pending.requestId, "POS_MISMATCH")
        }
        assertEquals(StopReason.POS_MISMATCH, DeliveryEngine(outbox, transport).drain(endpoint))
        assertNotNull(outbox.nextPending())
        assertTrue(outbox.acked.isEmpty())
        assertTrue(outbox.attention.isEmpty())
    }
    @Test fun exhaustedRetriesPreserveHeadAndDoNotSendFollowingOrder() = runTest {
        val outbox = FakeOutbox(listOf(order(), order()))
        val ids = mutableListOf<String>()
        val transport = Transport { _, message ->
            ids += (message as Message.Submit).pending.requestId; throw IOException("offline")
        }
        assertEquals(StopReason.RETRY_LIMIT, DeliveryEngine(outbox, transport, jitter = { 0.0 }).drain(endpoint))
        assertEquals(List(5) { outbox.accepted.first().requestId }, ids)
        assertEquals(15000L, testScheduler.currentTime)
        assertTrue(outbox.acked.isEmpty())
    }
    @Test fun cancellationDoesNotRetryOrMarkAttention() = runTest {
        val outbox = FakeOutbox(listOf(order()))
        var attempts = 0
        val entered = CompletableDeferred<Unit>()
        val transport = Transport { _, _ -> attempts++; entered.complete(Unit); awaitCancellation() }
        val job = launch { DeliveryEngine(outbox, transport).drain(endpoint) }
        entered.await(); job.cancelAndJoin(); advanceUntilIdle()
        assertEquals(1, attempts)
        assertTrue(outbox.acked.isEmpty()); assertTrue(outbox.attention.isEmpty())
    }
}
