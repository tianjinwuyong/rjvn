package com.smt.materialloader.data.repository

import com.smt.materialloader.data.api.RetrofitClient
import com.smt.materialloader.data.api.dto.*

class MaterialRepository {

    private val api get() = RetrofitClient.getApiService()

    suspend fun issueToLine(
        lotNo: String,
        workOrderCode: String,
        qty: Int,
        operator: String
    ): Result<IssueResponse> {
        return try {
            val request = IssueRequest(lotNo, workOrderCode, qty, operator)
            val response = api.issueToLine(request)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    Result.failure(Exception("Empty response"))
                }
            } else {
                Result.failure(parseError(response))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    suspend fun returnFromLine(
        lotNo: String,
        workOrderCode: String,
        qty: Int,
        operator: String,
        reason: String = ""
    ): Result<ReturnResponse> {
        return try {
            val request = ReturnRequest(lotNo, workOrderCode, qty, operator, reason)
            val response = api.returnFromLine(request)
            if (response.isSuccessful) {
                val data = response.body()?.data
                if (data != null) {
                    Result.success(data)
                } else {
                    Result.failure(Exception("Empty response"))
                }
            } else {
                Result.failure(parseError(response))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    suspend fun getMaterialLots(
        lotNo: String? = null,
        iqcStatus: String? = null,
        q: String? = null
    ): Result<List<MaterialLotDto>> {
        return try {
            val response = api.getMaterialLots(lotNo = lotNo, iqcStatus = iqcStatus, q = q)
            if (response.isSuccessful) {
                val items = response.body()?.data?.items ?: emptyList()
                Result.success(items)
            } else {
                Result.failure(parseError(response))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    suspend fun getLotTransactions(lotId: String): Result<List<InventoryTransactionDto>> {
        return try {
            val response = api.getLotTransactions(lotId)
            if (response.isSuccessful) {
                val items = response.body()?.data?.items ?: emptyList()
                Result.success(items)
            } else {
                Result.failure(parseError(response))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Network error: ${e.message}"))
        }
    }

    private fun parseError(response: retrofit2.Response<*>): Exception {
        return try {
            val body = response.errorBody()?.string()
            if (body != null) {
                val error = com.google.gson.Gson().fromJson(body, ApiEnvelope::class.java)
                Exception(error.error?.message ?: "Error ${response.code()}")
            } else {
                Exception("Error ${response.code()}")
            }
        } catch (e: Exception) {
            Exception("Error ${response.code()}")
        }
    }
}
