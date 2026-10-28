package dev.locallinklab.app

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.room.Room
import dev.locallinklab.core.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*

class LinkApplication : Application() {
    lateinit var controller: LinkController
        private set
    override fun onCreate() {
        super.onCreate()
        val database = Room.databaseBuilder(this, LinkDatabase::class.java, "local-link.db").build()
        controller = LinkController(Repository(database))
        ProcessLifecycleOwner.get().lifecycle.addObserver(controller)
    }
}

private data class RunRequest(val revision: Long = 0, val foreground: Boolean = false, val probe: Endpoint? = null)

/** One process-scoped owner. collectLatest cancels and joins the old socket worker before starting another. */
class LinkController(val repository: Repository) : DefaultLifecycleObserver {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val transport = TcpTransport()
    private val request = MutableStateFlow(RunRequest())
    private val wake = Channel<Unit>(Channel.CONFLATED)
    private val _runtime = MutableStateFlow("백그라운드 · 전송 중지")
    val runtime = _runtime.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy = _busy.asStateFlow()
    val orders = repository.dao.observeOrders().stateIn(scope, SharingStarted.Eagerly, emptyList())
    val settings = repository.dao.observeSettings().stateIn(scope, SharingStarted.Eagerly, null)

    init {
        scope.launch {
            request.collectLatest { run ->
                if (!run.foreground) { _runtime.value = "백그라운드 · 전송 중지"; return@collectLatest }
                try {
                    if (run.probe != null) {
                        _busy.value = true
                        _runtime.value = "POS 연결 확인 중"
                        val reply = transport.exchange(run.probe, Message.Hello) as? Message.HelloAck
                            ?: throw WireException("POS 식별 응답이 아닙니다.")
                        repository.configure(run.probe, reply.dbId)
                        _runtime.value = "POS 연결 확인됨"
                        restart()
                        return@collectLatest
                    }
                    val config = repository.dao.settings() ?: run {
                        _runtime.value = "POS 주소를 입력하고 연결을 확인하세요."
                        return@collectLatest
                    }
                    if (config.userPaused) { _runtime.value = "사용자가 전송을 일시 중지함"; return@collectLatest }
                    while (true) {
                        when (DeliveryEngine(repository, transport).drain(Endpoint(config.host, config.port)) { _runtime.value = it }) {
                            StopReason.EMPTY -> { _runtime.value = "대기 중"; wake.receive() }
                            StopReason.RETRY_LIMIT -> { _runtime.value = "재시도 한도 · 전송 재개를 눌러 확인하세요."; return@collectLatest }
                            StopReason.POS_MISMATCH -> { _runtime.value = "다른 POS DB입니다. 원래 POS 주소를 확인하세요."; return@collectLatest }
                        }
                    }
                } catch (e: CancellationException) { throw e
                } catch (e: Exception) { _runtime.value = "확인 필요: ${e.message ?: e.javaClass.simpleName}"
                } finally { _busy.value = false }
            }
        }
    }
    private fun restart(probe: Endpoint? = null, foreground: Boolean = request.value.foreground) {
        request.value = RunRequest(request.value.revision + 1, foreground, probe)
    }
    override fun onStart(owner: LifecycleOwner) = restart(foreground = true)
    override fun onStop(owner: LifecycleOwner) = restart(foreground = false)
    fun connect(host: String, port: String) {
        val number = port.toIntOrNull()
        if (number == null || number !in 1..65535) { _runtime.value = "포트는 1~65535를 입력하세요."; return }
        restart(Endpoint(host.trim(), number))
    }
    fun accept(id: String) = action {
        repository.accept(id, Order("DEMO_COFFEE", 1, 3000))
        wake.trySend(Unit)
    }
    fun pause(paused: Boolean) = action {
        repository.dao.pause(paused)
        restart()
    }
    fun recheck(id: String) = action {
        repository.dao.recheck(id)
        wake.trySend(Unit)
    }
    private fun action(block: suspend () -> Unit) {
        if (_busy.value) return
        _busy.value = true
        scope.launch {
            try { block() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { _runtime.value = "접수/설정 실패: ${e.message ?: e.javaClass.simpleName}" }
            finally { _busy.value = false }
        }
    }
}
