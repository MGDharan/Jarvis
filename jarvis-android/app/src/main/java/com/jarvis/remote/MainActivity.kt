package com.jarvis.remote

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.jarvis.remote.audio.AudioPlayer
import com.jarvis.remote.audio.VoiceRecorder
import com.jarvis.remote.ui.screens.*
import com.jarvis.remote.ui.theme.*
import com.jarvis.remote.ui.viewmodel.*
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    private lateinit var voiceRecorder: VoiceRecorder
    private lateinit var audioPlayer: AudioPlayer

    private val requestRecordAudioPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (!isGranted) {
                Toast.makeText(this, "Microphone permission required for voice commands", Toast.LENGTH_SHORT).show()
            }
        }

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* handled */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        audioPlayer = AudioPlayer(this)
        voiceRecorder = VoiceRecorder(this) { spokenText ->
            viewModel.sendVoiceQuery(spokenText)
        }

        // Request runtime permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestRecordAudioPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        // Observe ViewModel One-Time Events
        lifecycleScope.launch {
            viewModel.events.collectLatest { event ->
                when (event) {
                    is UiEvent.PlayAudio -> {
                        audioPlayer.playBase64Mp3(event.base64) {
                            viewModel.setOrbState(OrbVisualState.IDLE)
                        }
                    }
                    is UiEvent.ShowToast -> {
                        Toast.makeText(this@MainActivity, event.message, if (event.isLong) Toast.LENGTH_LONG else Toast.LENGTH_SHORT).show()
                    }
                    is UiEvent.TriggerVibration -> {
                        triggerHapticFeedback()
                    }
                    is UiEvent.NavigateToPairing -> {
                        // Handled by declarative state
                    }
                }
            }
        }

        setContent {
            JarvisRemoteTheme {
                val uiState by viewModel.uiState.collectAsState()
                val navController = rememberNavController()

                val startDestination = if (uiState.isPaired) "main_hub" else "qr_pair"

                NavHost(navController = navController, startDestination = startDestination) {
                    composable("qr_pair") {
                        QRPairingScreen(
                            onPairSuccess = {
                                viewModel.connect()
                                navController.navigate("main_hub") {
                                    popUpTo("qr_pair") { inclusive = true }
                                }
                            },
                            onPairWithJson = { jsonStr ->
                                viewModel.repository.pairWithQr(jsonStr)
                            }
                        )
                    }

                    composable("main_hub") {
                        MainHubScaffold(
                            uiState = uiState,
                            voiceRecorder = voiceRecorder,
                            onTabSelected = { viewModel.selectTab(it) },
                            onSendMessage = { viewModel.sendTextCommand(it) },
                            onConfirmChallenge = { id, act -> viewModel.confirmChallenge(id, act) },
                            onDismissChallenge = { viewModel.dismissChallenge() },
                            onQuickAction = { viewModel.executeQuickAction(it) },
                            onSetOrbState = { viewModel.setOrbState(it) },
                            onRunTerminalCommand = { viewModel.runTerminalCommand(it) },
                            onSearchFiles = { viewModel.searchFiles(it) },
                            onDownloadFile = { viewModel.requestFileDownload(it) },
                            onReconnect = { viewModel.connect() },
                            onUnpair = {
                                viewModel.unpair()
                                navController.navigate("qr_pair") {
                                    popUpTo("main_hub") { inclusive = true }
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    private fun triggerHapticFeedback() {
        try {
            val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(VibrationEffect.createOneShot(250, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(250)
            }
        } catch (e: Exception) {
            // Ignore vibration errors
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        voiceRecorder.stopListening()
        audioPlayer.stop()
    }
}

@Composable
fun MainHubScaffold(
    uiState: MainUiState,
    voiceRecorder: VoiceRecorder,
    onTabSelected: (NavTab) -> Unit,
    onSendMessage: (String) -> Unit,
    onConfirmChallenge: (String, String) -> Unit,
    onDismissChallenge: () -> Unit,
    onQuickAction: (String) -> Unit,
    onSetOrbState: (OrbVisualState) -> Unit,
    onRunTerminalCommand: (String) -> Unit,
    onSearchFiles: (String) -> Unit,
    onDownloadFile: (com.jarvis.remote.data.model.FileSearchResult) -> Unit,
    onReconnect: () -> Unit,
    onUnpair: () -> Unit
) {
    Scaffold(
        bottomBar = {
            HolographicNavigationBar(
                selectedTab = uiState.selectedTab,
                onTabSelected = onTabSelected
            )
        },
        containerColor = JarvisBackground
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when (uiState.selectedTab) {
                NavTab.ASSISTANT -> {
                    AssistantScreen(
                        connectionStatus = uiState.connectionStatus,
                        telemetry = uiState.telemetry,
                        messages = uiState.messages,
                        activeChallenge = uiState.activeChallenge,
                        orbState = uiState.orbState,
                        voiceRecorder = voiceRecorder,
                        serverName = uiState.serverName,
                        onSendMessage = onSendMessage,
                        onConfirmChallenge = onConfirmChallenge,
                        onDismissChallenge = onDismissChallenge,
                        onQuickAction = onQuickAction,
                        onSetOrbState = onSetOrbState
                    )
                }
                NavTab.CONSOLE -> {
                    ConsoleScreen(
                        terminalLogs = uiState.terminalLogs,
                        onExecuteAction = onQuickAction,
                        onRunTerminalCommand = onRunTerminalCommand
                    )
                }
                NavTab.TELEMETRY -> {
                    TelemetryDetailScreen(
                        telemetry = uiState.telemetry
                    )
                }
                NavTab.FILES -> {
                    FileBrowserScreen(
                        searchResults = uiState.searchResults,
                        downloadProgress = uiState.downloadProgress,
                        activeDownloadFilename = uiState.activeDownloadFilename,
                        onSearch = onSearchFiles,
                        onDownloadFile = onDownloadFile
                    )
                }
                NavTab.SETTINGS -> {
                    DeviceSettingsScreen(
                        securePrefs = com.jarvis.remote.data.preferences.SecurePreferences(androidx.compose.ui.platform.LocalContext.current),
                        connectionStatus = uiState.connectionStatus,
                        onReconnect = onReconnect,
                        onUnpair = onUnpair
                    )
                }
            }
        }
    }
}

@Composable
fun HolographicNavigationBar(
    selectedTab: NavTab,
    onTabSelected: (NavTab) -> Unit
) {
    Surface(
        color = JarvisBackgroundDark,
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, JarvisBorder, RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp))
    ) {
        NavigationBar(
            containerColor = JarvisBackgroundDark,
            tonalElevation = 8.dp
        ) {
            NavTab.values().forEach { tab ->
                val isSelected = selectedTab == tab
                val icon: ImageVector = when (tab) {
                    NavTab.ASSISTANT -> Icons.Default.Mic
                    NavTab.CONSOLE -> Icons.Default.Terminal
                    NavTab.TELEMETRY -> Icons.Default.Speed
                    NavTab.FILES -> Icons.Default.Folder
                    NavTab.SETTINGS -> Icons.Default.Settings
                }

                NavigationBarItem(
                    selected = isSelected,
                    onClick = { onTabSelected(tab) },
                    icon = {
                        Icon(
                            imageVector = icon,
                            contentDescription = tab.title,
                            tint = if (isSelected) JarvisCyan else JarvisTextMuted
                        )
                    },
                    label = {
                        Text(
                            text = tab.title.uppercase(),
                            color = if (isSelected) JarvisCyan else JarvisTextMuted,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    colors = NavigationBarItemDefaults.colors(
                        indicatorColor = JarvisCyanDark.copy(alpha = 0.3f),
                        selectedIconColor = JarvisCyan,
                        unselectedIconColor = JarvisTextMuted
                    )
                )
            }
        }
    }
}
