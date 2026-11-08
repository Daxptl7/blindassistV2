package com.blindassist.companion

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OnboardingTest {
    @get:Rule val rule = createAndroidComposeRule<MainActivity>()

    @Test fun appOpensWithoutConnectedDevice() {
        // Depending on persisted settings, onboarding or the dashboard is displayed.
        rule.waitForIdle()
        rule.onRoot().assertIsDisplayed()
    }
}
