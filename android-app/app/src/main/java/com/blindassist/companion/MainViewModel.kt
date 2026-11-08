package com.blindassist.companion

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.blindassist.companion.data.AppLanguage
import com.blindassist.companion.data.Appearance
import com.blindassist.companion.data.AppSettings
import com.blindassist.companion.data.SettingsRepository
import com.blindassist.companion.domain.DeviceConnectionState
import com.blindassist.companion.domain.DeviceRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    deviceRepository: DeviceRepository
) : ViewModel() {
    val settings: StateFlow<AppSettings?> = settingsRepository.settings
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val device: StateFlow<DeviceConnectionState> = deviceRepository.connectionState
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DeviceConnectionState.Unavailable)

    fun finishOnboarding() = viewModelScope.launch { settingsRepository.completeOnboarding() }
    fun setAppearance(value: Appearance) = viewModelScope.launch { settingsRepository.setAppearance(value) }
    fun setLanguage(value: AppLanguage) = viewModelScope.launch { settingsRepository.setLanguage(value) }
}
