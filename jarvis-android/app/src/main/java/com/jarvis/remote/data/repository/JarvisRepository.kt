package com.jarvis.remote.data.repository

import android.content.Context
import com.jarvis.remote.data.model.ChatMessage
import com.jarvis.remote.data.model.FileSearchResult
import com.jarvis.remote.data.model.NotificationRecord
import com.jarvis.remote.data.model.TelemetryData
import com.jarvis.remote.data.model.TransferMetadata
import com.jarvis.remote.data.preferences.SecurePreferences
import com.jarvis.remote.network.ConnectionStatus
import com.jarvis.remote.network.DownloadState
import com.jarvis.remote.network.FileDownloader
import com.jarvis.remote.network.JarvisWebSocketClient
import com.jarvis.remote.network.PairingService
import com.jarvis.remote.notifications.JarvisNotificationManager
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

class JarvisRepository(
    private val context: Context,
    val securePrefs: SecurePreferences = SecurePreferences(context),
    private val wsClient: JarvisWebSocketClient = JarvisWebSocketClient(securePrefs),
    private val pairingService: PairingService = PairingService(securePrefs),
    private val fileDownloader: FileDownloader = FileDownloader(context, securePrefs),
    private val notificationManager: JarvisNotificationManager = JarvisNotificationManager(context)
) {

    val connectionStatus: StateFlow<ConnectionStatus> = wsClient.connectionStatus
    val telemetry: StateFlow<TelemetryData> = wsClient.latestTelemetry
    val incomingMessages: StateFlow<ChatMessage?> = wsClient.incomingMessages
    val searchResults: StateFlow<List<FileSearchResult>> = wsClient.searchResults
    val incomingAudio: SharedFlow<String> = wsClient.incomingAudio
    val notifications: StateFlow<NotificationRecord?> = wsClient.notifications

    val isPaired: Boolean
        get() = securePrefs.isPaired

    val serverName: String
        get() = securePrefs.serverName

    val deviceId: String
        get() = securePrefs.deviceId

    val gatewayUrl: String
        get() = securePrefs.gatewayUrl

    fun connect() {
        if (securePrefs.isPaired) {
            wsClient.connect()
        }
    }

    fun disconnect() {
        wsClient.disconnect()
    }

    fun sendCommand(command: String, arguments: Map<String, Any?> = emptyMap()): String {
        return wsClient.sendCommand(command, arguments)
    }

    fun sendVoiceQuery(query: String) {
        wsClient.sendVoiceQuery(query)
    }

    fun downloadFile(transfer: TransferMetadata): Flow<DownloadState> {
        return fileDownloader.downloadFile(transfer)
    }

    suspend fun pairWithQr(qrJsonString: String): Result<String> {
        val result = pairingService.pairWithQrString(qrJsonString)
        if (result.isSuccess) {
            wsClient.connect()
        }
        return result
    }

    fun unpair() {
        wsClient.disconnect()
        securePrefs.clearAll()
    }

    fun dispatchNotification(record: NotificationRecord) {
        notificationManager.postNotification(record)
    }
}
