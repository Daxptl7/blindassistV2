package com.blindassist.companion

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.widget.FrameLayout

/** Phase 0 blank activity. Companion features belong to later phases. */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(FrameLayout(this).apply { setBackgroundColor(Color.WHITE) })
    }
}
