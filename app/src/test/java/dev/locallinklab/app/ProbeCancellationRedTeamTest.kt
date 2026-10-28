package dev.locallinklab.app

import android.app.Application
import android.os.Looper
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
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
 * M2 red-team regression written by the reviewer against 127ea32 (expected PASS).
 * Same harness as ControllerRobolectricTest: real Controller/Room/TcpTransport + POS on 127.0.0.1:18765.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class ProbeCancellationRedTeamTest {
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
        assertTrue("initial probe completed", waitFor(30_000) {
            controller.probeResult.value?.sequence == sequence && controller.settings.value != null && !controller.busy.value
        })
    }

    @After fun tearDown() {
        controller.close()
        pump(300)
        db.close()
    }

    private fun step() { shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20)); Thread.sleep(20) }
    private fun pump(ms: Long) { val end = System.nanoTime() + ms * 1_000_000; while (System.nanoTime() < end) step() }
    private fun waitFor(ms: Long, condition: () -> Boolean): Boolean {
        val end = System.nanoTime() + ms * 1_000_000
        while (System.nanoTime() < end) { if (condition()) return true; step() }
        return condition()
    }

    /** A probe cancelled by ON_STOP publishes no result, keeps settings, sends nothing until ON_START. */
    @Test fun backgroundDuringProbePublishesNothingAndDoesNotDeliver() {
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { silent ->
            thread(isDaemon = true) { runCatching { silent.accept().use { Thread.sleep(9000) } } }
            val before = controller.probeResult.value
            val saved = controller.settings.value
            val sequence = controller.connect("127.0.0.1", silent.localPort.toString())
            assertTrue("probe must start", waitFor(3_000) { controller.busy.value })
            controller.onStop(owner)
            assertTrue("probe must stop", waitFor(3_000) { !controller.busy.value })
            pump(6_000) // past the cancelled probe's own 5 s deadline
            assertEquals("a cancelled probe must not publish a result", before, controller.probeResult.value)
            assertNotEquals(sequence, controller.probeResult.value?.sequence)
            assertEquals(saved, controller.settings.value)
            assertEquals("백그라운드 · 전송 중지", controller.runtime.value)
            val id = UUID.randomUUID().toString()
            controller.accept(id)
            assertTrue(waitFor(5_000) { controller.orders.value.any { it.requestId == id } && !controller.busy.value })
            pump(1_500)
            assertEquals("no delivery while stopped", "PENDING", controller.orders.value.single { it.requestId == id }.status)
            controller.onStart(owner)
            assertTrue("delivery resumes on ON_START", waitFor(15_000) {
                controller.orders.value.single { it.requestId == id }.status == "ACKNOWLEDGED"
            })
        }
    }
}
