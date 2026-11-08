package com.blindassist.companion.data

import com.blindassist.companion.domain.DeviceCapability
import com.blindassist.companion.domain.DeviceConnectionState
import com.blindassist.companion.domain.DeviceRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import javax.inject.Inject

/** Phase 3 deliberately provides no simulated or live connection. */
class UnavailableDeviceRepository @Inject constructor() : DeviceRepository {
    override val connectionState: Flow<DeviceConnectionState> =
        flowOf(DeviceConnectionState.Unavailable)

    override suspend fun capabilities(): List<DeviceCapability> = emptyList()
}
