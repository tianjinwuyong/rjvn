package com.smt.materialloader.data.api.dto

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("username") val username: String,
    @SerializedName("password") val password: String
)

data class LoginResponse(
    @SerializedName("token") val token: String,
    @SerializedName("user") val user: UserInfo,
    @SerializedName("expiresAt") val expiresAt: String
)

data class UserInfo(
    @SerializedName("id") val id: String,
    @SerializedName("username") val username: String,
    @SerializedName("displayName") val displayName: String,
    @SerializedName("locale") val locale: String,
    @SerializedName("roleKey") val roleKey: String,
    @SerializedName("permissions") val permissions: List<String> = emptyList()
)

data class SessionResponse(
    @SerializedName("session") val session: SessionInfo,
    @SerializedName("permissions") val permissions: List<String>
)

data class SessionInfo(
    @SerializedName("userId") val userId: String,
    @SerializedName("username") val username: String,
    @SerializedName("displayName") val displayName: String,
    @SerializedName("locale") val locale: String,
    @SerializedName("roleKey") val roleKey: String,
    @SerializedName("issuedAt") val issuedAt: String,
    @SerializedName("expiresAt") val expiresAt: String
)
