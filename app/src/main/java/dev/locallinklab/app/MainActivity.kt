package dev.locallinklab.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.util.UUID

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val controller = (application as LinkApplication).controller
        setContent { MaterialTheme { Surface(Modifier.fillMaxSize()) { LinkScreen(controller) } } }
    }
}

@Composable
private fun LinkScreen(controller: LinkController) {
    val orders by controller.orders.collectAsStateWithLifecycle()
    val settings by controller.settings.collectAsStateWithLifecycle()
    val runtime by controller.runtime.collectAsStateWithLifecycle()
    val busy by controller.busy.collectAsStateWithLifecycle()
    val probe by controller.probeResult.collectAsStateWithLifecycle()
    var host by rememberSaveable { mutableStateOf("") }
    var port by rememberSaveable { mutableStateOf("8765") }
    var draft by rememberSaveable { mutableStateOf(UUID.randomUUID().toString()) }
    LaunchedEffect(settings?.host, settings?.port) {
        settings?.let { host = it.host; port = it.port.toString() }
    }
    LazyColumn(Modifier.fillMaxSize().safeDrawingPadding().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Local Link Lab", style = MaterialTheme.typography.headlineMedium) }
        item { Text("연결이 끊겨도 주문을 보관하는 실험 · 실제 결제 없음") }
        item {
            OutlinedTextField(host, { host = it }, label = { Text("POS IPv4 주소") }, singleLine = true,
                enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("host"))
            OutlinedTextField(port, { port = it }, label = { Text("포트") }, singleLine = true,
                enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("port"))
            Button({ controller.connect(host, port) }, enabled = !busy, modifier = Modifier.testTag("connect")) { Text("연결 확인") }
            settings?.let { Text("확인된 POS: ${it.host}:${it.port}", Modifier.testTag("configured")) }
            probe?.takeIf { !it.succeeded }?.let { Text(it.message, Modifier.testTag("probe-error")) }
            Text(runtime, Modifier.testTag("runtime"))
        }
        item {
            Text("샘플 커피 1개 · 3,000원", style = MaterialTheme.typography.titleMedium)
            Text("접수 ID: $draft", style = MaterialTheme.typography.bodySmall)
            Button({ controller.accept(draft) }, enabled = !busy && settings != null && orders.none { it.requestId == draft },
                modifier = Modifier.testTag("accept")) { Text("기기에 주문 접수") }
            TextButton({ draft = UUID.randomUUID().toString() }, enabled = !busy && orders.any { it.requestId == draft },
                modifier = Modifier.testTag("new-draft")) { Text("새 주문 준비") }
            Row {
                TextButton({ controller.pause(true) }, enabled = !busy && settings != null) { Text("전송 일시 중지") }
                TextButton({ controller.pause(false) }, enabled = !busy && settings != null, modifier = Modifier.testTag("resume")) { Text("전송 재개") }
            }
        }
        item { Text("기기에 저장된 주문 ${orders.size}건", style = MaterialTheme.typography.titleMedium) }
        items(orders, key = { it.requestId }) { order ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(when (order.status) {
                        "ACKNOWLEDGED" -> "POS 저장 확인"
                        "NEEDS_ATTENTION" -> "확인 필요"
                        else -> "기기에 접수됨 · POS 확인 대기"
                    }, Modifier.testTag("status-${order.requestId}"))
                    Text(order.requestId, style = MaterialTheme.typography.bodySmall)
                    Text("${order.itemCode} × ${order.quantity} · ${order.unitPriceKrw}원")
                    order.receiptId?.let { Text("영수증: $it", style = MaterialTheme.typography.bodySmall) }
                    order.reason?.let { Text(it) }
                    if (order.status == "NEEDS_ATTENTION") TextButton({ controller.recheck(order.requestId) }, enabled = !busy) { Text("같은 주문 다시 확인") }
                }
            }
        }
    }
}
