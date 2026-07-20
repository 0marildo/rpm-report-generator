package com.reportagent.api

import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.util.concurrent.TimeUnit

interface ApiService {

    @GET("/health")
    suspend fun health(): HealthResponse

    @GET("/api/templates")
    suspend fun templates(): TemplatesResponse

    @Multipart
    @POST("/api/extract")
    suspend fun extract(
        @Part files: List<MultipartBody.Part>,
        @Part("user_context") userContext: String = "",
        @Part("report_type") reportType: String = "LAUDO_TECNICO_CIRCUNSTANCIADO",
        @Part("use_orchestrator") useOrchestrator: Boolean = true,
    ): ExtractResponse

    @Multipart
    @POST("/api/generate-report")
    suspend fun generate(
        @Part("extracted_fields") extractedFields: String,
        @Part("template_name") templateName: String = "template novo v2.pdf",
        @Part("output_filename") outputFilename: String = "report.pdf",
        @Part images: List<MultipartBody.Part>,
        @Part("image_categories") imageCategories: String = "{}",
    ): Response<ResponseBody>

    companion object {
        private var instance: ApiService? = null

        fun create(baseUrl: String): ApiService {
            instance?.let { return it }

            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            }

            val client = OkHttpClient.Builder()
                .addInterceptor(logging)
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(120, TimeUnit.SECONDS)
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl.trimEnd('/') + "/")
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            instance = retrofit.create(ApiService::class.java)
            return instance!!
        }

        fun reset() {
            instance = null
        }
    }
}
