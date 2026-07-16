package com.reportagent.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

data class StepCard(val icon: androidx.compose.ui.graphics.vector.ImageVector, val title: String, val desc: String)

@Composable
fun HomeScreen(
    isConnected: Boolean,
    templates: List<String>,
    onNavigateToExtract: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Text("Dashboard", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))

        Card(
            colors = CardDefaults.cardColors(
                containerColor = if (isConnected) MaterialTheme.colorScheme.primaryContainer
                else MaterialTheme.colorScheme.errorContainer
            ),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    if (isConnected) Icons.Default.CheckCircle else Icons.Default.Error,
                    contentDescription = null,
                )
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(
                        if (isConnected) "Server Connected" else "Not Connected",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    if (isConnected && templates.isNotEmpty()) {
                        Text(
                            "${templates.size} template(s) available",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(24.dp))

        Text("Workflow", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))

        val steps = listOf(
            StepCard(Icons.Default.Description, "1. Upload PDFs", "Extract inspection data from report PDFs"),
            StepCard(Icons.Default.Image, "2. Add Photos", "Upload images and assign categories"),
            StepCard(Icons.Default.PictureAsPdf, "3. Generate Report", "Create the final PDF with placed images"),
        )

        steps.forEach { step ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                onClick = onNavigateToExtract,
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(step.icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(step.title, style = MaterialTheme.typography.titleSmall)
                        Text(step.desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
