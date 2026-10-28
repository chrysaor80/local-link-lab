package dev.locallinklab.core

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.net.ServerSocket
import java.net.SocketTimeoutException

class TcpTransportTest {
    @Test fun callerDeadlineStillCancelsAndClosesSocket() = runBlocking {
        ServerSocket(0).use { server ->
            server.soTimeout = 3000
            val peer = async(Dispatchers.IO) {
                server.accept().use { socket ->
                    socket.soTimeout = 3000
                    val input = socket.getInputStream()
                    while (true) { val byte = input.read(); if (byte == 10) break; check(byte != -1) }
                    input.read()
                }
            }
            val result = runCatching {
                withTimeout(300) { TcpTransport(attemptMs = 5000).exchange(Endpoint("127.0.0.1", server.localPort), Message.Hello) }
            }
            assertTrue(result.exceptionOrNull() is TimeoutCancellationException)
            assertEquals(-1, withTimeout(3000) { peer.await() })
        }
    }
    @Test fun parentCancellationClosesBlockedSocket() = runBlocking {
        ServerSocket(0).use { server ->
            val accepted = CompletableDeferred<Unit>()
            val peer = async(Dispatchers.IO) {
                server.accept().use { socket ->
                    socket.soTimeout = 3000
                    val input = socket.getInputStream()
                    while (true) { val byte = input.read(); if (byte == 10) break; check(byte != -1) { "EOF before request" } }
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
                    while (true) { val byte = input.read(); if (byte == 10) break; check(byte != -1) { "EOF before request" } }
                    input.read()
                }
            }
            val started = System.nanoTime()
            val result = runCatching { TcpTransport(attemptMs = 200).exchange(Endpoint("127.0.0.1", server.localPort), Message.Hello) }
            val elapsed = (System.nanoTime() - started) / 1_000_000
            assertTrue(result.exceptionOrNull() is SocketTimeoutException)
            assertTrue("elapsed=$elapsed ms", elapsed in 150..1500)
            assertEquals(-1, withTimeout(3000) { peer.await() })
        }
    }
}
