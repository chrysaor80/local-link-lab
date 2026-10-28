package dev.locallinklab.core

import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.UUID

@OptIn(ExperimentalCoroutinesApi::class)
class DestinationVerifierTest {
    private val expected = UUID.randomUUID().toString()
    private val endpoint = Endpoint("127.0.0.1", 8765)

    @Test fun anotherDatabaseStopsWithoutSubmittingOrAdoptingItsIdentity() = runTest {
        val sent = mutableListOf<Message>()
        val verifier = DestinationVerifier(Transport { _, request ->
            sent += request; Message.HelloAck(UUID.randomUUID().toString())
        })
        assertEquals(DestinationResult.MISMATCH, verifier.verify(endpoint, expected))
        assertEquals(listOf(Message.Hello), sent)
    }
    @Test fun resumeChecksAgainEvenAfterPreviousVerification() = runTest {
        var calls = 0
        val verifier = DestinationVerifier(Transport { _, _ ->
            calls++; Message.HelloAck(if (calls == 1) expected else UUID.randomUUID().toString())
        })
        assertEquals(DestinationResult.VERIFIED, verifier.verify(endpoint, expected))
        assertEquals(DestinationResult.MISMATCH, verifier.verify(endpoint, expected))
        assertEquals(2, calls)
    }
    @Test fun lostHelloCanRecoverWithinBoundedAttempts() = runTest {
        var calls = 0
        val verifier = DestinationVerifier(Transport { _, _ ->
            calls++; if (calls < 3) throw IOException("lost hello")
            Message.HelloAck(expected)
        }, jitter = { 0.0 })
        assertEquals(DestinationResult.VERIFIED, verifier.verify(endpoint, expected))
        assertEquals(3, calls)
        assertEquals(3000L, testScheduler.currentTime)
    }
    @Test fun silenceAndWrongReplyDoNotConfirmDestination() = runTest {
        var calls = 0
        val verifier = DestinationVerifier(Transport { _, _ ->
            calls++; if (calls % 2 == 0) Message.Hello else withTimeout(1) { awaitCancellation() }
        }, jitter = { 0.0 })
        assertEquals(DestinationResult.UNAVAILABLE, verifier.verify(endpoint, expected))
        assertEquals(5, calls)
    }
    @Test fun parentCancellationStopsIdentityRetries() = runTest {
        val entered = CompletableDeferred<Unit>()
        var calls = 0
        val verifier = DestinationVerifier(Transport { _, _ -> calls++; entered.complete(Unit); awaitCancellation() })
        val job = launch { verifier.verify(endpoint, expected) }
        entered.await(); job.cancelAndJoin(); advanceUntilIdle()
        assertEquals(1, calls)
    }
}
