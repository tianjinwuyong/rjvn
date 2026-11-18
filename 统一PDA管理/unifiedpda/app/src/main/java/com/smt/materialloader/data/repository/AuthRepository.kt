package com.smt.materialloader.data.repository

import com.smt.materialloader.data.api.RetrofitClient
import com.smt.materialloader.data.api.dto.*
import com.smt.materialloader.util.PreferencesManager
import com.google.gson.Gson

class AuthRepository(
    private val prefs: PreferencesManager
) {
    private val api get() = RetrofitClient.getApiService()

    suspend fun login(username: String, password: String): Result<LoginResponse> {
        return try {
            val response = api.login(LoginRequest(username, password))
            if (response.isSuccessful) {
                val envelope = response.body()
                val data = envelope?.data
                if (data != null) {
                    prefs.saveJwtToken(data.token)
                    prefs.saveUser(data.user)
                    // MES is the authority for line scope; the PDA never lets a user switch it locally.
                    data.user.lineCode?.takeIf { it.isNotBlank() }?.let { prefs.saveLineCode(it) }
                    prefs.saveLocale(data.user.locale)
                    Result.success(data)
                } else {
                    Result.failure(Exception(envelope?.error?.message ?: "Login failed"))
                }
            } else {
                val msg = parseErrorMessage(response)
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    suspend fun restoreSession(): Result<UserInfo> {
        val token = prefs.getJwtToken() ?: return Result.failure(Exception("No token"))
        return try {
            val response = api.getSession()
            if (response.isSuccessful) {
                val envelope = response.body()
                val session = envelope?.data?.session
                val user = prefs.getUser()
                if (user != null) {
                    Result.success(user)
                } else {
                    Result.failure(Exception("Session expired"))
                }
            } else {
                prefs.clearSession()
                Result.failure(Exception("Session expired"))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    fun getCurrentUser(): UserInfo? = prefs.getUser()

    fun isLoggedIn(): Boolean = prefs.hasToken()

    fun logout() {
        prefs.clearSession()
    }

    private fun parseErrorMessage(response: retrofit2.Response<*>): String {
        return try {
            val errorBody = response.errorBody()?.string()
            if (errorBody != null) {
                val error = Gson().fromJson(errorBody, ApiEnvelope::class.java)
                error.error?.message ?: "Unknown error"
            } else {
                "Error ${response.code()}"
            }
        } catch (e: Exception) {
            "Error ${response.code()}"
        }
    }
}
