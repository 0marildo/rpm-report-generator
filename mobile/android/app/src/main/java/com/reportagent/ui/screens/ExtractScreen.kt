package com.reportagent.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

@Composable
fun ExtractScreen(
    pdfUris: List<Uri>,
    extractedFields: Map<String, String>,
    isLoading: Boolean,
    extractionSuccess: Boolean,
    onPdfsSelected: (List<Uri>) -> Unit,
    onExtract: () -> Unit,
) {
    val context = LocalContext.current

    val pdfPicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments()
    ) { uris -> onPdfsSelected(uris) }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Extract Data", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))

        Button(onClick = { pdfPicker.launch(arrayOf("application/pdf")) }) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Select PDFs")
        }

        if (pdfUris.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("${pdfUris.size} file(s) selected", style = MaterialTheme.typography.bodySmall)
                    pdfUris.forEach { uri ->
                        val name = uri.lastPathSegment?.substringAfterLast('/') ?: uri.toString()
                        Text("  • $name", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            Button(
                onClick = onExtract,
                enabled = !isLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                }
                Text("Extract Fields")
            }
        }

        if (extractionSuccess && extractedFields.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            Text("Extracted Fields", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))

            LazyColumn {
                items(extractedFields.entries.toList()) { (key, value) ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(key, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                            Text(value, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}
