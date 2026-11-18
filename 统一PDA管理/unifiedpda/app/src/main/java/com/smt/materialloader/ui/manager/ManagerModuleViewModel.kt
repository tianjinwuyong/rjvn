package com.smt.materialloader.ui.manager

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.smt.materialloader.MaterialLoaderApp
import com.smt.materialloader.BuildConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

data class ManagerModuleState(
    val mesOnline: Boolean = false,
    val lastUpdated: String = "",
    val items: List<ManagerModuleItem> = emptyList(),
    val kpiSummary: String = "",
    val actionMessage: String? = null,
    val actionSucceeded: Boolean = false,
    val error: String? = null
)

class ManagerModuleViewModel : ViewModel() {
    private val api = MaterialLoaderApp.instance.apiService
    // MES assigns this scope at login (manual/auto/SMT); do not expose a local line switch.
    private val lineCode: String
        get() = MaterialLoaderApp.instance.prefs.getLineCode().ifBlank { "L004" }
    private val _state = MutableStateFlow(ManagerModuleState())
    val state: StateFlow<ManagerModuleState> = _state.asStateFlow()

    fun load(module: ManagerModule) {
        if (_state.value.lastUpdated.isNotEmpty()) return
        viewModelScope.launch {
            try {
                val response = when (module) {
                    ManagerModule.ALERTS, ManagerModule.REPAIR -> if (BuildConfig.TEST_ACTION_BYPASS_ENABLED) retrofit2.Response.success(JsonObject()) else api.managerAlerts(lineCode)
                    ManagerModule.DECISIONS -> api.managerDecisions(lineCode)
                    ManagerModule.APPROVALS -> api.managerDecisions("")
                    ManagerModule.ORG_CHART -> api.hrOrgChart()
                    ManagerModule.COMMUNICATIONS -> api.managerChannels()
                    ManagerModule.TEAM -> api.hrEmployees()
                    ManagerModule.ASSIGNMENTS -> api.managerLineAssignments()
                    ManagerModule.HIRING_REQUESTS -> api.managerHiringRequests()
                    ManagerModule.GRIEVANCE_CASES -> api.managerGrievanceCases()
                    ManagerModule.TARGETS -> api.managerTargets(lineCode)
                    ManagerModule.LINE_STATUS -> api.mesLine(lineCode)
                    ManagerModule.LOADING_STATUS -> api.smtLoadingWorkOrders(lineCode)
                    ManagerModule.HANDOVER -> api.managerHandover(lineCode)
                    ManagerModule.PROFILE -> api.getSession()
                    ManagerModule.PLANT_MANAGER -> api.plantManagerExceptionRequests()
                }
                val body = response.body() as? JsonObject
                val kpi = if (module == ManagerModule.LINE_STATUS) {
                    val k = body?.getAsJsonObject("data")?.getAsJsonObject("stationKpi")
                    if (k != null) "平均工作 ${k["workingHoursToday"]?.asString ?: "0"} h · 平均停机 ${k["stoppedHoursToday"]?.asString ?: "0"} h · 运行率 ${k["availabilityPct"]?.asString ?: "0"}%" else ""
                } else ""
                _state.value = ManagerModuleState(
                    mesOnline = response.isSuccessful,
                    lastUpdated = now(),
                    items = parseItems(module, body),
                    kpiSummary = kpi,
                    error = if (response.isSuccessful) null else local("MES 返回 HTTP ${response.code()}：${module.endpoint}", "MES returned HTTP ${response.code()} for ${module.endpoint}", "MES trả về HTTP ${response.code()} cho ${module.endpoint}")
                )
            } catch (e: Exception) {
                _state.value = ManagerModuleState(lastUpdated = now(), error = local("MES 连接失败：${e.message}", "MES connection failed: ${e.message}", "Kết nối MES thất bại: ${e.message}"))
            }
        }
    }

    fun perform(module: ManagerModule, action: String, recordId: String, comment: String) {
        if (recordId.isBlank() && module != ManagerModule.TEAM) {
            _state.value = _state.value.copy(actionMessage = local("操作前必须填写 MES 记录编号", "MES record ID is required before this action", "Phải nhập mã bản ghi MES trước khi thao tác"), actionSucceeded = false)
            return
        }
        if ((action == "reject" || action == "information" || action == "message" || action == "recovery" || action == "confirm") && comment.isBlank()) {
            _state.value = _state.value.copy(actionMessage = local("必须填写说明或原因", "Comment or reason is required", "Bắt buộc nhập ghi chú hoặc lý do"), actionSucceeded = false)
            return
        }
        viewModelScope.launch {
            try {
                val requestId = UUID.randomUUID().toString()
                val body = mapOf("lineCode" to lineCode, "comment" to comment, "reason" to comment, "idempotencyKey" to requestId)
                val response = when (module) {
                    ManagerModule.ALERTS, ManagerModule.REPAIR -> if (action == "acknowledge") api.managerAcknowledgeAlert(recordId, body) else api.managerEscalateAlert(recordId, body)
                    ManagerModule.DECISIONS, ManagerModule.APPROVALS -> when (action) {
                        "approve" -> api.managerApproveDecision(recordId, body)
                        "reject" -> api.managerRejectDecision(recordId, body)
                        else -> api.managerAskDecisionInformation(recordId, body)
                    }
                    ManagerModule.TEAM -> api.managerSendMessage(body + mapOf("audience" to recordId, "message" to comment, "requiresAcknowledgement" to true))
                    ManagerModule.TARGETS -> api.managerCreateRecoveryAction(body + mapOf("targetId" to recordId, "ownerEmployeeCode" to recordId))
                    ManagerModule.HANDOVER -> api.managerConfirmHandover(body + mapOf("receiverEmployeeCode" to recordId))
                    else -> null
                }
                if (response == null) return@launch
                val serverMessage = response.body()?.get("message")?.asString
                _state.value = _state.value.copy(
                    actionMessage = if (response.isSuccessful) local("MES 已确认 $action", "MES confirmed $action", "MES đã xác nhận $action") + (serverMessage?.let { ": $it" } ?: "") else local("MES 拒绝 $action：HTTP ${response.code()}", "MES rejected $action: HTTP ${response.code()}", "MES từ chối $action: HTTP ${response.code()}"),
                    actionSucceeded = response.isSuccessful,
                    lastUpdated = now()
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(actionMessage = local("操作失败：${e.message}", "Action failed: ${e.message}", "Thao tác thất bại: ${e.message}"), actionSucceeded = false)
            }
        }
    }

    private fun parseItems(module: ManagerModule, body: JsonObject?): List<ManagerModuleItem> {
        if (body == null) return emptyList()
        if (module == ManagerModule.LINE_STATUS) {
            val runtime = body.getAsJsonObject("data")?.getAsJsonArray("stationRuntime") ?: return emptyList()
            return runtime.map { element ->
                val o = element.asJsonObject
                ManagerModuleItem(
                    o.string("stationCode") ?: "Station",
                    "状态 ${o.string("status") ?: "UNKNOWN"} · 瞬时心跳 ${o.string("lastSeen") ?: "-"} · 最后事件 ${o.string("lastEventAt") ?: "-"}",
                    "今日运行 ${o.string("runtimeMinutesToday") ?: "0"} 分钟 · 推算停机 ${o.string("inferredStopMinutesToday") ?: "0"} 分钟"
                )
            }
        }
        val array = sequenceOf("data", "items", "employees", "records", "rows")
            .mapNotNull { body.get(it) }
            .mapNotNull { it.asArrayOrNull() }
            .firstOrNull() ?: return emptyList()
        return array.mapNotNull { element ->
            val o = element.asJsonObject
            if (module == ManagerModule.REPAIR) {
                val payload = o.getAsJsonObject("payload")
                val type = o["type"]?.asString ?: payload?.get("type")?.asString
                if (type != "MAINTENANCE_PICKUP_READY" && type != "REPAIR_STATUS" && type != "REPAIR_SLA_ALERT") return@mapNotNull null
            }
            when (module) {
                ManagerModule.TEAM -> ManagerModuleItem(
                    o.string("displayName", "name_zh", "name_en", "code") ?: "Employee",
                    "${o.string("code", "employeeCode") ?: ""} · ${o.string("departmentNameZh", "departmentCode") ?: "HR department"}",
                    "${o.string("positionTitleZh", "positionTitleEn") ?: "Position unknown"} · HR status ${o.string("status") ?: "unknown"}"
                )
                ManagerModule.LOADING_STATUS -> {
                    val materials = o["materials"]?.asJsonArray?.map { material ->
                        val m = material.asJsonObject
                        "${m.string("materialCode") ?: "-"}: 实际${m.string("actualConsumedQty") ?: "0"}，${m.string("actualConsumptionRatePerMinute") ?: "0"}/分钟"
                    }?.take(6)?.joinToString("；") ?: "暂无实际物料消耗事件"
                    ManagerModuleItem(
                        o.string("workOrderCode", "code") ?: "MES工单",
                        "实际消耗 ${o.string("actualConsumedQty") ?: "0"} · 生产速度 ${o.string("estimatedProductionRatePerMinute") ?: "0"} 产品/分钟\n$materials",
                        "产线 ${o.string("lineCode") ?: "-"} · 速度来源 ${o.string("rateSource") ?: "MES_OUTPUT_HISTORY"}"
                    )
                }
                else -> ManagerModuleItem(
                    o.string("title", "name", "code", "id") ?: module.title,
                    o.string("detail", "description", "message", "reason") ?: "MES record received",
                    o.string("status", "state") ?: "MES status received"
                )
            }
        }
    }

    private fun now() = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
    private fun local(zh: String, en: String, vi: String): String = when (MaterialLoaderApp.instance.prefs.getLocale()) {
        "vi-VN" -> vi
        "en-US" -> en
        else -> zh
    }
}

private fun JsonElement.asArrayOrNull(): JsonArray? = if (isJsonArray) asJsonArray else null
private fun JsonObject.string(vararg names: String): String? = names.asSequence().mapNotNull { get(it)?.takeUnless { v -> v.isJsonNull }?.asString }.firstOrNull()
