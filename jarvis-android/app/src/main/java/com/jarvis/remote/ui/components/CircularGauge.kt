package com.jarvis.remote.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.ui.theme.*

@Composable
fun CircularGauge(
    value: Float, // 0 to 100
    label: String,
    unit: String = "%",
    subtext: String? = null,
    modifier: Modifier = Modifier,
    size: Dp = 100.dp,
    strokeWidth: Dp = 8.dp
) {
    val clampedValue = value.coerceIn(0f, 100f)
    val animatedProgress by animateFloatAsState(
        targetValue = clampedValue / 100f,
        animationSpec = tween(durationMillis = 800),
        label = "GaugeProgress"
    )

    // Dynamic color threshold
    val activeColor = when {
        clampedValue >= 85f -> JarvisDanger
        clampedValue >= 70f -> JarvisWarning
        else -> JarvisCyan
    }

    val glowColor = activeColor.copy(alpha = 0.35f)

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier.size(size),
            contentAlignment = Alignment.Center
        ) {
            Canvas(modifier = Modifier.size(size)) {
                val strokePx = strokeWidth.toPx()
                val diameter = size.toPx() - strokePx
                val topLeft = Offset(strokePx / 2, strokePx / 2)
                val arcSize = Size(diameter, diameter)

                // Background Track Ring
                drawArc(
                    color = JarvisBorder.copy(alpha = 0.6f),
                    startAngle = 135f,
                    sweepAngle = 270f,
                    useCenter = false,
                    topLeft = topLeft,
                    size = arcSize,
                    style = Stroke(width = strokePx, cap = StrokeCap.Round)
                )

                // Active Progress Arc
                if (animatedProgress > 0.01f) {
                    drawArc(
                        brush = Brush.sweepGradient(
                            colors = listOf(JarvisCyanDark, activeColor, activeColor)
                        ),
                        startAngle = 135f,
                        sweepAngle = 270f * animatedProgress,
                        useCenter = false,
                        topLeft = topLeft,
                        size = arcSize,
                        style = Stroke(width = strokePx, cap = StrokeCap.Round)
                    )
                }
            }

            // Numeric Center Readout
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "${clampedValue.toInt()}$unit",
                    color = JarvisText,
                    fontSize = (size.value * 0.22f).sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.ExtraBold
                )
                if (subtext != null) {
                    Text(
                        text = subtext,
                        color = JarvisTextDim,
                        fontSize = (size.value * 0.12f).sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = label.uppercase(),
            color = JarvisTextDim,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )
    }
}
