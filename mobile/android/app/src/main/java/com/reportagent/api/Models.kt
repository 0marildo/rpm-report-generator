package com.reportagent.api

import com.google.gson.annotations.SerializedName

data class HealthResponse(val status: String)

data class TemplatesResponse(val templates: List<String>)

data class ExtractRequest(
    @SerializedName("user_context") val userContext: String = "",
    @SerializedName("report_type") val reportType: String = "LAUDO_TECNICO_CIRCUNSTANCIADO",
    @SerializedName("use_orchestrator") val useOrchestrator: Boolean = true,
)

data class ExtractResponse(
    val success: Boolean,
    @SerializedName("extracted_fields") val extractedFields: Map<String, String>,
    val error: String? = null,
)

data class GenerateRequest(
    @SerializedName("extracted_fields") val extractedFields: Map<String, String>,
    @SerializedName("template_name") val templateName: String = "template_images.pdf",
    @SerializedName("output_filename") val outputFilename: String = "report.pdf",
)

data class ImageCategory(
    val filename: String,
    val category: String,
)
