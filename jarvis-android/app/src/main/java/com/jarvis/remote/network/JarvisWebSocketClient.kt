package com.jarvis.remote.network

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.jarvis.remote.data.model.*
import com.jarvis.remote.data.preferences.SecurePreferences
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import java.util.UUID
import java.util.concurrent.TimeUnit

enum class ConnectionStatus {
    ONLINE,
    CONNECTING,
    OFFLINE,
    UNAUTHORIZED
}

class JarvisWebSocketClient(
    private val securePrefs: SecurePreferences,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO + SupervisorJob()),
    private val gson: Gson = Gson()
) {

    private val client = OkHttpClient.Builder()
        .pingInterval(10, TimeUnit.SECONDS)
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // infinite for WS
        .build()

    private var webSocket: WebSocket? = null
    private var isIntentionalClose = false

    private val _connectionStatus = MutableStateFlow(ConnectionStatus.OFFLINE)
    val connectionStatus: StateFlow<ConnectionStatus> = _connectionStatus.asStateFlow()

    private val _latestTelemetry = MutableStateFlow(TelemetryData())
    val latestTelemetry: StateFlow<TelemetryData> = _latestTelemetry.asStateFlow()

    private val _incomingMessages = MutableStateFlow<ChatMessage?>(null)
    val incomingMessages: StateFlow<ChatMessage?> = _incomingMessages.asStateFlow()

    private val _notifications = MutableStateFlow<NotificationRecord?>(null)
    val notifications: StateFlow<NotificationRecord?> = _notifications.asStateFlow()

    private val _searchResults = MutableStateFlow<List<FileSearchResult>>(emptyList())
    val searchResults: StateFlow<List<FileSearchResult>> = _searchResults.asStateFlow()

    private val _incomingAudio = MutableSharedFlow<String>(extraBufferCapacity = 5)
    val incomingAudio: SharedFlow<String> = _incomingAudio.asSharedFlow()

    fun connect() {
        if (!securePrefs.isPaired) {
            _connectionStatus.value = ConnectionStatus.UNAUTHORIZED
            return
        }

        isIntentionalClose = false
        _connectionStatus.value = ConnectionStatus.CONNECTING

        val baseUrl = securePrefs.gatewayUrl
        val deviceId = securePrefs.deviceId
        val authToken = securePrefs.authToken

        val authenticatedUrl = if (baseUrl.contains("?")) {
            "$baseUrl&device_id=$deviceId&auth_token=$authToken"
        } else {
            "$baseUrl?device_id=$deviceId&auth_token=$authToken"
        }

        val request = Request.Builder()
            .url(authenticatedUrl)
            .build()

        webSocket = client.newWebSocket(request, createListener())
    }

    fun disconnect() {
        isIntentionalClose = true
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        _connectionStatus.value = ConnectionStatus.OFFLINE
    }

    fun sendCommand(command: String, arguments: Map<String, Any?> = emptyMap()): String {
        val reqId = "req_${UUID.randomUUID().toString().take(8)}"
        val cmd = CommandRequest(
            requestId = reqId,
            deviceId = securePrefs.deviceId,
            type = "command",
            command = command,
            arguments = arguments
        )
        val json = gson.toJson(cmd)
        webSocket?.send(json)
        return reqId
    }

    fun sendVoiceQuery(query: String) {
        sendCommand("voice_query", mapOf("query" to query, "include_audio" to true))
    }

    private fun createListener() = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            _connectionStatus.value = ConnectionStatus.ONLINE
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                val json = gson.fromJson(text, JsonObject::class.java)
                val type = json.get("type")?.asString ?: ""

                when (type) {
                    "connection_status" -> {
                        _connectionStatus.value = ConnectionStatus.ONLINE
                    }
                    "telemetry" -> {
                        val dataJson = json.get("data")
                        val telemetry = gson.fromJson(dataJson, TelemetryData::class.java)
                        _latestTelemetry.value = telemetry
                    }
                    "notification" -> {
                        val dataJson = json.get("data")
                        val notif = gson.fromJson(dataJson, NotificationRecord::class.java)
                        _notifications.value = notif
                    }
                    "response" -> {
                        val dataJson = json.get("data")
                        val respData = gson.fromJson(dataJson, ResponseData::class.java)
                        if (respData != null) {
                            // Wire file search results if present
                            respData.results?.let { resultsList: List<FileSearchResult> ->
                                _searchResults.value = resultsList
                            }
                            // Wire audio TTS stream if present
                            respData.audioB64?.let { audio: String ->
                                _incomingAudio.tryEmit(audio)
                            }

                            val msg = ChatMessage(
                                id = respData.requestId ?: UUID.randomUUID().toString(),
                                sender = "JARVIS",
                                text = respData.message ?: "Done.",
                                challenge = respData.challenge,
                                transfer = respData.transfer,
                                audioB64 = respData.audioB64
                            )
                            _incomingMessages.value = msg
                        }
                    }
                    "error" -> {
                        val status = json.get("status")?.asString
                        if (status == "unauthorized" || status == "revoked") {
                            _connectionStatus.value = ConnectionStatus.UNAUTHORIZED
                        }
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            if (code == 4401 || code == 4403) {
                _connectionStatus.value = ConnectionStatus.UNAUTHORIZED
            } else {
                _connectionStatus.value = ConnectionStatus.OFFLINE
            }
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            if (code == 4401 || code == 4403) {
                _connectionStatus.value = ConnectionStatus.UNAUTHORIZED
            } else {
                _connectionStatus.value = ConnectionStatus.OFFLINE
                scheduleReconnect()
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            _connectionStatus.value = ConnectionStatus.OFFLINE
            scheduleReconnect()
        }
    }

    private fun scheduleReconnect() {
        if (!isIntentionalClose && securePrefs.isPaired) {
            scope.launch {
                delay(3000)
                connect()
            }
        }
    }
}
