package com.jarvis.remote.notifications

import android.Manifest
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.jarvis.remote.JarvisApp
import com.jarvis.remote.MainActivity
import com.jarvis.remote.data.model.NotificationRecord
import java.util.concurrent.atomic.AtomicInteger

class JarvisNotificationManager(private val context: Context) {

    private val notificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private val notificationIdGenerator = AtomicInteger(1001)

    fun postNotification(record: NotificationRecord) {
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val channelId = if (record.severity.equals("danger", ignoreCase = true) ||
            record.severity.equals("warning", ignoreCase = true) ||
            record.type.contains("motion", ignoreCase = true) ||
            record.type.contains("security", ignoreCase = true)
        ) {
            JarvisApp.CHANNEL_ALERTS
        } else {
            JarvisApp.CHANNEL_STATUS
        }

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("JARVIS: ${record.title}")
            .setContentText(record.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(record.message))
            .setPriority(
                if (channelId == JarvisApp.CHANNEL_ALERTS)
                    NotificationCompat.PRIORITY_HIGH
                else
                    NotificationCompat.PRIORITY_DEFAULT
            )
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)

        // If image attached in base64 (e.g. sentry camera snapshot)
        record.imageB64?.let { b64 ->
            try {
                val decoded = Base64.decode(b64, Base64.DEFAULT)
                val bitmap = BitmapFactory.decodeByteArray(decoded, 0, decoded.size)
                if (bitmap != null) {
                    builder.setLargeIcon(bitmap)
                    builder.setStyle(
                        NotificationCompat.BigPictureStyle()
                            .bigPicture(bitmap)
                            .setSummaryText(record.message)
                    )
                }
            } catch (e: Exception) {
                // Ignore image decode errors gracefully
            }
        }

        notificationManager.notify(notificationIdGenerator.incrementAndGet(), builder.build())
    }
}
