package dev.locallinklab.app

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import java.util.UUID

/** Instrumentation never opens the demo/user outbox, even on a reused physical device. */
class IsolatedTestApplication : LinkApplication() {
    override fun databaseName(): String = "instrumented-${UUID.randomUUID()}.db"
}

class LabTestRunner : AndroidJUnitRunner() {
    override fun newApplication(cl: ClassLoader, className: String, context: Context): Application =
        super.newApplication(cl, IsolatedTestApplication::class.java.name, context)
}
