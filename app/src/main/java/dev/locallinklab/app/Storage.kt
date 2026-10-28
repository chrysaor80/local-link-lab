package dev.locallinklab.app

import androidx.room.*
import dev.locallinklab.core.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "orders", indices = [Index(value = ["requestId"], unique = true)])
data class OrderRow(
    @PrimaryKey(autoGenerate = true) val sequence: Long = 0,
    val requestId: String,
    val posDbId: String,
    val itemCode: String,
    val quantity: Int,
    val unitPriceKrw: Long,
    val status: String = "PENDING",
    val receiptId: String? = null,
    val reason: String? = null,
) {
    fun pending() = PendingOrder(requestId, posDbId, Order(itemCode, quantity, unitPriceKrw))
}

@Entity(tableName = "settings")
data class SettingsRow(
    @PrimaryKey val singleton: Int = 1,
    val host: String,
    val port: Int,
    val posDbId: String,
    val userPaused: Boolean = false,
)

@Dao
interface LinkDao {
    @Query("SELECT * FROM orders ORDER BY sequence DESC") fun observeOrders(): Flow<List<OrderRow>>
    @Query("SELECT * FROM settings WHERE singleton = 1") fun observeSettings(): Flow<SettingsRow?>
    @Query("SELECT * FROM settings WHERE singleton = 1") suspend fun settings(): SettingsRow?
    @Query("SELECT * FROM orders WHERE requestId = :id") suspend fun order(id: String): OrderRow?
    @Query("SELECT COUNT(*) FROM orders WHERE status != 'ACKNOWLEDGED'") suspend fun unresolved(): Int
    @Query("SELECT * FROM orders WHERE status = 'PENDING' ORDER BY sequence LIMIT 1") suspend fun next(): OrderRow?
    @Insert suspend fun insert(row: OrderRow)
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun configure(row: SettingsRow)
    @Query("UPDATE settings SET userPaused = :paused WHERE singleton = 1") suspend fun pause(paused: Boolean)
    @Query("UPDATE orders SET status = 'ACKNOWLEDGED', receiptId = :receipt, reason = NULL WHERE requestId = :id AND status = 'PENDING'")
    suspend fun acknowledge(id: String, receipt: String): Int
    @Query("UPDATE orders SET status = 'NEEDS_ATTENTION', reason = :reason WHERE requestId = :id AND status = 'PENDING'")
    suspend fun attention(id: String, reason: String): Int
    @Query("UPDATE orders SET status = 'PENDING', reason = NULL WHERE requestId = :id AND status = 'NEEDS_ATTENTION'")
    suspend fun recheck(id: String)
}

@Database(entities = [OrderRow::class, SettingsRow::class], version = 1, exportSchema = true)
abstract class LinkDatabase : RoomDatabase() { abstract fun dao(): LinkDao }

class Repository(private val db: LinkDatabase) : Outbox {
    val dao = db.dao()
    suspend fun configure(endpoint: Endpoint, dbId: String) = db.withTransaction {
        val old = dao.settings()
        check(old == null || old.posDbId == dbId || dao.unresolved() == 0) {
            "미확인 주문이 있어 다른 POS DB로 변경할 수 없습니다. 기존 POS를 연결하세요."
        }
        dao.configure(SettingsRow(host = endpoint.host, port = endpoint.port, posDbId = dbId, userPaused = old?.userPaused ?: false))
    }
    suspend fun accept(id: String, order: Order) = db.withTransaction {
        require(Wire.validUuid(id))
        val old = dao.order(id)
        if (old != null) {
            check(old.pending().order == order) { "동일 요청 ID의 주문 내용이 다릅니다." }
            return@withTransaction
        }
        val settings = checkNotNull(dao.settings()) { "처음에는 POS 연결을 확인하세요." }
        // Validate before any insertion; the same ID and body survive uncertain commit retries.
        Wire.encode(Message.Submit(PendingOrder(id, settings.posDbId, order)))
        check(dao.unresolved() < 1000) { "미확인 주문이 1,000건입니다. 기존 주문을 확인한 뒤 다시 접수하세요." }
        dao.insert(OrderRow(requestId = id, posDbId = settings.posDbId, itemCode = order.itemCode,
            quantity = order.quantity, unitPriceKrw = order.unitPriceKrw))
    }
    override suspend fun nextPending() = dao.next()?.pending()
    override suspend fun acknowledge(requestId: String, receiptId: String) {
        check(dao.acknowledge(requestId, receiptId) == 1) { "Local ACK was not committed" }
    }
    override suspend fun needsAttention(requestId: String, reason: String) {
        check(dao.attention(requestId, reason) == 1) { "Local attention state was not committed" }
    }
}
