package dev.locallinklab.app

import android.app.Application
import android.os.Looper
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.locallinklab.core.Message
import dev.locallinklab.core.Wire
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.net.InetAddress
import java.net.ServerSocket
import java.time.Duration
import java.util.UUID
import kotlin.concurrent.thread

/**
 * Reviewer harness for M1-01, adopted with stable probe outcomes and teardown: the real LinkController + Repository + Room + TcpTransport on the JVM
 * (Robolectric), talking to a real POS process: python -m pos.server --port 18765 (fresh DB).
 * No Activity/Compose/ProcessLifecycleOwner: onStart/onStop are called directly.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class ControllerRobolectricTest {
    private val posPort = System.getProperty("pos.port") ?: "18765"
    private lateinit var db: LinkDatabase
    private lateinit var controller: LinkController
    private val owner = object : LifecycleOwner {
        private val registry = LifecycleRegistry(this)
        override val lifecycle: Lifecycle get() = registry
    }

    @Before fun setUp() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Application>(), LinkDatabase::class.java).build()
        controller = LinkController(Repository(db))
        controller.onStart(owner)
        val sequence = controller.connect("127.0.0.1", posPort)
        // Harness readiness includes Robolectric/Room cold start; product deadlines stay unchanged.
        assertTrue("initial probe completed", waitFor(30_000) { controller.probeResult.value?.sequence == sequence && controller.settings.value != null && !controller.busy.value })
        assertEquals(true, controller.probeResult.value?.succeeded)
        assertNotNull("harness: POS on $posPort must answer hello (${controller.runtime.value})", controller.settings.value)
    }

    @After fun tearDown() {
        controller.close()
        pump(300)
        db.close()
    }

    /** Main looper is paused under Robolectric: advance its clock roughly in step with wall time. */
    private fun step() { shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20)); Thread.sleep(20) }
    private fun pump(ms: Long) { val end = System.nanoTime() + ms * 1_000_000; while (System.nanoTime() < end) step() }
    private fun waitFor(ms: Long, condition: () -> Boolean): Boolean {
        val end = System.nanoTime() + ms * 1_000_000
        while (System.nanoTime() < end) { if (condition()) return true; step() }
        return condition()
    }
    private fun acked(id: String) = controller.orders.value.any { it.requestId == id && it.status == "ACKNOWLEDGED" }

    /** Control, expected PASS: the harness delivers a normal order end to end. */
    @Test fun normalOrderIsAcknowledged() {
        val id = UUID.randomUUID().toString()
        controller.accept(id)
        assertTrue(controller.runtime.value, waitFor(15_000) { acked(id) })
    }

    /** M1-01 regression (adapted from OPUS): a failed "연결 확인" leaves the foreground app without a worker. */
    @Test fun failedProbeKeepsDeliveringToConfiguredPos() {
        val closedPort = ServerSocket(0).use { it.localPort }
        val saved = controller.settings.value
        val sequence = controller.connect("127.0.0.1", closedPort.toString())
        assertTrue("failed probe completed", waitFor(10_000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value })
        assertEquals(false, controller.probeResult.value?.succeeded)
        assertEquals(saved, controller.settings.value)
        val id = UUID.randomUUID().toString()
        controller.accept(id)
        assertTrue("must deliver without manual resume: ${controller.runtime.value}", waitFor(15_000) { acked(id) })
        assertEquals(sequence, controller.probeResult.value?.sequence) // diagnostics survive delivery updates
    }

    @Test fun failedProbePreservesUserPause() {
        controller.pause(true)
        assertTrue(waitFor(5000) { controller.settings.value?.userPaused == true && !controller.busy.value })
        val closedPort = ServerSocket(0).use { it.localPort }
        val sequence = controller.connect("127.0.0.1", closedPort.toString())
        assertTrue(waitFor(10000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value })
        assertEquals(false, controller.probeResult.value?.succeeded)
        assertEquals(true, controller.settings.value?.userPaused)
        val id = UUID.randomUUID().toString()
        controller.accept(id)
        assertTrue(waitFor(5000) { controller.orders.value.any { it.requestId == id } && !controller.busy.value })
        pump(700)
        assertEquals("PENDING", controller.orders.value.single { it.requestId == id }.status)
        assertEquals("사용자가 전송을 일시 중지함", controller.runtime.value)
        controller.pause(false)
        assertTrue(waitFor(15000) { acked(id) })
    }

    @Test fun invalidAddressDoesNotStopConfiguredDelivery() {
        val saved = controller.settings.value
        val sequence = controller.connect("127.000.000.001", posPort)
        assertEquals(sequence, controller.probeResult.value?.sequence)
        assertEquals(false, controller.probeResult.value?.succeeded)
        assertEquals(saved, controller.settings.value)
        val id = UUID.randomUUID().toString()
        controller.accept(id)
        assertTrue(waitFor(15000) { acked(id) })
    }

    @Test fun rejectedDatabaseSwitchKeepsPendingOrderAndOriginalDestination() {
        controller.pause(true)
        assertTrue(waitFor(5000) { controller.settings.value?.userPaused == true && !controller.busy.value })
        val saved = controller.settings.value
        val id = UUID.randomUUID().toString()
        controller.accept(id)
        assertTrue(waitFor(5000) { controller.orders.value.any { it.requestId == id } && !controller.busy.value })
        ServerSocket(0).use { other ->
            val peer = thread(isDaemon = true) {
                other.accept().use { socket ->
                    socket.soTimeout = 3000
                    val input = socket.getInputStream()
                    while (true) { val byte = input.read(); if (byte == 10) break; check(byte != -1) }
                    socket.getOutputStream().write(Wire.encode(Message.HelloAck(UUID.randomUUID().toString())))
                }
            }
            val sequence = controller.connect("127.0.0.1", other.localPort.toString())
            assertTrue(waitFor(10000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value })
            assertEquals(false, controller.probeResult.value?.succeeded)
            assertTrue(controller.probeResult.value!!.message.contains("미확인 주문"))
            assertEquals(saved, controller.settings.value)
            assertEquals("PENDING", controller.orders.value.single { it.requestId == id }.status)
            peer.join(3000)
        }
        controller.pause(false)
        assertTrue(waitFor(15000) { acked(id) })
    }

    /** M1-01 regression (adapted from OPUS): a hello that hits the 5 s deadline must be reported. */
    @Test fun probeDeadlineIsReportedNotLeftAsChecking() {
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { silent ->
            thread(isDaemon = true) { runCatching { silent.accept().use { Thread.sleep(9000) } } }
            val started = System.nanoTime()
            val sequence = controller.connect("127.0.0.1", silent.localPort.toString())
            assertTrue("probe must start", waitFor(3_000) { controller.busy.value })
            assertTrue("probe must end", waitFor(9_000) { controller.probeResult.value?.sequence == sequence && !controller.busy.value })
            assertEquals(false, controller.probeResult.value?.succeeded)
            val endedAfterMs = (System.nanoTime() - started) / 1_000_000
            pump(500)
            assertNotEquals("runtime after the hello deadline (probe ended after $endedAfterMs ms)",
                "POS 연결 확인 중", controller.runtime.value)
        }
    }
}
