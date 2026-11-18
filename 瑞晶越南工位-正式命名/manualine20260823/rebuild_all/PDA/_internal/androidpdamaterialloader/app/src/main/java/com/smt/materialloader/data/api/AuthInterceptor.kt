package com.smt.materialloader.data.api

import com.smt.materialloader.util.PreferencesManager
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val prefs: PreferencesManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()

        // Skip auth header for login
        if (original.url.encodedPath.contains("/auth/login")) {
            return chain.proceed(original)
        }

        val token = prefs.getJwtToken()
        if (token != null) {
            val request = original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
            return chain.proceed(request)
        }

        return chain.proceed(original)
    }
}
