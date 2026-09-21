package com.jarvis.remote.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.data.model.TelemetryData
import com.jarvis.remote.ui.theme.*

@Composable
fun TelemetryCard(
    telemetry: TelemetryData,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        MetricItem(label = "CPU", value = "${telemetry.cpuPercent.toInt()}%", modifier = Modifier.weight(1f))
        MetricItem(label = "RAM", value = "${telemetry.ramPercent.toInt()}%", modifier = Modifier.weight(1f))
        val gpuVal = if (telemetry.gpu.loadPercent >= 0) "${telemetry.gpu.loadPercent.toInt()}%" else "—"
        MetricItem(label = "GPU", value = gpuVal, modifier = Modifier.weight(1f))
        MetricItem(label = "BAT", value = "${telemetry.battery.percent.toInt()}%", modifier = Modifier.weight(1f))
    }
}

@Composable
private fun MetricItem(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier
            .border(1.dp, JarvisBorder, RoundedCornerShape(8.dp)),
        color = JarvisSurface.copy(alpha = 0.8f),
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(vertical = 8.dp, horizontal = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = label,
                color = JarvisTextDim,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                color = JarvisCyan,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.ExtraBold
            )
        }
    }
}
