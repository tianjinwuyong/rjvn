package com.smt.materialloader.ui.manager

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.res.stringResource
import com.smt.materialloader.R
import com.smt.materialloader.MaterialLoaderApp
import androidx.lifecycle.viewmodel.compose.viewModel

enum class ManagerModule(val title: String, val endpoint: String, val description: String) {
    ALERTS("Alerts", "/api/manager/alerts", "Critical, overdue, blocked and offline work requiring attention."),
    REPAIR("Repair center", "/api/manager/alerts?type=MAINTENANCE_PICKUP_READY", "MES-owned NG repair pickup, repair status, return handover and SLA alerts."),
    DECISIONS("Decisions", "/api/manager/decisions", "MES-authorized requests for exceptions, stop/resume, changeover and rework."),
    APPROVALS("Applications approval", "/api/manager/decisions?scope=all-departments", "Cross-department applications requiring plant manager approval."),
    ORG_CHART("HR organization", "/hr/org-chart", "Real-time HR department tree, managers and active headcount."),
    COMMUNICATIONS("Communication center", "/api/manager/channels", "MES-routed communication with line managers and departments."),
    TEAM("Team", "/hr/employees + /api/manager/team + /api/manager/messages", "HR employee identity joined to MES line assignment, PDA health, messages and acknowledgement."),
    ASSIGNMENTS("Daily assignments", "/api/manager/line-assignments", "Line manager assigns HR employees to today's line positions, product/work order and loading permission."),
    HIRING_REQUESTS("Staffing requests", "/api/manager/hiring-requests", "Line manager requests missing positions; HR and plant manager sign before publication."),
    GRIEVANCE_CASES("HR investigations", "/api/manager/grievance-cases", "Confidential HR cases requiring the line manager's explanation."),
    TARGETS("Targets", "/api/manager/targets", "Output, quality, on-time, downtime and material-readiness achievement."),
    LINE_STATUS("Line status", "/mes/lines/{lineCode} + /api/pda/heartbeats", "Work order timeline, stations, operators, equipment and material status."),
    LOADING_STATUS("Material loading status", "/api/smt/loading/work-orders", "MES work-order material loading progress and PDA status."),
    HANDOVER("Handover", "/api/manager/handover", "Open issues, unfinished work, next-shift priorities and confirmation."),
    PROFILE("Profile & diagnostics", "/auth/session + /api/manager/audit", "Identity, authorized scope, expiry, audit and connection diagnostics.")
    ,PLANT_MANAGER("All line managers PDA", "/api/plant-manager/exception-requests + /api/manager/channels", "Shared PDA for manual, auto and SMT line managers; MES controls plant-only authority.")
}

@Composable
fun ManagerModuleScreen(module: ManagerModule, onBack: () -> Unit, viewModel: ManagerModuleViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    var recordId by remember { mutableStateOf("") }
    var comment by remember { mutableStateOf("") }
    val canFinalRelease = MaterialLoaderApp.instance.prefs.getUser()?.permissions.orEmpty().contains("approval.final.release")
    LaunchedEffect(module) { viewModel.load(module) }

    Column(Modifier.fillMaxSize().background(Color(0xFFF1F5F9))) {
        Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(moduleTitle(module), fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Color(0xFF0F172A))
            Text(stringResource(R.string.manager_back), color = Color(0xFF2563EB), modifier = Modifier.padding(top = 6.dp).clickable { onBack() })
        }
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.manager_scope), fontWeight = FontWeight.Bold, color = Color(0xFF0F172A))
                        Text(moduleDescription(module), color = Color(0xFF475569))
                        Text("MES interface: ${module.endpoint}", color = Color(0xFF64748B), fontSize = 12.sp)
                        Text(if (state.mesOnline) "MES connected · ${state.lastUpdated}" else stringResource(R.string.manager_no_local_write), color = if (state.mesOnline) Color(0xFF166534) else Color(0xFF991B1B), fontSize = 12.sp)
                        if (state.error != null) Text(state.error!!, color = Color(0xFF991B1B), fontSize = 12.sp)
                        if (module == ManagerModule.LINE_STATUS && state.kpiSummary.isNotBlank()) Text("平均/实时 KPI：${state.kpiSummary}", color = Color(0xFF0F766E), fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                }
            }
            if (module == ManagerModule.ALERTS || module == ManagerModule.REPAIR || module == ManagerModule.DECISIONS || module == ManagerModule.TEAM || module == ManagerModule.TARGETS || module == ManagerModule.HANDOVER) {
                item {
                    OutlinedTextField(recordId, { recordId = it }, label = { Text(stringResource(R.string.manager_record_id)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                    OutlinedTextField(comment, { comment = it }, label = { Text(stringResource(R.string.manager_comment)) }, modifier = Modifier.fillMaxWidth())
                    ActionButtons(module, recordId, comment, viewModel, state.mesOnline, canFinalRelease)
                }
            }
            if (module == ManagerModule.LOADING_STATUS) item {
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFE0F2FE)), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("MES 速度与消耗公式", fontWeight = FontWeight.Bold, color = Color(0xFF0F172A))
                        Text("产品/分钟 = 生产数量 ÷ 生产分钟数", color = Color(0xFF334155), fontSize = 12.sp)
                        Text("物料/分钟 = 产品/分钟 × BOM 单台用量", color = Color(0xFF334155), fontSize = 12.sp)
                        Text("手动线计划模拟会明确标记；线长只读查看 MES 结果。", color = Color(0xFF475569), fontSize = 12.sp)
                    }
                }
            }
            if (state.items.isEmpty()) item { EmptyModuleCard(module) }
            else items(state.items) { ModuleItemCard(it) }
            state.actionMessage?.let { message -> item { Text(message, color = if (state.actionSucceeded) Color(0xFF166534) else Color(0xFF991B1B)) } }
        }
    }
}

@Composable
private fun ActionButtons(module: ManagerModule, recordId: String, comment: String, viewModel: ManagerModuleViewModel, mesOnline: Boolean, canFinalRelease: Boolean) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        when (module) {
            ManagerModule.ALERTS, ManagerModule.REPAIR -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = mesOnline && recordId.isNotBlank(), onClick = { viewModel.perform(module, "acknowledge", recordId, comment) }) { Text(stringResource(R.string.manager_acknowledge)) }
                Button(enabled = mesOnline && recordId.isNotBlank(), onClick = { viewModel.perform(module, "escalate", recordId, comment) }) { Text(stringResource(R.string.manager_escalate)) }
            }
            ManagerModule.DECISIONS -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = mesOnline && canFinalRelease && recordId.isNotBlank(), onClick = { viewModel.perform(module, "approve", recordId, comment) }) { Text(if (canFinalRelease) stringResource(R.string.manager_approve) else "REVIEW ONLY") }
                Button(enabled = mesOnline && canFinalRelease && recordId.isNotBlank() && comment.isNotBlank(), onClick = { viewModel.perform(module, "reject", recordId, comment) }) { Text(if (canFinalRelease) stringResource(R.string.manager_reject) else "SENIOR ONLY") }
                Button(enabled = mesOnline && recordId.isNotBlank() && comment.isNotBlank(), onClick = { viewModel.perform(module, "information", recordId, comment) }) { Text(stringResource(R.string.manager_ask)) }
            }
            ManagerModule.TEAM -> Button(enabled = mesOnline && comment.isNotBlank(), onClick = { viewModel.perform(module, "message", recordId, comment) }) { Text(stringResource(R.string.manager_send)) }
            ManagerModule.TARGETS -> Button(enabled = mesOnline && recordId.isNotBlank() && comment.isNotBlank(), onClick = { viewModel.perform(module, "recovery", recordId, comment) }) { Text(stringResource(R.string.manager_recovery)) }
            ManagerModule.HANDOVER -> Button(enabled = mesOnline && recordId.isNotBlank() && comment.isNotBlank(), onClick = { viewModel.perform(module, "confirm", recordId, comment) }) { Text(stringResource(R.string.manager_handover_confirm)) }
            else -> Unit
        }
    }
}

@Composable
private fun EmptyModuleCard(module: ManagerModule) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.manager_no_records), fontWeight = FontWeight.Bold, color = Color(0xFF0F172A))
            Text("${moduleTitle(module)} · ${stringResource(R.string.manager_no_local_write)}", color = Color(0xFF475569))
        }
    }
}

@Composable
private fun ModuleItemCard(item: ManagerModuleItem) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.title, fontWeight = FontWeight.Bold, color = Color(0xFF0F172A))
            Text(item.detail, color = Color(0xFF475569))
            Text(item.status, color = Color(0xFF64748B), fontSize = 12.sp)
        }
    }
}

data class ManagerModuleItem(val title: String, val detail: String, val status: String)

@Composable private fun moduleTitle(module: ManagerModule): String = when (module) {
    ManagerModule.ALERTS -> stringResource(R.string.manager_alerts)
    ManagerModule.REPAIR -> "Repair center / 回修中心"
    ManagerModule.DECISIONS -> stringResource(R.string.manager_decisions_page)
    ManagerModule.APPROVALS -> "跨部门申请审批"
    ManagerModule.ORG_CHART -> "HR 实时组织结构"
    ManagerModule.COMMUNICATIONS -> "全厂通信中心"
    ManagerModule.TEAM -> stringResource(R.string.manager_team_page)
    ManagerModule.ASSIGNMENTS -> stringResource(R.string.manager_line_assignments)
    ManagerModule.HIRING_REQUESTS -> stringResource(R.string.manager_hiring_requests)
    ManagerModule.GRIEVANCE_CASES -> stringResource(R.string.manager_grievance_cases)
    ManagerModule.TARGETS -> stringResource(R.string.manager_targets_page)
    ManagerModule.LINE_STATUS -> stringResource(R.string.manager_line_status_page)
    ManagerModule.LOADING_STATUS -> "实时上料状态"
    ManagerModule.HANDOVER -> stringResource(R.string.manager_handover_page)
    ManagerModule.PROFILE -> stringResource(R.string.manager_profile_page)
    ManagerModule.PLANT_MANAGER -> "厂长 PDA"
}

@Composable private fun moduleDescription(module: ManagerModule): String = when (module) {
    ManagerModule.ALERTS -> stringResource(R.string.manager_desc_alerts)
    ManagerModule.REPAIR -> "MES 管理的 NG 回修、待取件、维修中、待返回和 SLA 告警"
    ManagerModule.DECISIONS -> stringResource(R.string.manager_desc_decisions)
    ManagerModule.APPROVALS -> "PMC、生产、质量、仓库、工程和 HR 的 MES 申请审批"
    ManagerModule.ORG_CHART -> "HR 部门树、负责人、在职人数和部门状态"
    ManagerModule.COMMUNICATIONS -> "线长、HR、WMS、采购、PMC、质量和工程频道"
    ManagerModule.TEAM -> stringResource(R.string.manager_desc_team)
    ManagerModule.ASSIGNMENTS -> stringResource(R.string.manager_line_assignments)
    ManagerModule.HIRING_REQUESTS -> stringResource(R.string.manager_desc_hiring_requests)
    ManagerModule.GRIEVANCE_CASES -> stringResource(R.string.manager_desc_grievance_cases)
    ManagerModule.TARGETS -> stringResource(R.string.manager_desc_targets)
    ManagerModule.LINE_STATUS -> stringResource(R.string.manager_desc_line_status)
    ManagerModule.LOADING_STATUS -> "MES 工单、各 PDA 分配物料、已完成/未完成、在线状态和错料报警"
    ManagerModule.HANDOVER -> stringResource(R.string.manager_desc_handover)
    ManagerModule.PROFILE -> stringResource(R.string.manager_desc_profile)
    ManagerModule.PLANT_MANAGER -> "全厂例外授权与中层管理者沟通"
}
