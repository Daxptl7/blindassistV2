package com.blindassist.companion.domain

import kotlinx.coroutines.flow.Flow

sealed interface DeviceConnectionState {
    data object Unavailable : DeviceConnectionState
    data object Disconnected : DeviceConnectionState
    data object Connecting : DeviceConnectionState
    data class Connected(val deviceName: String) : DeviceConnectionState
    data class Error(val description: String) : DeviceConnectionState
}

data class DeviceCapability(
    val identifier: String,
    val title: String,
    val available: Boolean
)

interface DeviceRepository {
    val connectionState: Flow<DeviceConnectionState>
    suspend fun capabilities(): List<DeviceCapability>
}
