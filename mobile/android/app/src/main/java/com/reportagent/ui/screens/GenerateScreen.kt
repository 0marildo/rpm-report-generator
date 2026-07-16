package com.reportagent.ui.screens

import android.content.Context
import android.os.Environment
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.io.File

@Composable
fun GenerateScreen(
    generationSuccess: Boolean,
    generatedPdfBytes: ByteArray?,
    extractedFields: Map<String, String>,
    numImages: Int,
    onReset: () -> Unit,
) {
    val context = LocalContext.current

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Generate Report", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(24.dp))

        if (extractedFields.isNotEmpty()) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Extracted Fields", style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    extractedFields.entries.take(5).forEach { (k, v) ->
                        Text("${k}: $v", style = MaterialTheme.typography.bodySmall)
                    }
                    if (extractedFields.size > 5) {
                        Text("... and ${extractedFields.size - 5} more", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Images", style = MaterialTheme.typography.titleSmall)
                Text("$numImages image(s) ready", style = MaterialTheme.typography.bodySmall)
            }
        }

        Spacer(Modifier.height(24.dp))

        if (generationSuccess && generatedPdfBytes != null) {
            Icon(
                Icons.Default.CheckCircle,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(12.dp))
            Text("Report Generated!", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(8.dp))
            Text("${generatedPdfBytes.size / 1024} KB", style = MaterialTheme.typography.bodyMedium)

            Spacer(Modifier.height(16.dp))

            Button(
                onClick = {
                    val dir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                    val file = File(dir, "report.pdf")
                    file.parentFile?.mkdirs()
                    file.writeBytes(generatedPdfBytes)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Download, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Save to Downloads")
            }

            Spacer(Modifier.height(8.dp))

            OutlinedButton(
                onClick = onReset,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Start New Report")
            }
        } else {
            Text(
                "Upload PDFs and images in the previous steps, then tap Generate.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
