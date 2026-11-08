package com.blindassist.companion

import com.blindassist.companion.domain.DeviceConnectionState
import org.junit.Assert.*
import org.junit.Test

class DeviceModelsTest {
    @Test fun unavailableIsDistinctFromDisconnected() {
        assertNotEquals(DeviceConnectionState.Unavailable, DeviceConnectionState.Disconnected)
    }

    @Test fun connectedContainsNameButIsNeverDefault() {
        val state = DeviceConnectionState.Connected("Test terminal")
        assertEquals("Test terminal", state.deviceName)
        assertNotEquals(DeviceConnectionState.Unavailable, state)
    }
}
