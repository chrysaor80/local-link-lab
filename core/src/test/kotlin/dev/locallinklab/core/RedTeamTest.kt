package dev.locallinklab.core

import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import java.net.ServerSocket
import java.net.SocketTimeoutException
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.concurrent.thread

/** M1 red-team checks written by the reviewer against ee67e2c. Expected outcome is stated per test. */
class RedTeamTest {
    private val dbId = UUID.randomUUID().toString()
    private val endpoint = Endpoint("127.0.0.1", 8765)

    /** Regression, expected PASS: trickled bytes without LF must not extend the attempt deadline. */
    @Test fun trickledBytesDoNotExtendAttemptDeadline() {
        ServerSocket(0).use { server ->
            val peer = thread {
                runCatching {
                    server.accept().use { socket ->
                        val input = socket.getInputStream()
                        while (true) { val byte = input.read(); if (byte == 10) break; check(byte != -1) { "EOF before request" } }
                        val out = socket.getOutputStream()
                        for (i in 0 until 40) {
                            if (runCatching { out.write(' '.code); out.flush() }.isFailure) break
                            Thread.sleep(100)
                        }
                    }
                }
            }
            val started = System.nanoTime()
            val result = runCatching {
                runBlocking { TcpTransport(attemptMs = 500).exchange(Endpoint("127.0.0.1", server.localPort), Message.Hello) }
            }
            val elapsedMs = (System.nanoTime() - started) / 1_000_000
            assertTrue(result.isFailure)
            assertTrue("elapsed=$elapsedMs ms", elapsedMs in 400..1500)
            peer.join(5000)
        }
    }

    private class OneOrder(private val order: PendingOrder) : Outbox {
        var receipt: String? = null
        var attention: String? = null
        override suspend fun nextPending() = order.takeIf { receipt == null && attention == null }
        override suspend fun acknowledge(requestId: String, receiptId: String) { receipt = receiptId }
        override suspend fun needsAttention(requestId: String, reason: String) { attention = reason }
    }

    /** Regression, expected PASS: replies for another request or another DB never resolve the order. */
    @Test fun unrelatedRepliesNeverResolveTheOrder() = runTest {
        val pending = PendingOrder(UUID.randomUUID().toString(), dbId, Order("DEMO", 1, 3000))
        val outbox = OneOrder(pending)
        val receipt = UUID.randomUUID().toString()
        val replies = ArrayDeque(listOf<Message>(
            Message.Ack(dbId, UUID.randomUUID().toString(), UUID.randomUUID().toString()),
            Message.Ack(UUID.randomUUID().toString(), pending.requestId, UUID.randomUUID().toString()),
            Message.Error(UUID.randomUUID().toString(), pending.requestId, "ID_CONFLICT"),
            Message.Error(dbId, null, "INVALID_REQUEST"),
            Message.Ack(dbId, pending.requestId, receipt),
        ))
        val engine = DeliveryEngine(outbox, Transport { _, _ -> replies.removeFirst() }, jitter = { 0.0 })
        assertEquals(StopReason.EMPTY, engine.drain(endpoint))
        assertEquals(receipt, outbox.receipt)
        assertNull(outbox.attention)
    }

    /**
     * M1-01 root cause, expected FAIL at ee67e2c: on a real-time single-thread caller (like Android Main),
     * the transport's own attempt deadline surfaces as TimeoutCancellationException, which the probe
     * branch rethrows, leaving "POS 연결 확인 중" on screen. Robolectric's paused clock hides this.
     */
    @Test fun attemptDeadlineIsNotReportedAsCancellation() {
        val main = Executors.newSingleThreadExecutor().asCoroutineDispatcher()
        try {
            ServerSocket(0).use { silent ->
                thread(isDaemon = true) { runCatching { silent.accept().use { Thread.sleep(3000) } } }
                val started = System.nanoTime()
                val error = runBlocking(main) {
                    runCatching { TcpTransport(attemptMs = 300).exchange(Endpoint("127.0.0.1", silent.localPort), Message.Hello) }
                        .exceptionOrNull()
                }
                val elapsed = (System.nanoTime() - started) / 1_000_000
                assertTrue("deadline surfaced as $error", error is SocketTimeoutException)
                assertTrue("elapsed=$elapsed ms", elapsed in 200..1500)
            }
        } finally { main.close() }
    }

    /**
     * Recommended behaviour, expected FAIL at ee67e2c: ambiguous IPv4 text (leading zeros) passes the
     * validator and reaches the platform resolver. Desktop JDK 21 reads it as decimal; Android is unverified.
     */
    @Test fun ambiguousIpv4TextIsRejectedBeforeResolution() = runBlocking {
        ServerSocket(0).use { server ->
            for (host in listOf("127.000.000.001", "１２７.0.0.1", "127.0.0.256", "localhost", "127.0.0", "127.0.0.1.")) {
                val error = runCatching {
                    TcpTransport(attemptMs = 300).exchange(Endpoint(host, server.localPort), Message.Hello)
                }.exceptionOrNull()
                assertTrue("$host -> $error", error is IllegalArgumentException)
            }
        }
    }
}
