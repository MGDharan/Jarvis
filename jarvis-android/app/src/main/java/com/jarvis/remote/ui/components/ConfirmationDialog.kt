package com.jarvis.remote.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.remote.data.model.ConfirmationChallenge
import com.jarvis.remote.ui.theme.*

@Composable
fun ConfirmationDialog(
    challenge: ConfirmationChallenge,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                text = "⚠️ HIGH-RISK ACTION CONFIRMATION",
                color = JarvisWarning,
                fontFamily = FontFamily.Monospace,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = challenge.message,
                    color = JarvisText,
                    fontSize = 14.sp
                )
                Text(
                    text = "Expires in ${challenge.expiresInSeconds} seconds.",
                    color = JarvisTextDim,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(containerColor = JarvisDanger),
                shape = RoundedCornerShape(6.dp)
            ) {
                Text(
                    text = "CONFIRM ${challenge.action.uppercase()}",
                    color = JarvisText,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDismiss,
                shape = RoundedCornerShape(6.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = JarvisTextDim)
            ) {
                Text(
                    text = "CANCEL",
                    fontFamily = FontFamily.Monospace
                )
            }
        },
        containerColor = JarvisSurface,
        modifier = Modifier.border(1.dp, JarvisWarning.copy(alpha = 0.5f), RoundedCornerShape(16.dp))
    )
}
