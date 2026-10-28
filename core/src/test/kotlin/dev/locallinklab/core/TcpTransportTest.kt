package dev.locallinklab.core

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.net.ServerSocket

class TcpTransportTest {
    @Test fun parentCancellationClosesBlockedSocket() = runBlocking {
        ServerSocket(0).use { server ->
            val accepted = CompletableDeferred<Unit>()
            val peer = async(Dispatchers.IO) {
                server.accept().use { socket ->
                    socket.soTimeout = 3000
                    val input = socket.getInputStream()
                    while (input.read() != 10) { }
                    accepted.complete(Unit)
                    input.read() // EOF proves the actual client socket closed.
                }
            }
            val client = launch { TcpTransport().exchange(Endpoint("127.0.0.1", server.localPort), Message.Hello) }
            withTimeout(3000) { accepted.await() }
            client.cancelAndJoin()
            assertEquals(-1, withTimeout(3000) { peer.await() })
        }
    }
    @Test fun silentPeerHitsDeadlineAndClosesSocket() = runBlocking {
        ServerSocket(0).use { server ->
            val peer = async(Dispatchers.IO) {
                server.accept().use { socket ->
                    socket.soTimeout = 3000
                    val input = socket.getInputStream()
                    while (input.read() != 10) { }
                    input.read()
                }
            }
            val result = runCatching { TcpTransport(attemptMs = 200).exchange(Endpoint("127.0.0.1", server.localPort), Message.Hello) }
            assertTrue(result.isFailure)
            assertEquals(-1, withTimeout(3000) { peer.await() })
        }
    }
}
