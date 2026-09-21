package com.jarvis.remote.network

import android.os.Build
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.jarvis.remote.data.model.QRPairingPayload
import com.jarvis.remote.data.preferences.SecurePreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class PairingService(
    private val securePrefs: SecurePreferences,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build(),
    private val gson: Gson = Gson()
) {

    suspend fun pairWithQrString(qrString: String): Result<String> = withContext(Dispatchers.IO) {
        try {
            val qrData = gson.fromJson(qrString.trim(), QRPairingPayload::class.java)
                ?: return@withContext Result.failure(IllegalArgumentException("Invalid QR code format"))

            val handshakeUrl = "${qrData.httpUrl.trimEnd('/')}/api/pair/handshake"

            val jsonBody = JsonObject().apply {
                addProperty("pairing_token", qrData.pairingToken)
                addProperty("device_name", "${Build.MANUFACTURER} ${Build.MODEL}")
                addProperty("device_model", "Android ${Build.VERSION.RELEASE}")
            }

            val requestBody = jsonBody.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url(handshakeUrl)
                .post(requestBody)
                .build()

            val response = client.newCall(request).execute()
            val respBody = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Pairing failed: HTTP ${response.code} ($respBody)"))
            }

            val respJson = gson.fromJson(respBody, JsonObject::class.java)
            val deviceId = respJson.get("device_id")?.asString
            val authToken = respJson.get("auth_token")?.asString
            val serverName = respJson.get("server_name")?.asString ?: "JARVIS Lab Laptop"

            if (deviceId.isNullOrBlank() || authToken.isNullOrBlank()) {
                return@withContext Result.failure(Exception("Incomplete credentials returned by server"))
            }

            // Save to encrypted storage
            securePrefs.deviceId = deviceId
            securePrefs.authToken = authToken
            securePrefs.gatewayUrl = qrData.gatewayUrl
            securePrefs.httpUrl = qrData.httpUrl
            securePrefs.serverName = serverName
            securePrefs.isPaired = true

            Result.success("Pairing complete! Connected to $serverName")
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
