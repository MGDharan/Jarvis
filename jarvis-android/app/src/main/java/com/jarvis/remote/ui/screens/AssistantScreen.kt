package com.jarvis.remote.ui.screens

import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInteropFilter
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.audio.VoiceRecorder
import com.jarvis.remote.data.model.ChatMessage
import com.jarvis.remote.data.model.ConfirmationChallenge
import com.jarvis.remote.data.model.TelemetryData
import com.jarvis.remote.network.ConnectionStatus
import com.jarvis.remote.ui.components.CommandPillsRow
import com.jarvis.remote.ui.components.ConfirmationDialog
import com.jarvis.remote.ui.components.GlowingOrb
import com.jarvis.remote.ui.components.TelemetryCard
import com.jarvis.remote.ui.theme.*
import com.jarvis.remote.ui.viewmodel.OrbVisualState

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AssistantScreen(
    connectionStatus: ConnectionStatus,
    telemetry: TelemetryData,
    messages: List<ChatMessage>,
    activeChallenge: ConfirmationChallenge?,
    orbState: OrbVisualState,
    voiceRecorder: VoiceRecorder,
    serverName: String,
    onSendMessage: (String) -> Unit,
    onConfirmChallenge: (String, String) -> Unit,
    onDismissChallenge: () -> Unit,
    onQuickAction: (String) -> Unit,
    onSetOrbState: (OrbVisualState) -> Unit,
    modifier: Modifier = Modifier
) {
    val isListening by voiceRecorder.isListening.collectAsState()
    val audioRms by voiceRecorder.audioRms.collectAsState()
    var inputText by remember { mutableStateOf("") }

    val effectiveOrbState = if (isListening) OrbVisualState.LISTENING else orbState

    if (activeChallenge != null) {
        ConfirmationDialog(
            challenge = activeChallenge,
            onConfirm = { onConfirmChallenge(activeChallenge.challengeId, activeChallenge.action) },
            onDismiss = onDismissChallenge
        )
    }

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(JarvisBackground)
                    .padding(top = 12.dp, bottom = 6.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "JARVIS",
                    color = JarvisCyan,
                    fontSize = 22.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 4.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val statusDotColor = when (connectionStatus) {
                        ConnectionStatus.ONLINE -> JarvisOnline
                        ConnectionStatus.CONNECTING -> JarvisWarning
                        ConnectionStatus.OFFLINE, ConnectionStatus.UNAUTHORIZED -> JarvisDanger
                    }
                    val statusText = when (connectionStatus) {
                        ConnectionStatus.ONLINE -> "LINK ACTIVE // $serverName"
                        ConnectionStatus.CONNECTING -> "CONNECTING TO GATEWAY…"
                        ConnectionStatus.OFFLINE -> "GATEWAY OFFLINE"
                        ConnectionStatus.UNAUTHORIZED -> "NOT AUTHENTICATED"
                    }

                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .background(statusDotColor, CircleShape)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = statusText.uppercase(),
                        color = statusDotColor,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        },
        bottomBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(JarvisBackground)
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            ) {
                // Text Input Bar
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = { Text("Command JARVIS…", color = JarvisTextDim, fontSize = 13.sp) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = JarvisCyan,
                            unfocusedBorderColor = JarvisBorder,
                            focusedTextColor = JarvisText,
                            unfocusedTextColor = JarvisText,
                            cursorColor = JarvisCyan,
                        ),
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                onSendMessage(inputText)
                                inputText = ""
                            }
                        },
                        modifier = Modifier
                            .size(48.dp)
                            .background(JarvisCyan, CircleShape)
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Send", tint = JarvisBackground)
                    }
                }
            }
        },
        containerColor = JarvisBackground
    ) { paddingValues ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .padding(paddingValues),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Live Hardware Telemetry Bar
            Spacer(modifier = Modifier.height(2.dp))
            TelemetryCard(telemetry = telemetry)

            // Center Interactive Holographic Orb
            Spacer(modifier = Modifier.height(10.dp))
            Box(
                modifier = Modifier
                    .size(175.dp)
                    .pointerInteropFilter { motionEvent ->
                        when (motionEvent.action) {
                            MotionEvent.ACTION_DOWN -> {
                                onSetOrbState(OrbVisualState.LISTENING)
                                voiceRecorder.startListening()
                                true
                            }
                            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                                voiceRecorder.stopListening()
                                onSetOrbState(OrbVisualState.IDLE)
                                true
                            }
                            else -> false
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                GlowingOrb(
                    visualState = effectiveOrbState,
                    audioRms = audioRms,
                    size = 170.dp
                )
            }

            Spacer(modifier = Modifier.height(6.dp))
            val orbPrompt = when (effectiveOrbState) {
                OrbVisualState.LISTENING -> "LISTENING // SPEAK NOW"
                OrbVisualState.PROCESSING -> "PROCESSING NEURAL QUERY…"
                OrbVisualState.SPEAKING -> "JARVIS VOCAL RESPONSE"
                OrbVisualState.IDLE -> "TOUCH & HOLD TO SPEAK"
            }
            Text(
                text = orbPrompt,
                color = when (effectiveOrbState) {
                    OrbVisualState.LISTENING -> JarvisCyanBright
                    OrbVisualState.PROCESSING -> JarvisPurpleHolo
                    OrbVisualState.SPEAKING -> JarvisArcOrange
                    OrbVisualState.IDLE -> JarvisTextDim
                },
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp
            )

            // Quick Action Macro Pills
            Spacer(modifier = Modifier.height(10.dp))
            CommandPillsRow(onActionClick = onQuickAction)

            // Conversation Chat Stream
            Spacer(modifier = Modifier.height(10.dp))
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(horizontal = 16.dp),
                reverseLayout = true,
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(messages.reversed()) { msg ->
                    MessageBubble(message = msg)
                }
            }
        }
    }
}

@Composable
fun MessageBubble(message: ChatMessage) {
    val isUser = message.sender == "USER"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Surface(
            color = if (isUser) JarvisCyanDark.copy(alpha = 0.35f) else JarvisSurfaceCard,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .widthIn(max = 290.dp)
                .border(
                    width = 1.dp,
                    color = if (isUser) JarvisCyan.copy(alpha = 0.5f) else JarvisBorderGlow,
                    shape = RoundedCornerShape(12.dp)
                )
        ) {
            Column(modifier = Modifier.padding(10.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = if (isUser) "COMMANDER" else "JARVIS AI",
                        color = if (isUser) JarvisCyanBright else JarvisCyan,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(message.timestamp),
                        color = JarvisTextMuted,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
                Spacer(modifier = Modifier.height(3.dp))
                Text(
                    text = message.text,
                    color = JarvisText,
                    fontSize = 13.sp,
                    lineHeight = 18.sp
                )
            }
        }
    }
}
