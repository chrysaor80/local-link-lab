package dev.locallinklab.core

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlin.random.Random

enum class DestinationResult { VERIFIED, MISMATCH, UNAVAILABLE }

/** Run once on each foreground/resume before draining saved orders. Never creates an order. */
class DestinationVerifier(
    private val transport: Transport,
    private val attempts: Int = 5,
    private val jitter: () -> Double = { Random.nextDouble() },
) {
    suspend fun verify(endpoint: Endpoint, expectedDbId: String, event: (String) -> Unit = {}): DestinationResult {
        require(attempts in 1..5)
        for (attempt in 0 until attempts) {
            currentCoroutineContext().ensureActive()
            event("POS 대상 확인 중 (${attempt + 1}/$attempts)")
            try {
                val reply = transport.exchange(endpoint, Message.Hello) as? Message.HelloAck
                    ?: throw WireException("Unexpected identity response")
                return if (reply.dbId == expectedDbId) DestinationResult.VERIFIED else DestinationResult.MISMATCH
            } catch (e: TimeoutCancellationException) {
                currentCoroutineContext().ensureActive()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { currentCoroutineContext().ensureActive() }
            if (attempt < attempts - 1) {
                val base = 1000L shl attempt
                delay(base + (base * 0.2 * jitter().coerceIn(0.0, 1.0)).toLong())
            }
        }
        return DestinationResult.UNAVAILABLE
    }
}
