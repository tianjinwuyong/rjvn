package com.smt.materialloader.ui.employee

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.JsonObject
import com.smt.materialloader.MaterialLoaderApp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class EmployeeSelfServiceState(
    val loading: Boolean = false,
    val profile: JsonObject? = null,
    val attendance: List<JsonObject> = emptyList(),
    val leaveRequests: List<JsonObject> = emptyList(),
    val grievances: List<JsonObject> = emptyList(),
    val employeeQr: String? = null,
    val message: String? = null
)

class EmployeeSelfServiceViewModel : ViewModel() {
    private val app = MaterialLoaderApp.instance
    private val _state = MutableStateFlow(EmployeeSelfServiceState())
    val state: StateFlow<EmployeeSelfServiceState> = _state.asStateFlow()

    private fun userCode(): String = app.prefs.getUser()?.username.orEmpty()

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, message = null)
            runCatching {
                val profileResponse = app.apiService.hrEmployee(userCode())
                val profile = profileResponse.body()?.getAsJsonObject("item")
                val employeeId = profile?.get("id")?.asString ?: app.prefs.getUser()?.id.orEmpty()
                val attendance = app.apiService.hrEmployeeAttendance(employeeId).body().items("items")
                val leave = app.apiService.hrEmployeeLeaveRequests(employeeId).body().items("items")
                val grievances = app.apiService.hrEmployeeGrievances().body().items("items")
                _state.value = EmployeeSelfServiceState(
                    profile = profile,
                    attendance = attendance,
                    leaveRequests = leave,
                    grievances = grievances,
                    message = "HR/MES synchronized"
                )
            }.onFailure { error ->
                _state.value = _state.value.copy(message = error.message ?: "HR/MES sync failed")
            }
            _state.value = _state.value.copy(loading = false)
        }
    }

    fun clockIn() = clock("in")
    fun clockOut() = clock("out")

    private fun clock(direction: String) {
        viewModelScope.launch {
            val employeeId = _state.value.profile?.get("id")?.asString ?: app.prefs.getUser()?.id.orEmpty()
            val body = mapOf("payload" to mapOf("employeeId" to employeeId))
            val response = if (direction == "in") app.apiService.hrEmployeeClockIn(body) else app.apiService.hrEmployeeClockOut(body)
            _state.value = _state.value.copy(message = if (response.isSuccessful) "Attendance recorded" else "Attendance rejected (${response.code()})")
            refresh()
        }
    }

    fun submitLeave(leaveType: String, startDate: String, endDate: String, reason: String) {
        viewModelScope.launch {
            val response = app.apiService.hrEmployeeCreateLeave(
                mapOf("payload" to mapOf("leaveType" to leaveType, "startDate" to startDate, "endDate" to endDate, "reason" to reason))
            )
            _state.value = _state.value.copy(message = if (response.isSuccessful) "Leave request submitted" else "Leave request rejected (${response.code()})")
            refresh()
        }
    }

    fun generateEmployeeQr() {
        viewModelScope.launch {
            val employeeId = _state.value.profile?.get("id")?.asString ?: app.prefs.getUser()?.id.orEmpty()
            val response = app.apiService.hrEmployeeGenerateQr(employeeId, mapOf("validDays" to 365))
            val qr = response.body()?.getAsJsonObject("item")?.get("qrContent")?.asString
            _state.value = _state.value.copy(employeeQr = qr, message = if (response.isSuccessful) "Employee QR issued" else "Employee QR rejected (${response.code()})")
        }
    }

    fun submitGrievance(subjectEmployeeCode: String, lineCode: String, category: String, text: String) {
        viewModelScope.launch {
            val response = app.apiService.hrEmployeeCreateGrievance(
                mapOf("payload" to mapOf(
                    "subjectEmployeeCode" to subjectEmployeeCode,
                    "lineCode" to lineCode,
                    "allegationCategory" to category,
                    "complaintText" to text
                ))
            )
            _state.value = _state.value.copy(message = if (response.isSuccessful) "Grievance submitted" else "Grievance rejected (${response.code()})")
            refresh()
        }
    }

    private fun JsonObject?.items(name: String): List<JsonObject> =
        this?.getAsJsonArray(name)?.mapNotNull { it.asJsonObject } ?: emptyList()
}
