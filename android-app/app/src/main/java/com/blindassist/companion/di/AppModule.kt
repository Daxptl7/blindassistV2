package com.blindassist.companion.di

import com.blindassist.companion.data.UnavailableDeviceRepository
import com.blindassist.companion.domain.DeviceRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent

@Module
@InstallIn(SingletonComponent::class)
abstract class AppModule {
    @Binds abstract fun bindDeviceRepository(impl: UnavailableDeviceRepository): DeviceRepository
}
