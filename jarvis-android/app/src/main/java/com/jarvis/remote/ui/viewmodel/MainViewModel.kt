package com.jarvis.remote.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.remote.data.model.*
import com.jarvis.remote.data.repository.JarvisRepository
import com.jarvis.remote.network.ConnectionStatus
import com.jarvis.remote.network.DownloadState
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.UUID

enum class OrbVisualState {
    IDLE,
    LISTENING,
    PROCESSING,
    SPEAKING
}

enum class NavTab(val title: String) {
    ASSISTANT("Assistant"),
    CONSOLE("Console"),
    TELEMETRY("Telemetry"),
    FILES("Cloud Files"),
    SETTINGS("Settings")
}

data class MainUiState(
    val connectionStatus: ConnectionStatus = ConnectionStatus.OFFLINE,
    val telemetry: TelemetryData = TelemetryData(),
    val messages: List<ChatMessage> = emptyList(),
    val activeChallenge: ConfirmationChallenge? = null,
    val searchResults: List<FileSearchResult> = emptyList(),
    val downloadProgress: Int? = null,
    val isDownloading: Boolean = false,
    val activeDownloadFilename: String? = null,
    val selectedTab: NavTab = NavTab.ASSISTANT,
    val orbState: OrbVisualState = OrbVisualState.IDLE,
    val isPaired: Boolean = false,
    val serverName: String = "JARVIS Lab Laptop",
    val statusBanner: String? = null,
    val terminalLogs: List<String> = listOf("System initialized. Awaiting commands.")
)

sealed class UiEvent {
    data class PlayAudio(val base64: String) : UiEvent()
    data class ShowToast(val message: String, val isLong: Boolean = false) : UiEvent()
    object TriggerVibration : UiEvent()
    object NavigateToPairing : UiEvent()
}

class MainViewModel(
    application: Application,
    val repository: JarvisRepository = JarvisRepository(application)
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(
        MainUiState(
            isPaired = repository.isPaired,
            serverName = repository.serverName
        )
    )
    val uiState: StateFlow<MainUiState> = _uiState.asStateFlow()

    private val _eventChannel = Channel<UiEvent>(Channel.BUFFERED)
    val events: Flow<UiEvent> = _eventChannel.receiveAsFlow()

    init {
        observeRepository()
        if (repository.isPaired) {
            repository.connect()
        }
    }

    private fun observeRepository() {
        // Connection status
        viewModelScope.launch {
            repository.connectionStatus.collect { status ->
                _uiState.update { it.copy(connectionStatus = status) }
                if (status == ConnectionStatus.ONLINE) {
                    addTerminalLog("Connected to JARVIS Gateway (${repository.serverName})")
                } else if (status == ConnectionStatus.OFFLINE) {
                    addTerminalLog("Disconnected from JARVIS Gateway.")
                }
            }
        }

        // Telemetry
        viewModelScope.launch {
            repository.telemetry.collect { tele ->
                _uiState.update { it.copy(telemetry = tele) }
            }
        }

        // Incoming messages
        viewModelScope.launch {
            repository.incomingMessages.collect { msg ->
                msg?.let { chatMsg ->
                    _uiState.update { state ->
                        val updated = state.messages + chatMsg
                        state.copy(
                            messages = updated,
                            activeChallenge = chatMsg.challenge ?: state.activeChallenge,
                            orbState = OrbVisualState.IDLE
                        )
                    }
                    addTerminalLog("JARVIS: ${chatMsg.text}")

                    // Check for automatic transfer dispatch
                    chatMsg.transfer?.let { transfer ->
                        startFileDownload(transfer)
                    }
                }
            }
        }

        // Search results
        viewModelScope.launch {
            repository.searchResults.collect { results ->
                _uiState.update { it.copy(searchResults = results) }
                addTerminalLog("Received ${results.size} file search results.")
            }
        }

        // Incoming TTS Audio
        viewModelScope.launch {
            repository.incomingAudio.collect { audioB64 ->
                if (audioB64.isNotBlank()) {
                    _uiState.update { it.copy(orbState = OrbVisualState.SPEAKING) }
                    _eventChannel.send(UiEvent.PlayAudio(audioB64))
                }
            }
        }

        // Push notifications
        viewModelScope.launch {
            repository.notifications.collect { notif ->
                notif?.let { record ->
                    repository.dispatchNotification(record)
                    _eventChannel.send(UiEvent.ShowToast("🚨 [${record.type.uppercase()}] ${record.title}", true))
                    _eventChannel.send(UiEvent.TriggerVibration)
                    addTerminalLog("ALERT: [${record.type}] ${record.title} - ${record.message}")
                }
            }
        }
    }

    fun selectTab(tab: NavTab) {
        _uiState.update { it.copy(selectedTab = tab) }
    }

    fun setOrbState(state: OrbVisualState) {
        _uiState.update { it.copy(orbState = state) }
    }

    fun sendVoiceQuery(query: String) {
        if (query.isBlank()) return
        val userMsg = ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = "USER",
            text = query
        )
        _uiState.update { state ->
            state.copy(
                messages = state.messages + userMsg,
                orbState = OrbVisualState.PROCESSING
            )
        }
        addTerminalLog("USER: $query")
        repository.sendVoiceQuery(query)
    }

    fun sendTextCommand(text: String) {
        if (text.isBlank()) return
        val userMsg = ChatMessage(
            id = UUID.randomUUID().toString(),
            sender = "USER",
            text = text
        )
        _uiState.update { it.copy(messages = it.messages + userMsg) }
        addTerminalLog("USER: $text")
        repository.sendCommand("voice_query", mapOf("query" to text, "include_audio" to true))
    }

    fun executeQuickAction(action: String) {
        when (action) {
            "System Health" -> sendTextCommand("report system health and telemetry")
            "Sentry Mode" -> repository.sendCommand("toggle_sentry", mapOf("mode" to "active"))
            "Lock Workstation" -> repository.sendCommand("system_action", mapOf("action" to "lock"))
            "Screen Grab" -> repository.sendCommand("capture_screen", emptyMap())
            "Mute Audio" -> repository.sendCommand("media_control", mapOf("action" to "mute"))
            "Volume Up" -> repository.sendCommand("media_control", mapOf("action" to "volume_up"))
            "Volume Down" -> repository.sendCommand("media_control", mapOf("action" to "volume_down"))
            "Sleep PC" -> repository.sendCommand("system_action", mapOf("action" to "sleep"))
            "Restart PC" -> repository.sendCommand("system_action", mapOf("action" to "restart"))
            else -> sendTextCommand(action)
        }
        addTerminalLog("Executed quick action: $action")
    }

    fun runTerminalCommand(rawCommand: String) {
        if (rawCommand.isBlank()) return
        addTerminalLog("$ > $rawCommand")
        repository.sendCommand("terminal_exec", mapOf("command" to rawCommand))
    }

    fun confirmChallenge(challengeId: String, action: String) {
        _uiState.update { it.copy(activeChallenge = null) }
        repository.sendCommand("confirm_action", mapOf("challenge_id" to challengeId, "action" to action))
        addTerminalLog("Confirmed challenge: $action (ID: $challengeId)")
    }

    fun dismissChallenge() {
        _uiState.update { it.copy(activeChallenge = null) }
        addTerminalLog("Dismissed security challenge.")
    }

    fun searchFiles(query: String) {
        if (query.isBlank()) return
        addTerminalLog("Searching files for query: \"$query\"")
        repository.sendCommand("search_files", mapOf("query" to query))
    }

    fun requestFileDownload(file: FileSearchResult) {
        addTerminalLog("Requesting file preparation: ${file.path}")
        repository.sendCommand("prepare_transfer", mapOf("target_path" to file.path))
    }

    private fun startFileDownload(transfer: TransferMetadata) {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isDownloading = true,
                    activeDownloadFilename = transfer.filename,
                    downloadProgress = 0
                )
            }
            addTerminalLog("Starting secure download: ${transfer.filename} (${transfer.totalMb} MB)")

            repository.downloadFile(transfer).collect { downloadState ->
                when (downloadState) {
                    is DownloadState.Progress -> {
                        _uiState.update { it.copy(downloadProgress = downloadState.percentage) }
                    }
                    is DownloadState.Success -> {
                        _uiState.update {
                            it.copy(
                                isDownloading = false,
                                activeDownloadFilename = null,
                                downloadProgress = null
                            )
                        }
                        val integrityMsg = if (downloadState.sha256Verified) "Verified SHA-256 ✓" else "SHA-256 Mismatch ⚠️"
                        _eventChannel.send(UiEvent.ShowToast("Downloaded ${transfer.filename} ($integrityMsg)"))
                        addTerminalLog("Download finished: ${downloadState.savedFile.name} [$integrityMsg]")
                    }
                    is DownloadState.Error -> {
                        _uiState.update {
                            it.copy(
                                isDownloading = false,
                                activeDownloadFilename = null,
                                downloadProgress = null
                            )
                        }
                        _eventChannel.send(UiEvent.ShowToast("Download error: ${downloadState.message}"))
                        addTerminalLog("Download failed: ${downloadState.message}")
                    }
                }
            }
        }
    }

    fun addTerminalLog(log: String) {
        val timestamp = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
        _uiState.update { state ->
            val updated = state.terminalLogs + "[$timestamp] $log"
            state.copy(terminalLogs = if (updated.size > 100) updated.takeLast(100) else updated)
        }
    }

    fun unpair() {
        repository.unpair()
        _uiState.update {
            it.copy(
                isPaired = false,
                connectionStatus = ConnectionStatus.OFFLINE,
                messages = emptyList(),
                searchResults = emptyList()
            )
        }
        viewModelScope.launch {
            _eventChannel.send(UiEvent.NavigateToPairing)
        }
    }

    fun connect() {
        repository.connect()
    }
}
