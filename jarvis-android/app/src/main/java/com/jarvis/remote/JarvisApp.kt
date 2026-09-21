package com.jarvis.remote

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class JarvisApp : Application() {

    companion object {
        const val CHANNEL_ALERTS = "jarvis_alerts_channel"
        const val CHANNEL_STATUS = "jarvis_status_channel"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val alertsChannel = NotificationChannel(
                CHANNEL_ALERTS,
                "JARVIS Security & Motion Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Critical alerts like lab motion detection and hardware warnings"
                enableVibration(true)
            }

            val statusChannel = NotificationChannel(
                CHANNEL_STATUS,
                "JARVIS System Updates",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "File transfer completion and background status updates"
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(alertsChannel)
            notificationManager.createNotificationChannel(statusChannel)
        }
    }
}
