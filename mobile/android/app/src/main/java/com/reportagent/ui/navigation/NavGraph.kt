package com.reportagent.ui.navigation

sealed class Screen(val route: String, val label: String) {
    data object Setup : Screen("setup", "Server")
    data object Home : Screen("home", "Dashboard")
    data object Extract : Screen("extract", "Extract")
    data object Images : Screen("images", "Images")
    data object Generate : Screen("generate", "Generate")
}

val bottomNavItems = listOf(Screen.Home, Screen.Extract, Screen.Images, Screen.Generate)
