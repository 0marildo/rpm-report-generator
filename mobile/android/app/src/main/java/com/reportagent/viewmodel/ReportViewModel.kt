package com.reportagent.viewmodel

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.reportagent.BuildConfig
import com.reportagent.api.ApiService
import com.reportagent.api.ExtractResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream

data class UiState(
    val serverUrl: String = BuildConfig.DEFAULT_SERVER_URL,
    val isConnected: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,

    val templates: List<String> = emptyList(),

    val pdfUris: List<Uri> = emptyList(),
    val extractedFields: Map<String, String> = emptyMap(),
    val extractionSuccess: Boolean = false,

    val imageUris: List<Uri> = emptyList(),
    val imageCategories: MutableMap<String, String> = mutableMapOf(),
    val categoryOptions: List<String> = listOf(
        "extintor", "hidrante_recalque", "hidrante_urbano", "hidrante_caixa",
        "cmi", "bomba", "alarme", "sinalizacao", "sprinkler",
        "iluminacao_emergencia", "saida_emergencia", "risco_especifico",
        "fachada", "le_print", "pressurizacao", "outro",
    ),

    val generationSuccess: Boolean = false,
    val generatedPdfBytes: ByteArray? = null,

    val numPages: Int = 0,
    val numImages: Int = 0,
)

class ReportViewModel : ViewModel() {
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var api: ApiService? = null

    fun updateServerUrl(url: String) {
        _state.value = _state.value.copy(serverUrl = url)
        ApiService.reset()
        api = null
    }

    fun checkConnection() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val svc = getApi()
                val health = svc.health()
                val templates = svc.templates()
                _state.value = _state.value.copy(
                    isConnected = health.status == "ok",
                    isLoading = false,
                    templates = templates.templates,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isConnected = false,
                    isLoading = false,
                    error = "Connection failed: ${e.localizedMessage}",
                )
            }
        }
    }

    fun setPdfUris(uris: List<Uri>) {
        _state.value = _state.value.copy(pdfUris = uris, extractionSuccess = false)
    }

    fun extractPdfs(context: android.content.Context) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val svc = getApi()
                val parts = _state.value.pdfUris.map { uri ->
                    val inputStream = context.contentResolver.openInputStream(uri)
                    val bytes = inputStream?.readBytes() ?: ByteArray(0)
                    inputStream?.close()
                    val requestBody = bytes.toRequestBody("application/pdf".toMediaTypeOrNull())
                    MultipartBody.Part.createFormData("files", "document.pdf", requestBody)
                }
                val response = svc.extract(files = parts)
                _state.value = _state.value.copy(
                    isLoading = false,
                    extractedFields = response.extractedFields,
                    extractionSuccess = response.success,
                    error = if (!response.success) response.error else null,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Extraction failed: ${e.localizedMessage}",
                )
            }
        }
    }

    fun setImageUris(uris: List<Uri>) {
        val cats = mutableMapOf<String, String>()
        uris.forEachIndexed { i, _ ->
            cats["image_$i"] = "outro"
        }
        _state.value = _state.value.copy(imageUris = uris, imageCategories = cats)
    }

    fun setImageCategory(index: Int, category: String) {
        val cats = _state.value.imageCategories.toMutableMap()
        cats["image_$index"] = category
        _state.value = _state.value.copy(imageCategories = cats)
    }

    fun generateReport(context: android.content.Context) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            try {
                val svc = getApi()
                val fieldsJson = com.google.gson.Gson().toJson(_state.value.extractedFields)

                val catMap = mutableMapOf<String, String>()
                val imageParts = mutableListOf<MultipartBody.Part>()

                _state.value.imageUris.forEachIndexed { i, uri ->
                    val inputStream = context.contentResolver.openInputStream(uri)
                    val bytes = inputStream?.readBytes() ?: ByteArray(0)
                    inputStream?.close()

                    val mimeType = detectMimeType(bytes)
                    val ext = when (mimeType) {
                        "image/png" -> "png"
                        "image/webp" -> "webp"
                        "image/gif" -> "gif"
                        "image/tiff" -> "tiff"
                        "image/bmp" -> "bmp"
                        else -> "jpg"
                    }
                    val filename = "image_$i.$ext"
                    catMap[filename] = _state.value.imageCategories["image_$i"] ?: "outro"

                    val requestBody = bytes.toRequestBody(mimeType.toMediaTypeOrNull())
                    imageParts.add(
                        MultipartBody.Part.createFormData("images", filename, requestBody)
                    )
                }

                val catJson = com.google.gson.Gson().toJson(catMap)

                val response = svc.generate(
                    extractedFields = fieldsJson,
                    imageCategories = catJson,
                    images = imageParts,
                )

                if (response.isSuccessful) {
                    val pdfBytes = response.body()?.bytes()
                    _state.value = _state.value.copy(
                        isLoading = false,
                        generationSuccess = true,
                        generatedPdfBytes = pdfBytes,
                        error = null,
                    )
                } else {
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = "Generation failed: HTTP ${response.code()}",
                    )
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Generation failed: ${e.localizedMessage}",
                )
            }
        }
    }

    private fun detectMimeType(data: ByteArray): String {
        if (data.size >= 4) {
            // JPEG: FF D8 FF
            if (data[0] == 0xFF.toByte() && data[1] == 0xD8.toByte() && data[2] == 0xFF.toByte()) {
                return "image/jpeg"
            }
            // PNG: 89 50 4E 47
            if (data[0] == 0x89.toByte() && data[1] == 0x50.toByte() && data[2] == 0x4E.toByte() && data[3] == 0x47.toByte()) {
                return "image/png"
            }
            // GIF: 47 49 46 38
            if (data[0] == 0x47.toByte() && data[1] == 0x49.toByte() && data[2] == 0x46.toByte() && data[3] == 0x38.toByte()) {
                return "image/gif"
            }
            // BMP: 42 4D
            if (data[0] == 0x42.toByte() && data[1] == 0x4D.toByte()) {
                return "image/bmp"
            }
            // TIFF: 49 49 or 4D 4D
            if ((data[0] == 0x49.toByte() && data[1] == 0x49.toByte()) ||
                (data[0] == 0x4D.toByte() && data[1] == 0x4D.toByte())) {
                return "image/tiff"
            }
        }
        if (data.size >= 12) {
            val riff = String(data, 0, 4, Charsets.US_ASCII)
            val webp = String(data, 8, 4, Charsets.US_ASCII)
            if (riff == "RIFF" && webp == "WEBP") {
                return "image/webp"
            }
        }
        return "image/jpeg"
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    fun reset() {
        _state.value = UiState(serverUrl = _state.value.serverUrl)
        ApiService.reset()
        api = null
    }

    private fun getApi(): ApiService {
        if (api == null) {
            api = ApiService.create(_state.value.serverUrl)
        }
        return api!!
    }
}
