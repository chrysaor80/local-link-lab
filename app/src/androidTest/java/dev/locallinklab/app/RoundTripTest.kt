package dev.locallinklab.app

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Host POS must run on port 8765. This is emulator NAT, not a physical LAN test. */
class RoundTripTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun uiToRoomToTcpToPosAndBack() {
        val app = compose.activity.application as LinkApplication
        compose.onNodeWithTag("host").performTextReplacement("10.0.2.2")
        compose.onNodeWithTag("connect").performClick()
        compose.waitUntil(15000) { app.controller.settings.value != null && !app.controller.busy.value }
        // Capture intent BEFORE acceptance, independent of the eventual Room/POS contents.
        val draftText = compose.onNodeWithText("접수 ID:", substring = true).fetchSemanticsNode()
            .config[SemanticsProperties.Text].single().text
        val expectedId = draftText.removePrefix("접수 ID: ")
        val expectedDb = checkNotNull(app.controller.settings.value).posDbId
        val baseline = JSONObject().put("request_id", expectedId).put("pos_db_id", expectedDb)
            .put("item_code", "DEMO_COFFEE").put("quantity", 1).put("unit_price_krw", 3000)
        InstrumentationRegistry.getInstrumentation().targetContext.filesDir.resolve("m1-baseline.json").writeText(baseline.toString())
        compose.onNodeWithTag("accept").performClick()
        compose.waitUntil(20000) { app.controller.orders.value.any { it.requestId == expectedId && it.status == "ACKNOWLEDGED" } }
        compose.onNodeWithTag("status-$expectedId").performScrollTo().assertTextEquals("POS 저장 확인")
        val row = runBlocking { app.controller.repository.dao.order(expectedId) }!!
        assertEquals(expectedDb, row.posDbId)
        assertEquals("DEMO_COFFEE", row.itemCode)
        assertEquals(1, row.quantity)
        assertEquals(3000L, row.unitPriceKrw)
        assertNotNull(row.receiptId)
        InstrumentationRegistry.getInstrumentation().targetContext.filesDir.resolve("m1-result.json")
            .writeText(JSONObject(baseline.toString()).put("receipt_id", row.receiptId).put("status", row.status).toString())
    }
}
