package com.jarvis.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.data.model.TelemetryData
import com.jarvis.remote.ui.components.CircularGauge
import com.jarvis.remote.ui.theme.*

@Composable
fun TelemetryDetailScreen(
    telemetry: TelemetryData,
    modifier: Modifier = Modifier
) {
    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(JarvisBackground)
            .padding(16.dp)
            .verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        Column {
            Text(
                text = "HOST TELEMETRY DIAGNOSTICS",
                color = JarvisCyan,
                fontSize = 18.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp
            )
            Text(
                text = "Real-time hardware sensor & compute telemetry",
                color = JarvisTextDim,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        // Circular Gauge 2x2 Matrix
        Surface(
            color = JarvisSurfaceCard,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, JarvisBorder, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    CircularGauge(
                        value = telemetry.cpuPercent,
                        label = "CPU Load",
                        unit = "%",
                        size = 110.dp
                    )
                    CircularGauge(
                        value = telemetry.ramPercent,
                        label = "RAM Load",
                        unit = "%",
                        subtext = "${String.format("%.1f", telemetry.ramUsedGb)}G",
                        size = 110.dp
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    val gpuVal = if (telemetry.gpu.loadPercent >= 0) telemetry.gpu.loadPercent else 0f
                    val gpuSub = if (telemetry.gpu.tempC >= 0) "${telemetry.gpu.tempC.toInt()}°C" else null
                    CircularGauge(
                        value = gpuVal,
                        label = "GPU Compute",
                        unit = "%",
                        subtext = gpuSub,
                        size = 110.dp
                    )

                    CircularGauge(
                        value = telemetry.battery.percent,
                        label = "Battery",
                        unit = "%",
                        subtext = if (telemetry.battery.powerPlugged) "AC" else "BAT",
                        size = 110.dp
                    )
                }
            }
        }

        // Detailed Hardware Specs Card
        Surface(
            color = JarvisSurfaceCard,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, JarvisBorder, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "HARDWARE SUBSYSTEM BREAKDOWN",
                    color = JarvisCyan,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                TelemetryRow(
                    label = "RAM Allocation",
                    value = "${String.format("%.1f", telemetry.ramUsedGb)} GB / ${String.format("%.1f", telemetry.ramTotalGb)} GB (${telemetry.ramPercent.toInt()}%)"
                )

                TelemetryRow(
                    label = "GPU Subsystem",
                    value = if (telemetry.gpu.name.isNotBlank() && telemetry.gpu.name != "N/A")
                        "${telemetry.gpu.name} (${if (telemetry.gpu.tempC >= 0) "${telemetry.gpu.tempC.toInt()}°C" else "N/A"})"
                    else "Integrated / No Dedicated GPU"
                )

                TelemetryRow(
                    label = "Storage Usage",
                    value = "${String.format("%.1f", telemetry.disk.totalGb - telemetry.disk.freeGb)} GB used / ${String.format("%.1f", telemetry.disk.totalGb)} GB (${telemetry.disk.percent.toInt()}%)"
                )

                TelemetryRow(
                    label = "Power Source",
                    value = if (telemetry.battery.powerPlugged) "Plugged in (AC Power)" else "Running on Battery (${telemetry.battery.percent.toInt()}%)"
                )
            }
        }
    }
}

@Composable
private fun TelemetryRow(label: String, value: String) {
    Column {
        Text(
            text = label.uppercase(),
            color = JarvisTextDim,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = value,
            color = JarvisText,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
