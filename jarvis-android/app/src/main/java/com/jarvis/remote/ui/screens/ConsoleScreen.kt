package com.jarvis.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.ui.theme.*
import kotlinx.coroutines.launch

data class ConsoleAction(
    val id: String,
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val isDangerous: Boolean = false
)

val consoleGridActions = listOf(
    ConsoleAction("Lock Workstation", "Lock PC", "Lock Windows session", Icons.Default.Lock),
    ConsoleAction("Screen Grab", "Screenshot", "Capture primary display", Icons.Default.Screenshot),
    ConsoleAction("Sentry Mode", "Sentry Guard", "Activate lab motion detection", Icons.Default.Security),
    ConsoleAction("Mute Audio", "Mute Audio", "Toggle host audio mute", Icons.Default.VolumeMute),
    ConsoleAction("Volume Up", "Volume Up", "Increase volume (+10%)", Icons.Default.VolumeUp),
    ConsoleAction("Volume Down", "Volume Down", "Decrease volume (-10%)", Icons.Default.VolumeDown),
    ConsoleAction("Sleep PC", "Sleep System", "Enter low power sleep", Icons.Default.Bedtime),
    ConsoleAction("Restart PC", "Restart PC", "Initiate system reboot", Icons.Default.RestartAlt, isDangerous = true)
)

@Composable
fun ConsoleScreen(
    terminalLogs: List<String>,
    onExecuteAction: (String) -> Unit,
    onRunTerminalCommand: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var commandInput by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(terminalLogs.size) {
        if (terminalLogs.isNotEmpty()) {
            listState.animateScrollToItem(terminalLogs.size - 1)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(JarvisBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "COMMAND DECK // MATRIX",
            color = JarvisCyan,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp
        )
        Text(
            text = "Direct workstation hardware & script controls",
            color = JarvisTextDim,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Grid of Action Buttons (2 columns)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            for (i in consoleGridActions.indices step 2) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    ActionCard(
                        action = consoleGridActions[i],
                        onClick = { onExecuteAction(consoleGridActions[i].id) },
                        modifier = Modifier.weight(1f)
                    )
                    if (i + 1 < consoleGridActions.size) {
                        ActionCard(
                            action = consoleGridActions[i + 1],
                            onClick = { onExecuteAction(consoleGridActions[i + 1].id) },
                            modifier = Modifier.weight(1f)
                        )
                    } else {
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Terminal Log Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "TERMINAL AUDIT STREAM",
                color = JarvisTextDim,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "LIVE",
                color = JarvisOnline,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        // Terminal Log Container
        Surface(
            color = JarvisBackgroundDark,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .border(1.dp, JarvisBorder, RoundedCornerShape(8.dp))
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                items(terminalLogs) { log ->
                    val logColor = when {
                        log.contains("ALERT") || log.contains("failed") || log.contains("error", true) -> JarvisDanger
                        log.contains("USER:") || log.contains("$ >") -> JarvisCyanBright
                        log.contains("JARVIS:") -> JarvisText
                        log.contains("Connected") || log.contains("Verified") -> JarvisOnline
                        else -> JarvisTextDim
                    }
                    Text(
                        text = log,
                        color = logColor,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Command Prompt Input
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = commandInput,
                onValueChange = { commandInput = it },
                placeholder = { Text("$ > enter shell / python command…", color = JarvisTextDim, fontSize = 11.sp) },
                modifier = Modifier.weight(1f),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = JarvisCyan,
                    unfocusedBorderColor = JarvisBorder,
                    focusedTextColor = JarvisCyanBright,
                    unfocusedTextColor = JarvisText
                ),
                shape = RoundedCornerShape(8.dp),
                singleLine = true
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = {
                    if (commandInput.isNotBlank()) {
                        onRunTerminalCommand(commandInput)
                        commandInput = ""
                    }
                },
                modifier = Modifier
                    .size(48.dp)
                    .background(JarvisCyan, RoundedCornerShape(8.dp))
            ) {
                Icon(Icons.Default.Terminal, contentDescription = "Run", tint = JarvisBackground)
            }
        }
    }
}

@Composable
private fun ActionCard(
    action: ConsoleAction,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        color = JarvisSurfaceCard,
        shape = RoundedCornerShape(8.dp),
        modifier = modifier
            .border(
                1.dp,
                if (action.isDangerous) JarvisDanger.copy(alpha = 0.6f) else JarvisBorder,
                RoundedCornerShape(8.dp)
            )
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(
                imageVector = action.icon,
                contentDescription = action.title,
                tint = if (action.isDangerous) JarvisDanger else JarvisCyan,
                modifier = Modifier.size(22.dp)
            )
            Column {
                Text(
                    text = action.title,
                    color = if (action.isDangerous) JarvisDanger else JarvisText,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = action.subtitle,
                    color = JarvisTextDim,
                    fontSize = 10.sp,
                    maxLines = 1
                )
            }
        }
    }
}
