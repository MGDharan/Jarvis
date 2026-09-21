package com.jarvis.remote.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.ui.theme.*

data class QuickActionItem(
    val title: String,
    val icon: ImageVector
)

val defaultQuickActions = listOf(
    QuickActionItem("System Health", Icons.Default.Analytics),
    QuickActionItem("Sentry Mode", Icons.Default.Security),
    QuickActionItem("Lock Workstation", Icons.Default.Lock),
    QuickActionItem("Screen Grab", Icons.Default.Screenshot),
    QuickActionItem("Mute Audio", Icons.Default.VolumeMute),
    QuickActionItem("Sleep PC", Icons.Default.Bedtime)
)

@Composable
fun CommandPillsRow(
    onActionClick: (String) -> Unit,
    modifier: Modifier = Modifier,
    actions: List<QuickActionItem> = defaultQuickActions
) {
    LazyRow(
        modifier = modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(actions) { item ->
            Surface(
                color = JarvisSurface.copy(alpha = 0.85f),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier
                    .border(1.dp, JarvisBorderGlow, RoundedCornerShape(20.dp))
                    .clickable { onActionClick(item.title) }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        imageVector = item.icon,
                        contentDescription = item.title,
                        tint = JarvisCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = item.title,
                        color = JarvisText,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}
