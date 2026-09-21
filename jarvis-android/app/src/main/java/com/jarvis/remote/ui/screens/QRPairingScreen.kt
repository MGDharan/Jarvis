package com.jarvis.remote.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.jarvis.remote.ui.theme.*
import kotlinx.coroutines.launch
import java.util.concurrent.Executors

@OptIn(ExperimentalGetImage::class)
@Composable
fun QRPairingScreen(
    onPairSuccess: () -> Unit,
    onPairWithJson: suspend (String) -> Result<String>,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted -> hasCameraPermission = granted }
    )

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            launcher.launch(Manifest.permission.CAMERA)
        }
    }

    var manualJson by remember { mutableStateOf("") }
    var statusMessage by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }

    fun processBarcodeText(text: String) {
        if (isLoading) return
        isLoading = true
        statusMessage = "Pairing with lab laptop…"
        scope.launch {
            val result = onPairWithJson(text)
            isLoading = false
            if (result.isSuccess) {
                statusMessage = "Pairing successful!"
                onPairSuccess()
            } else {
                statusMessage = "Error: ${result.exceptionOrNull()?.message}"
            }
        }
    }

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "PAIR WITH JARVIS",
                    color = JarvisCyan,
                    fontSize = 20.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 2.sp
                )
                Text(
                    text = "Scan the QR code on your laptop screen",
                    color = JarvisTextDim,
                    fontSize = 12.sp
                )
            }
        },
        containerColor = JarvisBackground
    ) { padding ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            if (hasCameraPermission) {
                Box(
                    modifier = Modifier
                        .size(260.dp)
                        .border(2.dp, JarvisCyan, RoundedCornerShape(16.dp))
                        .background(JarvisSurface, RoundedCornerShape(16.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    AndroidView(
                        factory = { ctx ->
                            val previewView = PreviewView(ctx)
                            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                            val executor = Executors.newSingleThreadExecutor()

                            cameraProviderFuture.addListener({
                                val cameraProvider = cameraProviderFuture.get()
                                val preview = Preview.Builder().build().also {
                                    it.setSurfaceProvider(previewView.surfaceProvider)
                                }

                                val scanner = BarcodeScanning.getClient()
                                val imageAnalysis = ImageAnalysis.Builder()
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    .build()

                                imageAnalysis.setAnalyzer(executor) { imageProxy ->
                                    @ExperimentalGetImage
                                    val mediaImage = imageProxy.image
                                    if (mediaImage != null) {
                                        val image = InputImage.fromMediaImage(
                                            mediaImage,
                                            imageProxy.imageInfo.rotationDegrees
                                        )
                                        scanner.process(image)
                                            .addOnSuccessListener { barcodes ->
                                                for (barcode in barcodes) {
                                                    val raw = barcode.rawValue
                                                    if (!raw.isNullOrBlank() && raw.contains("pairing_token")) {
                                                        processBarcodeText(raw)
                                                        break
                                                    }
                                                }
                                            }
                                            .addOnCompleteListener {
                                                imageProxy.close()
                                            }
                                    } else {
                                        imageProxy.close()
                                    }
                                }

                                try {
                                    cameraProvider.unbindAll()
                                    cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        CameraSelector.DEFAULT_BACK_CAMERA,
                                        preview,
                                        imageAnalysis
                                    )
                                } catch (e: Exception) {
                                    e.printStackTrace()
                                }
                            }, ContextCompat.getMainExecutor(ctx))

                            previewView
                        },
                        modifier = Modifier.fillMaxSize()
                    )
                }
            } else {
                Surface(
                    color = JarvisSurface,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "Camera permission is required to scan QR code.",
                        color = JarvisWarning,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            if (isLoading) {
                CircularProgressIndicator(color = JarvisCyan)
            }

            if (statusMessage.isNotBlank()) {
                Text(
                    text = statusMessage,
                    color = if (statusMessage.startsWith("Error")) JarvisDanger else JarvisOnline,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Manual JSON entry fallback
            OutlinedTextField(
                value = manualJson,
                onValueChange = { manualJson = it },
                placeholder = { Text("Or paste pairing JSON payload here…", color = JarvisTextDim, fontSize = 12.sp) },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = JarvisCyan,
                    unfocusedBorderColor = JarvisBorder,
                    focusedTextColor = JarvisText,
                    unfocusedTextColor = JarvisText
                ),
                shape = RoundedCornerShape(8.dp)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Button(
                onClick = { processBarcodeText(manualJson) },
                enabled = manualJson.isNotBlank() && !isLoading,
                colors = ButtonDefaults.buttonColors(containerColor = JarvisCyan),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("PAIR MANUALLY", color = JarvisBackground, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            }
        }
    }
}
