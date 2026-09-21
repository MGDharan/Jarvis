package com.jarvis.remote.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = JarvisCyan,
    secondary = JarvisCyanDark,
    background = JarvisBackground,
    surface = JarvisSurface,
    onPrimary = JarvisBackground,
    onSecondary = JarvisText,
    onBackground = JarvisText,
    onSurface = JarvisText,
)

@Composable
fun JarvisRemoteTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
