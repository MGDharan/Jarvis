package com.jarvis.remote.ui.theme

import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color

// Core Sci-Fi Dark Palette
val JarvisBackground = Color(0xFF000814)
val JarvisBackgroundDark = Color(0xFF00040A)
val JarvisSurface = Color(0xFF0A192F)
val JarvisSurfaceLight = Color(0xFF132F4C)
val JarvisSurfaceCard = Color(0xCC0D2137)
val JarvisBorder = Color(0xFF1B3A5B)
val JarvisBorderGlow = Color(0x6600E5FF)

// Holographic Accents
val JarvisCyan = Color(0xFF00E5FF)
val JarvisCyanBright = Color(0xFF80F3FF)
val JarvisCyanDark = Color(0xFF0077B6)
val JarvisBlueElectric = Color(0xFF0051FF)
val JarvisPurpleHolo = Color(0xFF7B2CBF)
val JarvisArcOrange = Color(0xFFFF9100)

// Status & Indicators
val JarvisOnline = Color(0xFF00FF66)
val JarvisWarning = Color(0xFFFFD600)
val JarvisDanger = Color(0xFFFF1744)

// Typography & Text
val JarvisText = Color(0xFFE0F7FA)
val JarvisTextDim = Color(0xFF80DEEA)
val JarvisTextMuted = Color(0xFF4A7C8A)

// Gradients
val HologramGlowGradient = Brush.radialGradient(
    colors = listOf(JarvisCyan.copy(alpha = 0.45f), JarvisCyanDark.copy(alpha = 0.15f), Color.Transparent)
)

val GlassCardGradient = Brush.verticalGradient(
    colors = listOf(JarvisSurfaceCard, JarvisSurface)
)

val NeonCyanGradient = Brush.horizontalGradient(
    colors = listOf(JarvisCyan, JarvisBlueElectric)
)

val WarningAlertGradient = Brush.horizontalGradient(
    colors = listOf(JarvisWarning, JarvisArcOrange)
)
