package com.reportagent.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImagesScreen(
    imageUris: List<Uri>,
    imageCategories: Map<String, String>,
    categoryOptions: List<String>,
    isLoading: Boolean,
    onImagesSelected: (List<Uri>) -> Unit,
    onCategoryChange: (Int, String) -> Unit,
    onGenerate: () -> Unit,
) {
    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        onImagesSelected(uris.filter { uri ->
            val path = uri.toString().lowercase()
            path.endsWith(".jpg") || path.endsWith(".jpeg") ||
            path.endsWith(".png") || path.endsWith(".webp") ||
            path.endsWith(".gif") || path.endsWith(".tiff") ||
            path.endsWith(".bmp")
        })
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Add Photos", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))

        Button(onClick = { imagePicker.launch(arrayOf("image/*")) }) {
            Icon(Icons.Default.AddPhotoAlternate, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Select Images")
        }

        Spacer(Modifier.height(12.dp))

        if (imageUris.isNotEmpty()) {
            LazyColumn(modifier = Modifier.weight(1f)) {
                itemsIndexed(imageUris) { index, uri ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    ) {
                        Row(modifier = Modifier.padding(8.dp)) {
                            AsyncImage(
                                model = uri,
                                contentDescription = null,
                                modifier = Modifier.size(80.dp),
                                contentScale = ContentScale.Crop,
                            )
                            Spacer(Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Image ${index + 1}", style = MaterialTheme.typography.bodySmall)
                                Spacer(Modifier.height(4.dp))
                                var expanded by remember { mutableStateOf(false) }
                                val currentCat = imageCategories["image_$index"] ?: "outro"
                                ExposedDropdownMenuBox(
                                    expanded = expanded,
                                    onExpandedChange = { expanded = it },
                                ) {
                                    OutlinedTextField(
                                        value = currentCat,
                                        onValueChange = {},
                                        readOnly = true,
                                        label = { Text("Category") },
                                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                                        modifier = Modifier.menuAnchor(),
                                    )
                                    ExposedDropdownMenu(
                                        expanded = expanded,
                                        onDismissRequest = { expanded = false },
                                    ) {
                                        categoryOptions.forEach { cat ->
                                            DropdownMenuItem(
                                                text = { Text(cat) },
                                                onClick = {
                                                    onCategoryChange(index, cat)
                                                    expanded = false
                                                },
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(12.dp))
            Button(
                onClick = onGenerate,
                enabled = !isLoading && imageUris.isNotEmpty(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                }
                Text("Generate Report")
            }
        }
    }
}
