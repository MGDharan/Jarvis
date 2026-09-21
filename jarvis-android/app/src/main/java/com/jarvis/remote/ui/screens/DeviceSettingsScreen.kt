package com.jarvis.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.data.preferences.SecurePreferences
import com.jarvis.remote.network.ConnectionStatus
import com.jarvis.remote.ui.theme.*

@Composable
fun DeviceSettingsScreen(
    securePrefs: SecurePreferences,
    connectionStatus: ConnectionStatus,
    onReconnect: () -> Unit,
    onUnpair: () -> Unit,
    modifier: Modifier = Modifier
) {
    var showUnpairConfirm by remember { mutableStateOf(false) }
    val scrollState = rememberScrollState()

    if (showUnpairConfirm) {
        AlertDialog(
            onDismissRequest = { showUnpairConfirm = false },
            title = {
                Text(
                    text = "UNPAIR WORKSTATION?",
                    color = JarvisDanger,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
            },
            text = {
                Text(
                    text = "This will wipe encrypted authentication tokens and disconnect from ${securePrefs.serverName}. You will need to rescan the QR code to connect again.",
                    color = JarvisText,
                    fontSize = 13.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showUnpairConfirm = false
                        onUnpair()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = JarvisDanger),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("UNPAIR & WIPE", color = JarvisText, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { showUnpairConfirm = false },
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("CANCEL", color = JarvisTextDim, fontFamily = FontFamily.Monospace)
                }
            },
            containerColor = JarvisSurfaceCard,
            modifier = Modifier.border(1.dp, JarvisDanger.copy(alpha = 0.5f), RoundedCornerShape(12.dp))
        )
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(JarvisBackground)
            .padding(16.dp)
            .verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "LINK CONFIGURATION & SECURITY",
            color = JarvisCyan,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp
        )
        Text(
            text = "Cryptographic tokens & workstation pairing",
            color = JarvisTextDim,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        // Connection Diagnostics Card
        Surface(
            color = JarvisSurfaceCard,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, JarvisBorder, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "LINK PROTOCOL DIAGNOSTICS",
                        color = JarvisCyan,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                    IconButton(onClick = onReconnect) {
                        Icon(Icons.Default.Refresh, contentDescription = "Reconnect", tint = JarvisCyan)
                    }
                }

                SettingRow(label = "Target Host", value = securePrefs.serverName)
                SettingRow(label = "WebSocket Gateway", value = securePrefs.gatewayUrl)
                SettingRow(label = "HTTP Transfer URL", value = securePrefs.httpUrl)
                SettingRow(label = "Connection State", value = connectionStatus.name)
            }
        }

        // Encryption & Security Card
        Surface(
            color = JarvisSurfaceCard,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, JarvisBorderGlow, RoundedCornerShape(12.dp))
                .padding(16.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(Icons.Default.Security, contentDescription = null, tint = JarvisOnline, modifier = Modifier.size(18.dp))
                    Text(
                        text = "HARDWARE CRYPTO VAULT",
                        color = JarvisOnline,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }

                SettingRow(label = "Registered Device ID", value = securePrefs.deviceId.ifBlank { "Not Registered" })
                SettingRow(label = "Storage Scheme", value = "Android Keystore AES-256 SIV/GCM")
                SettingRow(label = "Auth Token Status", value = if (securePrefs.authToken.isNotBlank()) "Valid & Encrypted" else "Missing")
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Danger Zone: Unpair
        Button(
            onClick = { showUnpairConfirm = true },
            colors = ButtonDefaults.buttonColors(containerColor = JarvisDanger),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = "DISCONNECT & UNPAIR WORKSTATION",
                color = JarvisText,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp
            )
        }
    }
}

@Composable
private fun SettingRow(label: String, value: String) {
    Column {
        Text(
            text = label.uppercase(),
            color = JarvisTextDim,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = value,
            color = JarvisText,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
