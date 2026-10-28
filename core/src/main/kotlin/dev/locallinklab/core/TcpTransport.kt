package dev.locallinklab.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.InetAddress
import java.net.Socket
import java.net.SocketTimeoutException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

fun interface Transport { suspend fun exchange(endpoint: Endpoint, message: Message): Message }

/** Canonical ASCII IPv4 only; never hand user input to a hostname resolver. */
fun Endpoint.socketAddress(): InetSocketAddress {
    require(port in 1..65535) { "포트는 1~65535를 입력하세요." }
    val parts = host.split('.')
    require(parts.size == 4 && parts.all { it.matches(Regex("0|[1-9][0-9]{0,2}")) && it.toInt() <= 255 }) {
        "IPv4는 192.168.0.10처럼 입력하세요. 앞자리 0은 허용하지 않습니다."
    }
    return InetSocketAddress(InetAddress.getByAddress(parts.map { it.toInt().toByte() }.toByteArray()), port)
}

class TcpTransport(private val attemptMs: Long = 5000, private val connectMs: Int = 2000) : Transport {
    override suspend fun exchange(endpoint: Endpoint, message: Message): Message = withTimeoutOrNull(attemptMs) {
        val address = endpoint.socketAddress()
        val frame = Wire.encode(message)
        withContext(Dispatchers.IO) {
            suspendCancellableCoroutine { continuation ->
                val socket = Socket()
                continuation.invokeOnCancellation { runCatching { socket.close() } }
                try {
                    val deadline = System.nanoTime() + attemptMs * 1_000_000
                    socket.connect(address, minOf(connectMs, attemptMs.coerceAtMost(Int.MAX_VALUE.toLong()).toInt()))
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
    } ?: throw SocketTimeoutException("Attempt deadline")
}
