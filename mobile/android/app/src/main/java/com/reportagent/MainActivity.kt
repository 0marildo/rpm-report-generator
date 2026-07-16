package com.reportagent

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.reportagent.ui.navigation.Screen
import com.reportagent.ui.navigation.bottomNavItems
import com.reportagent.ui.screens.*
import com.reportagent.ui.theme.ReportAgentTheme
import com.reportagent.viewmodel.ReportViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ReportAgentTheme {
                ReportApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportApp(viewModel: ReportViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var currentScreen by remember { mutableStateOf<Screen>(Screen.Setup) }
    var showError by remember { mutableStateOf(false) }

    LaunchedEffect(state.error) {
        if (state.error != null) showError = true
    }

    if (!state.isConnected || currentScreen == Screen.Setup) {
        SetupScreen(
            currentUrl = state.serverUrl,
            isConnected = state.isConnected,
            isLoading = state.isLoading,
            onUrlChange = { viewModel.updateServerUrl(it) },
            onConnect = {
                viewModel.checkConnection()
                currentScreen = Screen.Home
            },
        )
        return
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                bottomNavItems.forEach { screen ->
                    NavigationBarItem(
                        selected = currentScreen == screen,
                        onClick = { currentScreen = screen },
                        icon = {
                            Icon(
                                when (screen) {
                                    Screen.Home -> Icons.Default.Home
                                    Screen.Extract -> Icons.Default.Description
                                    Screen.Images -> Icons.Default.Image
                                    Screen.Generate -> Icons.Default.PictureAsPdf
                                    else -> Icons.Default.MoreHoriz
                                },
                                contentDescription = screen.label,
                            )
                        },
                        label = { Text(screen.label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            when (currentScreen) {
                Screen.Home -> HomeScreen(
                    isConnected = state.isConnected,
                    templates = state.templates,
                    onNavigateToExtract = { currentScreen = Screen.Extract },
                )
                Screen.Extract -> ExtractScreen(
                    pdfUris = state.pdfUris,
                    extractedFields = state.extractedFields,
                    isLoading = state.isLoading,
                    extractionSuccess = state.extractionSuccess,
                    onPdfsSelected = { viewModel.setPdfUris(it) },
                    onExtract = { viewModel.extractPdfs(this@Box.context) },
                )
                Screen.Images -> ImagesScreen(
                    imageUris = state.imageUris,
                    imageCategories = state.imageCategories,
                    categoryOptions = state.categoryOptions,
                    isLoading = state.isLoading,
                    onImagesSelected = { viewModel.setImageUris(it) },
                    onCategoryChange = { i, c -> viewModel.setImageCategory(i, c) },
                    onGenerate = {
                        viewModel.generateReport(this@Box.context)
                        currentScreen = Screen.Generate
                    },
                )
                Screen.Generate -> GenerateScreen(
                    generationSuccess = state.generationSuccess,
                    generatedPdfBytes = state.generatedPdfBytes,
                    extractedFields = state.extractedFields,
                    numImages = state.imageUris.size,
                    onReset = {
                        viewModel.reset()
                        currentScreen = Screen.Home
                    },
                )
                else -> HomeScreen(
                    isConnected = state.isConnected,
                    templates = state.templates,
                    onNavigateToExtract = { currentScreen = Screen.Extract },
                )
            }
        }
    }

    if (showError && state.error != null) {
        AlertDialog(
            onDismissRequest = { showError = false; viewModel.clearError() },
            title = { Text("Error") },
            text = { Text(state.error ?: "") },
            confirmButton = {
                TextButton(onClick = { showError = false; viewModel.clearError() }) {
                    Text("OK")
                }
            },
        )
    }
}
