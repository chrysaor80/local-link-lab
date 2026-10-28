package dev.locallinklab.core

import com.squareup.moshi.Moshi
import org.junit.Assert.*
import org.junit.Test

class WireTest {
    @Test fun sharedRawCorpus() {
        val source = checkNotNull(javaClass.getResource("/wire.raw-examples.json")).readText()
        val cases = Moshi.Builder().build().adapter(List::class.java).fromJson(source)!!
        for (raw in cases) {
            val case = raw as Map<*, *>
            val frame = (case["frame_hex"] as String).chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            val result = runCatching { Wire.decode(frame) }
            assertEquals("${case["name"]}: ${result.exceptionOrNull()}", case["expected_valid"], result.isSuccess)
            result.getOrNull()?.let { assertEquals(it, Wire.decode(Wire.encode(it))) }
        }
    }
}
