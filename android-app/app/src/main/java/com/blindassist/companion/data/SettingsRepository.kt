package com.blindassist.companion.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore by preferencesDataStore(name = "blindassist_settings")

enum class Appearance { SYSTEM, LIGHT, DARK }
enum class AppLanguage(val languageTag: String) {
    ENGLISH("en"), HINDI("hi"), GUJARATI("gu")
}

data class AppSettings(
    val onboardingComplete: Boolean = false,
    val appearance: Appearance = Appearance.SYSTEM,
    val language: AppLanguage = AppLanguage.ENGLISH
)

@Singleton
class SettingsRepository @Inject constructor(@ApplicationContext private val context: Context) {
    private object Keys {
        val ONBOARDING = booleanPreferencesKey("onboarding_complete")
        val APPEARANCE = stringPreferencesKey("appearance")
        val LANGUAGE = stringPreferencesKey("language")
    }

    val settings: Flow<AppSettings> = context.settingsDataStore.data
        .catch { if (it is IOException) emit(androidx.datastore.preferences.core.emptyPreferences()) else throw it }
        .map { values ->
            AppSettings(
                onboardingComplete = values[Keys.ONBOARDING] ?: false,
                appearance = enumValues<Appearance>().firstOrNull {
                    it.name == values[Keys.APPEARANCE]
                } ?: Appearance.SYSTEM,
                language = enumValues<AppLanguage>().firstOrNull {
                    it.name == values[Keys.LANGUAGE]
                } ?: AppLanguage.ENGLISH
            )
        }

    suspend fun completeOnboarding() {
        context.settingsDataStore.edit { it[Keys.ONBOARDING] = true }
    }

    suspend fun setAppearance(value: Appearance) {
        context.settingsDataStore.edit { it[Keys.APPEARANCE] = value.name }
    }

    suspend fun setLanguage(value: AppLanguage) {
        context.settingsDataStore.edit { it[Keys.LANGUAGE] = value.name }
    }
}
