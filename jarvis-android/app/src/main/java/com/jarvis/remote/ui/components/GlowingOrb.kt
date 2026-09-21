package com.jarvis.remote.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.jarvis.remote.ui.theme.*
import com.jarvis.remote.ui.viewmodel.OrbVisualState
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun GlowingOrb(
    visualState: OrbVisualState,
    audioRms: Float = 0f,
    modifier: Modifier = Modifier,
    size: Dp = 180.dp
) {
    val isListening = visualState == OrbVisualState.LISTENING
    val isProcessing = visualState == OrbVisualState.PROCESSING
    val isSpeaking = visualState == OrbVisualState.SPEAKING

    val infiniteTransition = rememberInfiniteTransition(label = "OrbPulse")

    // Breathing pulse speed
    val pulseDuration = when (visualState) {
        OrbVisualState.LISTENING -> 550
        OrbVisualState.PROCESSING -> 350
        OrbVisualState.SPEAKING -> 450
        OrbVisualState.IDLE -> 2200
    }

    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.90f,
        targetValue = 1.10f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = pulseDuration, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "OrbPulseScale"
    )

    // Clockwise ring rotation
    val rotationSpeed = if (isProcessing) 2500 else 14000
    val rotationAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = rotationSpeed, easing = LinearEasing)
        ),
        label = "OrbRotation"
    )

    // Counter-clockwise outer ring rotation
    val counterRotationAngle by infiniteTransition.animateFloat(
        initialValue = 360f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = if (isProcessing) 3500 else 18000, easing = LinearEasing)
        ),
        label = "OrbCounterRotation"
    )

    // Dynamic reactivity from microphone RMS
    val dynamicBoost = if (isListening) (audioRms.coerceIn(0f, 10f) / 10f) * 0.30f else 0f
    val currentScale = pulseScale + dynamicBoost

    // Dynamic accent color based on state
    val coreColor = when (visualState) {
        OrbVisualState.LISTENING -> JarvisCyanBright
        OrbVisualState.PROCESSING -> JarvisPurpleHolo
        OrbVisualState.SPEAKING -> JarvisArcOrange
        OrbVisualState.IDLE -> JarvisCyan
    }

    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.size(size)) {
            val center = Offset(this.size.width / 2, this.size.height / 2)
            val radius = (this.size.minDimension / 2) * currentScale

            // 1. Outermost Ambient Halo
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        coreColor.copy(alpha = if (isListening || isSpeaking) 0.45f else 0.18f),
                        Color.Transparent
                    ),
                    center = center,
                    radius = radius * 1.35f
                ),
                radius = radius * 1.35f,
                center = center
            )

            // 2. Outer Segmented HUD Ring (Counter-rotating)
            rotate(degrees = counterRotationAngle, pivot = center) {
                val outerRadius = radius * 0.96f
                val strokeWidth = 2.dp.toPx()
                // Draw 4 distinct HUD arcs
                for (i in 0 until 4) {
                    val startAngle = i * 90f + 10f
                    drawArc(
                        color = coreColor.copy(alpha = 0.5f),
                        startAngle = startAngle,
                        sweepAngle = 70f,
                        useCenter = false,
                        topLeft = Offset(center.x - outerRadius, center.y - outerRadius),
                        size = androidx.compose.ui.geometry.Size(outerRadius * 2, outerRadius * 2),
                        style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
                    )
                }
            }

            // 3. Middle Clockwise Orbit Ring with Ticks
            rotate(degrees = rotationAngle, pivot = center) {
                val midRadius = radius * 0.80f
                drawCircle(
                    color = JarvisCyanDark.copy(alpha = 0.4f),
                    radius = midRadius,
                    center = center,
                    style = Stroke(width = 1.5.dp.toPx())
                )

                // 8 Geometric Tick Marks on the mid ring
                for (i in 0 until 8) {
                    val angleRad = Math.toRadians((i * 45.0))
                    val startX = center.x + (midRadius - 6.dp.toPx()) * cos(angleRad).toFloat()
                    val startY = center.y + (midRadius - 6.dp.toPx()) * sin(angleRad).toFloat()
                    val endX = center.x + (midRadius + 6.dp.toPx()) * cos(angleRad).toFloat()
                    val endY = center.y + (midRadius + 6.dp.toPx()) * sin(angleRad).toFloat()

                    drawLine(
                        color = coreColor.copy(alpha = 0.7f),
                        start = Offset(startX, startY),
                        end = Offset(endX, endY),
                        strokeWidth = 2.dp.toPx()
                    )
                }
            }

            // 4. Inner Arc Reactor Core Sphere
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color.White,
                        coreColor,
                        JarvisCyanDark,
                        Color.Transparent
                    ),
                    center = center,
                    radius = radius * 0.58f
                ),
                radius = radius * 0.58f,
                center = center
            )

            // 5. Center Core Highlight Dot
            drawCircle(
                color = Color.White,
                radius = 5.dp.toPx() * if (isListening) 1.4f else 1.0f,
                center = center
            )
        }
    }
}
