package dev.locallinklab.app

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.net.InetAddress
import java.net.ServerSocket
import java.util.UUID
import kotlin.concurrent.thread

/**
 * M1 red-team checks written by the reviewer against ee67e2c. Both are expected to FAIL there.
 * Adopted with stable probe outcomes. Host POS on 10.0.2.2:18766 needs its OWN fresh POS DB:
 * these tests add orders, so running them before verify_m1.py would break its one-row check.
 */
class ControllerRecoveryTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val controller get() = (compose.activity.application as LinkApplication).controller

    private fun configureHostPos() {
        var sequence = 0L
        compose.runOnUiThread { sequence = controller.connect("10.0.2.2", "18766") }
        compose.waitUntil(15000) { controller.probeResult.value?.sequence == sequence && controller.settings.value != null && !controller.busy.value }
        assertEquals(true, controller.probeResult.value?.succeeded)
        assertEquals("10.0.2.2", controller.settings.value?.host)
    }

    /** A failed "연결 확인" must not leave the foreground app without a delivery worker. */
    @Test fun failedProbeKeepsDeliveringToConfiguredPos() {
        configureHostPos()
        val closedPort = ServerSocket(0).use { it.localPort }
        var sequence = 0L
        compose.runOnUiThread { sequence = controller.connect("127.0.0.1", closedPort.toString()) }
        compose.waitUntil(10000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value }
        assertEquals(false, controller.probeResult.value?.succeeded)
        val id = UUID.randomUUID().toString()
        compose.runOnUiThread { controller.accept(id) }
        compose.waitUntil(20000) { controller.orders.value.any { it.requestId == id && it.status == "ACKNOWLEDGED" } }
    }

    /** A hello that hits the 5 s attempt deadline must be reported, not left as "POS 연결 확인 중". */
    @Test fun probeDeadlineIsReportedNotLeftAsChecking() {
        configureHostPos()
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { silent ->
            thread(isDaemon = true) { runCatching { silent.accept().use { Thread.sleep(8000) } } }
            var sequence = 0L
            compose.runOnUiThread { sequence = controller.connect("127.0.0.1", silent.localPort.toString()) }
            compose.waitUntil(3000) { controller.busy.value } // the probe has really started
            compose.waitUntil(9000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value }
            assertEquals(false, controller.probeResult.value?.succeeded)
            assertNotEquals("POS 연결 확인 중", controller.runtime.value)
            val id = UUID.randomUUID().toString()
            compose.runOnUiThread { controller.accept(id) }
            compose.waitUntil(20000) { controller.orders.value.any { it.requestId == id && it.status == "ACKNOWLEDGED" } }
        }
    }
}
