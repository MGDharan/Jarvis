package com.jarvis.remote.data.model

import com.google.gson.annotations.SerializedName

// ── Outgoing Command Model ──────────────────────────────────────────────────
data class CommandRequest(
    @SerializedName("request_id") val requestId: String,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("type") val type: String = "command",
    @SerializedName("command") val command: String,
    @SerializedName("arguments") val arguments: Map<String, Any?> = emptyMap()
)

// ── Ingoing Server Response ─────────────────────────────────────────────────
data class ServerResponse(
    @SerializedName("type") val type: String? = null,
    @SerializedName("data") val data: ResponseData? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("message") val message: String? = null
)

data class ResponseData(
    @SerializedName("request_id") val requestId: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("command") val command: String? = null,
    @SerializedName("message") val message: String? = null,
    @SerializedName("audio_b64") val audioB64: String? = null,
    @SerializedName("telemetry") val telemetry: TelemetryData? = null,
    @SerializedName("results") val results: List<FileSearchResult>? = null,
    @SerializedName("transfer") val transfer: TransferMetadata? = null,
    @SerializedName("challenge") val challenge: ConfirmationChallenge? = null,
    @SerializedName("notifications") val notifications: List<NotificationRecord>? = null,
    @SerializedName("is_active") val isActive: Boolean? = null
)

// ── Telemetry ───────────────────────────────────────────────────────────────
data class TelemetryData(
    @SerializedName("cpu_percent") val cpuPercent: Float = 0f,
    @SerializedName("ram_percent") val ramPercent: Float = 0f,
    @SerializedName("ram_used_gb") val ramUsedGb: Float = 0f,
    @SerializedName("ram_total_gb") val ramTotalGb: Float = 0f,
    @SerializedName("gpu") val gpu: GpuData = GpuData(),
    @SerializedName("battery") val battery: BatteryData = BatteryData(),
    @SerializedName("disk") val disk: DiskData = DiskData()
)

data class GpuData(
    @SerializedName("load_percent") val loadPercent: Float = -1f,
    @SerializedName("memory_percent") val memoryPercent: Float = -1f,
    @SerializedName("temp_c") val tempC: Float = -1f,
    @SerializedName("name") val name: String = "N/A"
)

data class BatteryData(
    @SerializedName("percent") val percent: Float = 100f,
    @SerializedName("power_plugged") val powerPlugged: Boolean = true,
    @SerializedName("has_battery") val hasBattery: Boolean = true
)

data class DiskData(
    @SerializedName("percent") val percent: Float = 0f,
    @SerializedName("free_gb") val freeGb: Float = 0f,
    @SerializedName("total_gb") val totalGb: Float = 0f
)

// ── Files & Transfer ────────────────────────────────────────────────────────
data class FileSearchResult(
    @SerializedName("name") val name: String,
    @SerializedName("path") val path: String,
    @SerializedName("is_dir") val isDir: Boolean,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("extension") val extension: String,
    @SerializedName("modified_at") val modifiedAt: String
)

data class TransferMetadata(
    @SerializedName("transfer_id") val transferId: String,
    @SerializedName("filename") val filename: String,
    @SerializedName("file_count") val fileCount: Int,
    @SerializedName("total_bytes") val totalBytes: Long,
    @SerializedName("total_mb") val totalMb: Float,
    @SerializedName("sha256") val sha256: String,
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false
)

// ── Confirmation Challenge for Dangerous Actions ────────────────────────────
data class ConfirmationChallenge(
    @SerializedName("challenge_id") val challengeId: String,
    @SerializedName("action") val action: String,
    @SerializedName("message") val message: String,
    @SerializedName("expires_in_seconds") val expiresInSeconds: Int = 60
)

// ── Push Notifications ──────────────────────────────────────────────────────
data class NotificationRecord(
    @SerializedName("id") val id: String,
    @SerializedName("timestamp") val timestamp: String,
    @SerializedName("type") val type: String,
    @SerializedName("title") val title: String,
    @SerializedName("message") val message: String,
    @SerializedName("severity") val severity: String,
    @SerializedName("has_image") val hasImage: Boolean = false,
    @SerializedName("image_b64") val imageB64: String? = null
)

// ── QR Pairing Model ────────────────────────────────────────────────────────
data class QRPairingPayload(
    @SerializedName("v") val version: Int = 1,
    @SerializedName("gateway_url") val gatewayUrl: String,
    @SerializedName("http_url") val httpUrl: String,
    @SerializedName("pairing_token") val pairingToken: String,
    @SerializedName("expires_at") val expiresAt: Long
)

// ── Conversation UI Message ─────────────────────────────────────────────────
data class ChatMessage(
    val id: String,
    val sender: String, // "USER" | "JARVIS"
    val text: String,
    val timestamp: Long = System.currentTimeMillis(),
    val challenge: ConfirmationChallenge? = null,
    val transfer: TransferMetadata? = null,
    val audioB64: String? = null
)
