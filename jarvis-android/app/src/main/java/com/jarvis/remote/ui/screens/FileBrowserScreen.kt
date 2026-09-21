package com.jarvis.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.data.model.FileSearchResult
import com.jarvis.remote.ui.theme.*

@Composable
fun FileBrowserScreen(
    searchResults: List<FileSearchResult>,
    downloadProgress: Int?,
    activeDownloadFilename: String? = null,
    onSearch: (String) -> Unit,
    onDownloadFile: (FileSearchResult) -> Unit,
    modifier: Modifier = Modifier
) {
    var searchQuery by remember { mutableStateOf("") }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(JarvisBackground)
            .padding(16.dp)
    ) {
        Text(
            text = "REMOTE CLOUD EXPLORER",
            color = JarvisCyan,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp
        )
        Text(
            text = "Search & download authorized files from workstation",
            color = JarvisTextDim,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Search Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("Search files or directories (e.g. project, log, data)…", color = JarvisTextDim, fontSize = 12.sp) },
                modifier = Modifier.weight(1f),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = JarvisCyan,
                    unfocusedBorderColor = JarvisBorder,
                    focusedTextColor = JarvisText,
                    unfocusedTextColor = JarvisText
                ),
                shape = RoundedCornerShape(8.dp),
                singleLine = true
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = { if (searchQuery.isNotBlank()) onSearch(searchQuery) },
                modifier = Modifier
                    .size(48.dp)
                    .background(JarvisCyan, RoundedCornerShape(8.dp))
            ) {
                Icon(Icons.Default.Search, contentDescription = "Search", tint = JarvisBackground)
            }
        }

        // Active Download Progress Banner
        if (downloadProgress != null) {
            Spacer(modifier = Modifier.height(12.dp))
            Surface(
                color = JarvisSurfaceCard,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, JarvisCyan, RoundedCornerShape(8.dp))
                    .padding(12.dp)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "DOWNLOADING: ${activeDownloadFilename ?: "FILE"}",
                            color = JarvisCyanBright,
                            fontSize = 12.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "$downloadProgress%",
                            color = JarvisCyan,
                            fontSize = 12.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    LinearProgressIndicator(
                        progress = downloadProgress / 100f,
                        modifier = Modifier.fillMaxWidth(),
                        color = JarvisCyan,
                        trackColor = JarvisSurfaceLight
                    )
                }
            }
        }

        // Search Results List
        Spacer(modifier = Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "SEARCH MATCHES (${searchResults.size})",
                color = JarvisTextDim,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            if (searchResults.isNotEmpty()) {
                Text(
                    text = "TAP TO DOWNLOAD",
                    color = JarvisTextMuted,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        if (searchResults.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "NO FILES MATCHED // TYPE QUERY ABOVE",
                    color = JarvisTextMuted,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(searchResults) { item ->
                    FileItemRow(item = item, onDownload = { onDownloadFile(item) })
                }
            }
        }
    }
}

@Composable
fun FileItemRow(
    item: FileSearchResult,
    onDownload: () -> Unit
) {
    val (icon, iconColor) = when {
        item.isDir -> Icons.Default.Folder to JarvisWarning
        item.extension in listOf("py", "kt", "js", "html", "css", "json", "xml", "sh") -> Icons.Default.Code to JarvisCyan
        item.extension in listOf("png", "jpg", "jpeg", "mp4", "mp3") -> Icons.Default.Image to JarvisPurpleHolo
        item.extension in listOf("zip", "tar", "gz", "rar") -> Icons.Default.Archive to JarvisArcOrange
        else -> Icons.Default.InsertDriveFile to JarvisTextDim
    }

    Surface(
        color = JarvisSurfaceCard,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, JarvisBorder, RoundedCornerShape(8.dp))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = iconColor,
                modifier = Modifier.size(28.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = item.name,
                    color = JarvisText,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = item.path,
                    color = JarvisTextMuted,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 1
                )
                if (!item.isDir && item.sizeBytes > 0) {
                    val formattedSize = formatBytes(item.sizeBytes)
                    Text(
                        text = "SIZE: $formattedSize // ${item.modifiedAt.take(19)}",
                        color = JarvisTextDim,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
            if (!item.isDir) {
                IconButton(onClick = onDownload) {
                    Icon(Icons.Default.Download, contentDescription = "Download", tint = JarvisCyan)
                }
            }
        }
    }
}

private fun formatBytes(bytes: Long): String {
    return when {
        bytes >= 1024 * 1024 * 1024 -> String.format("%.2f GB", bytes.toDouble() / (1024 * 1024 * 1024))
        bytes >= 1024 * 1024 -> String.format("%.1f MB", bytes.toDouble() / (1024 * 1024))
        bytes >= 1024 -> "${bytes / 1024} KB"
        else -> "$bytes B"
    }
}
