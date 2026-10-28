package dev.locallinklab.core

import com.squareup.moshi.JsonReader
import com.squareup.moshi.JsonWriter
import okio.Buffer
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction

data class Order(val itemCode: String, val quantity: Int, val unitPriceKrw: Long)
data class PendingOrder(val requestId: String, val dbId: String, val order: Order)
data class Endpoint(val host: String, val port: Int)

sealed interface Message {
    data object Hello : Message
    data class HelloAck(val dbId: String) : Message
    data class Submit(val pending: PendingOrder) : Message
    data class Ack(val dbId: String, val requestId: String, val receiptId: String) : Message
    data class Error(val dbId: String, val requestId: String?, val code: String) : Message
}

class WireException(message: String) : java.io.IOException(message)

object Wire {
    const val MAX_FRAME = 8192
    private val uuid = Regex("[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
    private val codes = setOf("INVALID_REQUEST", "UNSUPPORTED_VERSION", "ID_CONFLICT", "TEMPORARY_UNAVAILABLE", "POS_MISMATCH")
    fun validUuid(value: String) = uuid.matches(value)

    fun decode(frame: ByteArray): Message {
        if (frame.size > MAX_FRAME || frame.lastOrNull() != 10.toByte() || frame.count { it == 10.toByte() } != 1 || frame.contains(13.toByte()))
            throw WireException("Invalid frame boundary")
        val text = try {
            Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(frame, 0, frame.size - 1)).toString()
        } catch (e: java.nio.charset.CharacterCodingException) { throw WireException("Invalid UTF-8") }
        if (text.startsWith('\uFEFF')) throw WireException("BOM")
        val reader = JsonReader.of(Buffer().writeUtf8(text))
        val value = read(reader, 0)
        if (reader.peek() != JsonReader.Token.END_DOCUMENT) throw WireException("Trailing data")
        val obj = value as? Map<*, *> ?: throw WireException("Object required")
        if (obj["version"] != 1L) throw WireException("Version")
        fun keys(vararg names: String) { if (obj.keys != names.toSet() + setOf("version", "type")) throw WireException("Fields") }
        fun id(key: String) = (obj[key] as? String)?.takeIf(::validUuid) ?: throw WireException(key)
        return when (obj["type"]) {
            "hello" -> { keys(); Message.Hello }
            "hello_ack" -> { keys("pos_db_id"); Message.HelloAck(id("pos_db_id")) }
            "submit_order" -> {
                keys("pos_db_id", "request_id", "order")
                val body = obj["order"] as? Map<*, *> ?: throw WireException("Order")
                if (body.keys != setOf("item_code", "quantity", "unit_price_krw")) throw WireException("Order fields")
                val item = (body["item_code"] as? String)?.takeIf { Regex("[A-Z0-9_-]{1,32}").matches(it) } ?: throw WireException("Item")
                val qty = (body["quantity"] as? Long)?.takeIf { it in 1..99 } ?: throw WireException("Quantity")
                val price = (body["unit_price_krw"] as? Long)?.takeIf { it in 0..1_000_000_000 } ?: throw WireException("Price")
                Message.Submit(PendingOrder(id("request_id"), id("pos_db_id"), Order(item, qty.toInt(), price)))
            }
            "ack" -> { keys("pos_db_id", "request_id", "receipt_id"); Message.Ack(id("pos_db_id"), id("request_id"), id("receipt_id")) }
            "error" -> {
                keys("pos_db_id", "request_id", "code")
                val rid = if (obj["request_id"] == null) null else id("request_id")
                val code = (obj["code"] as? String)?.takeIf { it in codes } ?: throw WireException("Error code")
                Message.Error(id("pos_db_id"), rid, code)
            }
            else -> throw WireException("Message type")
        }
    }

    private fun read(reader: JsonReader, depth: Int): Any? {
        if (depth > 8) throw WireException("Nesting")
        return when (reader.peek()) {
            JsonReader.Token.BEGIN_OBJECT -> {
                val result = linkedMapOf<String, Any?>()
                reader.beginObject()
                while (reader.hasNext()) {
                    val key = reader.nextName()
                    if (result.containsKey(key)) throw WireException("Duplicate key")
                    result[key] = read(reader, depth + 1)
                }
                reader.endObject(); result
            }
            JsonReader.Token.STRING -> reader.nextString()
            JsonReader.Token.NUMBER -> {
                val literal = reader.nextString()
                if (!Regex("-?(0|[1-9][0-9]*)").matches(literal)) throw WireException("Integer literal required")
                literal.toLongOrNull() ?: throw WireException("Integer overflow")
            }
            JsonReader.Token.BOOLEAN -> reader.nextBoolean()
            JsonReader.Token.NULL -> reader.nextNull<Any>()
            else -> throw WireException("Unexpected token")
        }
    }

    fun encode(message: Message): ByteArray {
        val fields = linkedMapOf<String, Any?>("version" to 1)
        when (message) {
            Message.Hello -> fields["type"] = "hello"
            is Message.HelloAck -> { fields["type"] = "hello_ack"; fields["pos_db_id"] = message.dbId }
            is Message.Submit -> {
                val p = message.pending
                fields.putAll(mapOf("type" to "submit_order", "pos_db_id" to p.dbId, "request_id" to p.requestId,
                    "order" to mapOf("item_code" to p.order.itemCode, "quantity" to p.order.quantity, "unit_price_krw" to p.order.unitPriceKrw)))
            }
            is Message.Ack -> fields.putAll(mapOf("type" to "ack", "pos_db_id" to message.dbId, "request_id" to message.requestId, "receipt_id" to message.receiptId))
            is Message.Error -> fields.putAll(mapOf("type" to "error", "pos_db_id" to message.dbId, "request_id" to message.requestId, "code" to message.code))
        }
        val buffer = Buffer()
        val writer = JsonWriter.of(buffer).apply { serializeNulls = true }
        fun write(value: Any?) {
            when (value) {
                null -> writer.nullValue()
                is Map<*, *> -> { writer.beginObject(); value.forEach { (k, v) -> writer.name(k as String); write(v) }; writer.endObject() }
                is String -> writer.value(value)
                is Number -> writer.value(value)
                else -> throw WireException("Unsupported value")
            }
        }
        write(fields); writer.flush()
        val result = buffer.writeByte(10).readByteArray()
        decode(result)
        return result
    }
}
