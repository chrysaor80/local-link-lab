package dev.locallinklab.core

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlin.random.Random

interface Outbox {
    suspend fun nextPending(): PendingOrder?
    suspend fun acknowledge(requestId: String, receiptId: String)
    suspend fun needsAttention(requestId: String, reason: String)
}

enum class StopReason { EMPTY, RETRY_LIMIT, POS_MISMATCH }

class DeliveryEngine(
    private val outbox: Outbox,
    private val transport: Transport,
    private val attempts: Int = 5,
    private val jitter: () -> Double = { Random.nextDouble() },
) {
    suspend fun drain(endpoint: Endpoint, event: (String) -> Unit = {}): StopReason {
        while (true) {
            currentCoroutineContext().ensureActive()
            val pending = outbox.nextPending() ?: return StopReason.EMPTY
            var resolved = false
            for (attempt in 0 until attempts) {
                currentCoroutineContext().ensureActive()
                event("전송 중 (${attempt + 1}/$attempts)")
                try {
                    when (val response = transport.exchange(endpoint, Message.Submit(pending))) {
                        is Message.Ack -> {
                            if (response.requestId != pending.requestId || response.dbId != pending.dbId) throw WireException("Unrelated ACK")
                            outbox.acknowledge(pending.requestId, response.receiptId)
                            resolved = true
                        }
                        is Message.Error -> {
                            if (response.requestId != pending.requestId) throw WireException("Unrelated error")
                            if (response.code == "POS_MISMATCH") return StopReason.POS_MISMATCH
                            if (response.dbId != pending.dbId) throw WireException("Unrelated database")
                            if (response.code == "TEMPORARY_UNAVAILABLE") throw WireException("Temporary unavailable")
                            outbox.needsAttention(pending.requestId, response.code)
                            resolved = true
                        }
                        else -> throw WireException("Unexpected reply")
                    }
                } catch (e: TimeoutCancellationException) {
                    // A transport-local timeout is retryable; parent cancellation is not.
                    currentCoroutineContext().ensureActive()
                    event("응답 확인 대기")
                } catch (e: CancellationException) { throw e
                } catch (e: Exception) {
                    currentCoroutineContext().ensureActive()
                    event("응답 확인 대기: ${e.message ?: e.javaClass.simpleName}")
                }
                if (resolved) break
                if (attempt < attempts - 1) {
                    event("재시도 대기")
                    val base = (1000L shl attempt).coerceAtMost(8000L)
                    delay(base + (base * 0.2 * jitter().coerceIn(0.0, 1.0)).toLong())
                }
            }
            if (!resolved) return StopReason.RETRY_LIMIT
        }
    }
}
