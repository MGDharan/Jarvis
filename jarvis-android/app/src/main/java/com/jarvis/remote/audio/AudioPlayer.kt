package com.jarvis.remote.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Base64
import java.io.File
import java.io.FileOutputStream

class AudioPlayer(private val context: Context) {

    private var mediaPlayer: MediaPlayer? = null

    fun playBase64Mp3(base64Audio: String, onCompletion: (() -> Unit)? = null) {
        if (base64Audio.isBlank()) return

        try {
            stop()

            val audioBytes = Base64.decode(base64Audio, Base64.DEFAULT)
            val tempFile = File.createTempFile("jarvis_speech", ".mp3", context.cacheDir)
            tempFile.deleteOnExit()

            val fos = FileOutputStream(tempFile)
            fos.write(audioBytes)
            fos.flush()
            fos.close()

            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .build()
                )
                setDataSource(tempFile.absolutePath)
                prepare()
                setOnCompletionListener {
                    stop()
                    tempFile.delete()
                    onCompletion?.invoke()
                }
                start()
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun stop() {
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
        } catch (e: Exception) {
            // Ignore release exceptions
        } finally {
            mediaPlayer = null
        }
    }
}
