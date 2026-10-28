package dev.locallinklab.app

import androidx.room.Room
import androidx.room.withTransaction
import androidx.test.platform.app.InstrumentationRegistry
import dev.locallinklab.core.Endpoint
import dev.locallinklab.core.Order
import kotlinx.coroutines.runBlocking
import org.junit.*
import org.junit.Assert.*
import java.util.UUID

class RepositoryTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val name = "test-${UUID.randomUUID()}.db"
    private val dbId = UUID.randomUUID().toString()
    private lateinit var db: LinkDatabase
    private lateinit var repo: Repository
    private fun open() {
        db = Room.databaseBuilder(context, LinkDatabase::class.java, name).build()
        repo = Repository(db)
    }
    @Before fun setup() = runBlocking { open(); repo.configure(Endpoint("127.0.0.1", 8765), dbId) }
    @After fun cleanup() { db.close(); context.deleteDatabase(name) }

    @Test fun duplicateDraftAndDatabaseSwitchRules() = runBlocking {
        val id = UUID.randomUUID().toString()
        val order = Order("TEST", 1, 3000)
        repo.accept(id, order); repo.accept(id, order)
        assertEquals(1, repo.dao.unresolved())
        assertTrue(runCatching { repo.accept(id, order.copy(quantity = 2)) }.isFailure)
        repo.configure(Endpoint("192.168.1.123", 8766), dbId)
        assertEquals("192.168.1.123", repo.dao.settings()!!.host)
        assertTrue(runCatching { repo.configure(Endpoint("127.0.0.1", 8765), UUID.randomUUID().toString()) }.isFailure)
        assertEquals(dbId, repo.dao.settings()!!.posDbId)
        assertEquals(order, repo.dao.order(id)!!.pending().order)
    }
    @Test fun capacityRefusesNewOrderAndRetainsEveryAcceptedId() = runBlocking {
        val accepted = List(1000) { UUID.randomUUID().toString() }
        db.withTransaction {
            accepted.forEach { repo.dao.insert(OrderRow(requestId = it, posDbId = dbId, itemCode = "TEST", quantity = 1, unitPriceKrw = 1)) }
        }
        val refused = UUID.randomUUID().toString()
        assertTrue(runCatching { repo.accept(refused, Order("TEST", 1, 1)) }.isFailure)
        assertNull(repo.dao.order(refused))
        assertEquals(1000, repo.dao.unresolved())
        accepted.forEach { assertNotNull(repo.dao.order(it)) }
    }
    @Test fun reopeningDatabasePreservesPauseAndOrderStates() = runBlocking {
        val pending = UUID.randomUUID().toString()
        val acked = UUID.randomUUID().toString()
        val receipt = UUID.randomUUID().toString()
        repo.accept(pending, Order("TEST", 1, 1)); repo.accept(acked, Order("TEST", 1, 1))
        repo.acknowledge(acked, receipt); repo.dao.pause(true)
        db.close(); open()
        assertTrue(repo.dao.settings()!!.userPaused)
        assertEquals(pending, repo.nextPending()!!.requestId)
        assertEquals("ACKNOWLEDGED", repo.dao.order(acked)!!.status)
        assertEquals(receipt, repo.dao.order(acked)!!.receiptId)
        // Reopening Room proves persisted state, not Android process-death recovery.
    }
}
