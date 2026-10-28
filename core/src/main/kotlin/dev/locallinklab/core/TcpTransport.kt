package dev.locallinklab.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

fun interface Transport { suspend fun exchange(endpoint: Endpoint, message: Message): Message }

class TcpTransport(private val attemptMs: Long = 5000, private val connectMs: Int = 2000) : Transport {
    override suspend fun exchange(endpoint: Endpoint, message: Message): Message = withTimeout(attemptMs) {
        require(endpoint.port in 1..65535)
        require(endpoint.host.split('.').let { parts -> parts.size == 4 && parts.all { it.isNotEmpty() && it.all(Char::isDigit) && it.toIntOrNull() in 0..255 } })
        val frame = Wire.encode(message)
        withContext(Dispatchers.IO) {
            suspendCancellableCoroutine { continuation ->
                val socket = Socket()
                continuation.invokeOnCancellation { runCatching { socket.close() } }
                try {
                    val deadline = System.nanoTime() + attemptMs * 1_000_000
                    socket.connect(InetSocketAddress(endpoint.host, endpoint.port), minOf(connectMs, attemptMs.toInt()))
                    socket.getOutputStream().write(frame)
                    val result = ByteArrayOutputStream()
                    val input = socket.getInputStream()
                    while (true) {
                        val remaining = (deadline - System.nanoTime()) / 1_000_000
                        if (remaining <= 0) throw SocketTimeoutException("Attempt deadline")
                        socket.soTimeout = remaining.coerceAtMost(Int.MAX_VALUE.toLong()).toInt().coerceAtLeast(1)
                        val byte = input.read()
                        if (byte < 0) throw WireException("EOF before LF")
                        result.write(byte)
                        if (result.size() > Wire.MAX_FRAME) throw WireException("Oversized frame")
                        if (byte == 10) break
                    }
                    val response = Wire.decode(result.toByteArray())
                    if (continuation.isActive) continuation.resume(response)
                } catch (e: Exception) {
                    if (continuation.isActive) continuation.resumeWithException(e)
                } finally { runCatching { socket.close() } }
            }
        }
    }
}
