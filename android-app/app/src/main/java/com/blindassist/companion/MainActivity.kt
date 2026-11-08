package com.blindassist.companion

import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RectangleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.blindassist.companion.data.AppLanguage
import com.blindassist.companion.data.AppSettings
import com.blindassist.companion.data.Appearance
import com.blindassist.companion.domain.DeviceConnectionState
import dagger.hilt.android.AndroidEntryPoint
import java.util.Locale

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { BlindAssistApp() }
    }
}

@Composable
private fun localized(id: Int, lang: AppLanguage): String {
    val context = LocalContext.current
    return remember(context, id, lang) {
        val config = Configuration(context.resources.configuration)
        config.setLocale(Locale.forLanguageTag(lang.languageTag))
        context.createConfigurationContext(config).getString(id)
    }
}

private val darkColors = darkColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF8DBBFF),
    background = androidx.compose.ui.graphics.Color(0xFF121212),
    surface = androidx.compose.ui.graphics.Color(0xFF1E1E1E)
)
private val lightColors = lightColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF194F90),
    background = androidx.compose.ui.graphics.Color.White,
    surface = androidx.compose.ui.graphics.Color(0xFFF5F5F5)
)

@Composable
fun BlindAssistApp(viewModel: MainViewModel = hiltViewModel()) {
    val settings by viewModel.settings.collectAsStateWithLifecycle()
    val device by viewModel.device.collectAsStateWithLifecycle()
    val actualSettings = settings
    if (actualSettings == null) {
        MaterialTheme { Box(Modifier.fillMaxSize(), contentAlignment = androidx.compose.ui.Alignment.Center) { CircularProgressIndicator() } }
        return
    }

    val dark = when (actualSettings.appearance) {
        Appearance.DARK -> true
        Appearance.LIGHT -> false
        Appearance.SYSTEM -> androidx.compose.foundation.isSystemInDarkTheme()
    }
    MaterialTheme(colorScheme = if (dark) darkColors else lightColors) {
        Surface(modifier = Modifier.fillMaxSize()) {
            if (!actualSettings.onboardingComplete) {
                OnboardingScreen(actualSettings.language, viewModel::finishOnboarding)
            } else {
                MainNavigation(actualSettings, device, viewModel)
            }
        }
    }
}

@Composable
private fun PageTitle(text: String) {
    Text(text, style = MaterialTheme.typography.headlineMedium,
        fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
}

@Composable
private fun ActionButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(onClick = onClick, modifier = modifier.fillMaxWidth().heightIn(min = 52.dp),
        shape = RectangleShape, enabled = enabled) {
        Text(label)
    }
}

@Composable
private fun OnboardingScreen(lang: AppLanguage, onStart: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Spacer(Modifier.height(48.dp))
        PageTitle(localized(R.string.app_name, lang))
        Text(localized(R.string.welcome_message, lang), style = MaterialTheme.typography.bodyLarge)
        Text(localized(R.string.offline_explanation, lang), style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.weight(1f, fill = false))
        ActionButton(localized(R.string.get_started, lang), onStart)
    }
}

private data class Page(val route: String, val label: Int)
private val pages = listOf(
    Page("home", R.string.home),
    Page("devices", R.string.devices),
    Page("features", R.string.features),
    Page("settings", R.string.settings)
)

@Composable
private fun MainNavigation(settings: AppSettings, device: DeviceConnectionState, vm: MainViewModel) {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    Scaffold(
        bottomBar = {
            NavigationBar {
                pages.forEach { page ->
                    NavigationBarItem(
                        selected = route == page.route,
                        onClick = {
                            nav.navigate(page.route) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Text("•") },
                        label = { Text(localized(page.label, settings.language)) },
                        alwaysShowLabel = true
                    )
                }
            }
        }
    ) { insets ->
        NavHost(navController = nav, startDestination = "home",
            modifier = Modifier.padding(insets)) {
            composable("home") {
                BasicPage {
                    PageTitle(localized(R.string.home, settings.language))
                    Text(localized(R.string.device_not_connected, settings.language))
                    Text(localized(R.string.welcome_message, settings.language))
                    ActionButton(localized(R.string.devices, settings.language)) {
                        nav.navigate("devices") { launchSingleTop = true }
                    }
                }
            }
            composable("devices") {
                BasicPage {
                    PageTitle(localized(R.string.devices, settings.language))
                    Text(localized(R.string.device_not_connected, settings.language))
                    Text(localized(R.string.connection_coming, settings.language))
                    Text(localized(R.string.transport_unavailable, settings.language))
                }
            }
            composable("features") {
                BasicPage {
                    PageTitle(localized(R.string.features, settings.language))
                    Text(localized(R.string.features_info, settings.language))
                    listOf(
                        R.string.feature_ocr, R.string.feature_morse, R.string.feature_voice,
                        R.string.feature_translation, R.string.feature_gesture, R.string.feature_object,
                        R.string.feature_gps, R.string.feature_confidential, R.string.feature_math
                    ).forEach { id ->
                        HorizontalDivider()
                        Text(localized(id, settings.language), fontWeight = FontWeight.SemiBold)
                        Text(localized(R.string.remote_unavailable, settings.language),
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            composable("settings") {
                BasicPage {
                    PageTitle(localized(R.string.settings, settings.language))
                    Text(localized(R.string.appearance, settings.language), fontWeight = FontWeight.SemiBold)
                    Appearance.entries.forEach { appearance ->
                        ChoiceRow(
                            label = when (appearance) {
                                Appearance.SYSTEM -> localized(R.string.system, settings.language)
                                Appearance.LIGHT -> localized(R.string.light, settings.language)
                                Appearance.DARK -> localized(R.string.dark, settings.language)
                            },
                            selected = settings.appearance == appearance,
                            onClick = { vm.setAppearance(appearance) }
                        )
                    }
                    HorizontalDivider()
                    Text(localized(R.string.language, settings.language), fontWeight = FontWeight.SemiBold)
                    AppLanguage.entries.forEach { language ->
                        ChoiceRow(
                            label = when (language) {
                                AppLanguage.ENGLISH -> "English"
                                AppLanguage.HINDI -> "हिन्दी"
                                AppLanguage.GUJARATI -> "ગુજરાતી"
                            },
                            selected = settings.language == language,
                            onClick = { vm.setLanguage(language) }
                        )
                    }
                    HorizontalDivider()
                    ActionButton(localized(R.string.about, settings.language)) { nav.navigate("about") }
                }
            }
            composable("about") {
                BasicPage {
                    PageTitle(localized(R.string.about, settings.language))
                    Text(localized(R.string.about_content, settings.language))
                    ActionButton(localized(R.string.back, settings.language)) { nav.popBackStack() }
                }
            }
        }
    }
}

@Composable
private fun BasicPage(content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        content = content
    )
}

@Composable
private fun ChoiceRow(label: String, selected: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
        shape = RectangleShape,
        color = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface
    ) {
        Row(Modifier.padding(14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, modifier = Modifier.weight(1f))
            Text(if (selected) "✓" else "", style = MaterialTheme.typography.bodyLarge)
        }
    }
}
