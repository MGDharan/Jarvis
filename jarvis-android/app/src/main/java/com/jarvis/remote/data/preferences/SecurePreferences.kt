package com.jarvis.remote.data.preferences

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SecurePreferences(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs: SharedPreferences = try {
        EncryptedSharedPreferences.create(
            context,
            "jarvis_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    } catch (e: Exception) {
        // Fallback to standard prefs if Android Keystore has temporary issues on certain emulators
        context.getSharedPreferences("jarvis_fallback_prefs", Context.MODE_PRIVATE)
    }

    var isPaired: Boolean
        get() = prefs.getBoolean("is_paired", false)
        set(value) = prefs.edit().putBoolean("is_paired", value).apply()

    var deviceId: String
        get() = prefs.getString("device_id", "") ?: ""
        set(value) = prefs.edit().putString("device_id", value).apply()

    var authToken: String
        get() = prefs.getString("auth_token", "") ?: ""
        set(value) = prefs.edit().putString("auth_token", value).apply()

    var gatewayUrl: String
        get() = prefs.getString("gateway_url", "ws://192.168.1.100:8765/ws/remote") ?: "ws://192.168.1.100:8765/ws/remote"
        set(value) = prefs.edit().putString("gateway_url", value).apply()

    var httpUrl: String
        get() = prefs.getString("http_url", "http://192.168.1.100:8765") ?: "http://192.168.1.100:8765"
        set(value) = prefs.edit().putString("http_url", value).apply()

    var serverName: String
        get() = prefs.getString("server_name", "JARVIS Lab Laptop") ?: "JARVIS Lab Laptop"
        set(value) = prefs.edit().putString("server_name", value).apply()

    fun clearAll() {
        prefs.edit().clear().apply()
    }
}
