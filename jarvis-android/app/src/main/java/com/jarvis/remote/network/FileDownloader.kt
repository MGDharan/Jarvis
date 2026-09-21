package com.jarvis.remote.network

import android.content.Context
import android.os.Environment
import com.jarvis.remote.data.model.TransferMetadata
import com.jarvis.remote.data.preferences.SecurePreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest

sealed class DownloadState {
    data class Progress(val percentage: Int, val downloadedBytes: Long, val totalBytes: Long) : DownloadState()
    data class Success(val savedFile: File, val sha256Verified: Boolean) : DownloadState()
    data class Error(val message: String) : DownloadState()
}

class FileDownloader(
    private val context: Context,
    private val securePrefs: SecurePreferences,
    private val client: OkHttpClient = OkHttpClient()
) {

    fun downloadFile(transfer: TransferMetadata): Flow<DownloadState> = flow {
        val downloadUrl = "${securePrefs.httpUrl.trimEnd('/')}/api/transfer/${transfer.transferId}" +
                "?device_id=${securePrefs.deviceId}&auth_token=${securePrefs.authToken}"

        val request = Request.Builder().url(downloadUrl).build()

        try {
            val response = client.newCall(request).execute()
            if (!response.isSuccessful) {
                emit(DownloadState.Error("Server returned error: HTTP ${response.code}"))
                return@flow
            }

            val body = response.body ?: run {
                emit(DownloadState.Error("Empty response body"))
                return@flow
            }

            val targetDir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                ?: Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            if (!targetDir.exists()) {
                targetDir.mkdirs()
            }
            val destinationFile = File(targetDir, transfer.filename)

            val inputStream = body.byteStream()
            val outputStream = FileOutputStream(destinationFile)
            val digest = MessageDigest.getInstance("SHA-256")

            val buffer = ByteArray(8192)
            var bytesRead: Int
            var totalDownloaded: Long = 0
            val totalLength = if (body.contentLength() > 0) body.contentLength() else transfer.totalBytes

            while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                outputStream.write(buffer, 0, bytesRead)
                digest.update(buffer, 0, bytesRead)
                totalDownloaded += bytesRead

                if (totalLength > 0) {
                    val progress = ((totalDownloaded * 100) / totalLength).toInt()
                    emit(DownloadState.Progress(progress, totalDownloaded, totalLength))
                }
            }

            outputStream.flush()
            outputStream.close()
            inputStream.close()

            val computedSha256 = digest.digest().joinToString("") { "%02x".format(it) }
            val shaMatches = computedSha256.equals(transfer.sha256, ignoreCase = true)

            emit(DownloadState.Success(destinationFile, shaMatches))
        } catch (e: Exception) {
            emit(DownloadState.Error(e.message ?: "Download failed"))
        }
    }.flowOn(Dispatchers.IO)
}
