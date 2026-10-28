package dev.locallinklab.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.AtomicFile
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** ADB-only test adapter; acceptance and pause use the same controller as the screen. */
class LabControlReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val token = intent.getStringExtra("token") ?: return
        if (!Regex("[a-f0-9-]{36}").matches(token)) return
        val pendingResult = goAsync()
        scope.launch {
            val file = AtomicFile(File(context.filesDir, "lab-$token.json"))
            try {
                val app = context.applicationContext as LinkApplication
                val c = app.controller
                val result = withTimeout(8000) {
                    check(!c.busy.value) { "Controller is busy; command was not applied" }
                    when (intent.getStringExtra("command")) {
                        "configure" -> {
                            val host = checkNotNull(intent.getStringExtra("host"))
                            val port = checkNotNull(intent.getStringExtra("port"))
                            c.connect(host, port)
                            c.settings.first { it?.host == host && it.port == port.toInt() }
                            c.busy.first { !it }
                        }
                        "accept" -> {
                            val id = checkNotNull(intent.getStringExtra("request_id"))
                            c.accept(id)
                            c.orders.first { rows -> rows.any { it.requestId == id } }
                            c.busy.first { !it }
                        }
                        "pause", "resume" -> {
                            val paused = intent.getStringExtra("command") == "pause"
                            c.pause(paused)
                            c.settings.first { it?.userPaused == paused }
                            c.busy.first { !it }
                        }
                        "snapshot" -> Unit
                        else -> error("Unknown lab command")
                    }
                    val config = c.repository.dao.settings()
                    val rows = c.repository.dao.observeOrders().first()
                    JSONObject().put("ok", true).put("token", token)
                        .put("pid", android.os.Process.myPid()).put("runtime", c.runtime.value)
                        .put("user_paused", config?.userPaused ?: false)
                        .put("pos_db_id", config?.posDbId ?: JSONObject.NULL)
                        .put("rows", JSONArray().apply {
                            rows.forEach { row -> put(JSONObject()
                                .put("request_id", row.requestId).put("pos_db_id", row.posDbId)
                                .put("item_code", row.itemCode).put("quantity", row.quantity)
                                .put("unit_price_krw", row.unitPriceKrw).put("status", row.status)
                                .put("receipt_id", row.receiptId ?: JSONObject.NULL)) }
                        })
                }
                write(file, result)
            } catch (e: Exception) {
                write(file, JSONObject().put("ok", false).put("token", token).put("error", e.toString()))
            } finally { pendingResult.finish() }
        }
    }
    private fun write(file: AtomicFile, value: JSONObject) {
        val stream = file.startWrite()
        try { stream.write(value.toString().toByteArray(Charsets.UTF_8)); file.finishWrite(stream) }
        catch (e: Exception) { file.failWrite(stream); throw e }
    }
    companion object { private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate) }
}
