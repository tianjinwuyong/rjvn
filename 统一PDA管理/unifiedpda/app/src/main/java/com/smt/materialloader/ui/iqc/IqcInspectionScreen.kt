package com.smt.materialloader.ui.iqc

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.BottomAppBar
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.smt.materialloader.MaterialLoaderApp
import kotlinx.coroutines.launch

private data class IqcItem(val title: String, val checks: List<String>)
private data class IqcMaterial(val lot: String, val code: String, val name: String, val qty: String, val location: String)

private val iqcQueue = listOf(
    IqcMaterial("TEST-PO-20260827-01", "SMT-R-10K-0603", "Chip Resistor 10KΩ 0603", "5,000 PCS", "IQC-A01-01"),
    IqcMaterial("TEST-PO-20260827-02", "SMT-C-100N-0402", "MLCC Capacitor 100nF 0402", "12,000 PCS", "IQC-A01-02"),
    IqcMaterial("TEST-PO-20260827-03", "SMT-LED-GRN-0805", "Green LED 0805", "3,000 PCS", "IQC-A01-03"),
)

private val iqcItems = listOf(
    IqcItem("物料身份/BOM与采购单", listOf("料号与采购单", "制造商/原厂型号", "规格书与BOM版本", "替代料批准状态")),
    IqcItem("数量、批次、日期码", listOf("外箱数量", "内包装数量", "批次号/日期码", "卷数/盘数与单据")),
    IqcItem("包装、载带、卷盘完整性", listOf("外箱无破损", "内袋密封完整", "载带/卷盘无变形", "无污染/混料")),
    IqcItem("标签、条码、原厂标识", listOf("供应商标签", "原厂标识", "条码可扫描", "批次/原产地可追溯")),
    IqcItem("外观、丝印、引脚、焊端", listOf("本体无裂纹", "引脚/焊端无氧化", "丝印清晰", "无变形/缺件")),
    IqcItem("尺寸、间距、厚度", listOf("长/宽/高", "引脚间距", "厚度/外形", "载带孔距/腔体")),
    IqcItem("电气参数/功能", listOf("标称值", "容差", "耐压/漏电", "ESR或功能参数")),
    IqcItem("可焊性", listOf("焊端润湿", "焊点覆盖", "无拒焊/虚焊", "测试方法与时间")),
    IqcItem("MSD、HIC、Floor Life、烘烤", listOf("MSL等级", "HIC湿度指示", "干燥剂/真空袋", "开封时间", "Floor Life/烘烤")),
    IqcItem("ESD包装与处理", listOf("防静电包装", "ESD标签", "接地状态", "操作与运输条件")),
    IqcItem("COA、RoHS/REACH及文件", listOf("COA/检验报告", "RoHS/REACH", "客户特殊要求", "文件版本有效")),
    IqcItem("风险/假料/重大缺陷升级", listOf("假料/改标识别", "重大缺陷升级", "隔离状态", "供应商8D要求")),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IqcInspectionScreen(onHome: () -> Unit, onBack: () -> Unit, onLogout: () -> Unit) {
    val results = remember { mutableStateMapOf<Int, String>() }
    val operator = remember { mutableStateOf("IQC测试员") }
    val deviceName = remember { mutableStateOf("PDA-IQC-01") }
    val deviceConfirmed = remember { mutableStateOf(false) }
    val selectedMaterial = remember { mutableStateOf<IqcMaterial?>(null) }
    val apiStatus = remember { mutableStateOf("API同步中") }
    val scope = rememberCoroutineScope()
    val completed = results.count { it.value != "待检测" }
    fun recordResult(index: Int, result: String) {
        results[index] = result
        scope.launch {
            apiStatus.value = "API提交中"
            try {
                val response = MaterialLoaderApp.instance.apiService.postPdaEvent(
                    mapOf(
                        "from" to deviceName.value,
                        "to" to "WMS",
                        "type" to "IQC_ITEM_RESULT",
                        "payload" to mapOf(
                            "deviceId" to deviceName.value,
                            "operatorName" to operator.value,
                            "lotNo" to (selectedMaterial.value?.lot ?: ""),
                            "itemIndex" to index + 1,
                            "itemTitle" to iqcItems[index].title,
                            "result" to result,
                            "completed" to completed + 1,
                            "total" to iqcItems.size
                        )
                    )
                )
                apiStatus.value = if (response.isSuccessful) "API已同步" else "API同步失败 ${response.code()}"
            } catch (error: Exception) {
                apiStatus.value = "API离线：${error.message ?: "稍后重试"}"
            }
        }
    }
    LaunchedEffect(Unit) {
        try {
            val response = MaterialLoaderApp.instance.apiService.pdaRoleContext()
            val root = response.body()
            val assigned = root?.get("pdaId")?.asString
                ?: root?.getAsJsonObject("data")?.get("pdaId")?.asString
                ?: root?.get("deviceId")?.asString
            if (!assigned.isNullOrBlank()) {
                deviceName.value = assigned
                deviceConfirmed.value = true
            }
            apiStatus.value = if (response.isSuccessful) "API已连接 · IQC" else "API同步失败 ${response.code()}"
        } catch (error: Exception) {
            apiStatus.value = "API离线：${error.message ?: "稍后重试"}"
        }
    }
    Scaffold(
        topBar = { TopAppBar(title = { Text("PDA IQC 检验") }) },
        bottomBar = {
            BottomAppBar {
                TextButton(onClick = onHome, modifier = Modifier.weight(1f)) { Text("首页") }
                TextButton(onClick = onBack, modifier = Modifier.weight(1f)) { Text("返回") }
                TextButton(onClick = onLogout, modifier = Modifier.weight(1f)) { Text("退出") }
            }
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("IQC 待检物料队列", style = MaterialTheme.typography.titleMedium)
                        Text("先选择一项物料，再进入逐项 IQC 检测", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        iqcQueue.forEach { material ->
                            Button(
                                onClick = { if (deviceConfirmed.value) { selectedMaterial.value = material; results.clear() } },
                                enabled = deviceConfirmed.value,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text("${material.lot}\n${material.code} · ${material.name}\n数量：${material.qty} · 库位：${material.location}")
                            }
                        }
                        Text("当前选择：${selectedMaterial.value?.lot ?: "未选择"}", color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("IQC来料品质 · 原生PDA页面", style = MaterialTheme.typography.titleMedium)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(value = deviceName.value, onValueChange = { deviceName.value = it; deviceConfirmed.value = false }, label = { Text("PDA设备名称") }, modifier = Modifier.weight(1f))
                            Button(onClick = { deviceConfirmed.value = deviceName.value.isNotBlank() }) { Text(if (deviceConfirmed.value) "已确认" else "确认") }
                        }
                        Text("设备 ID：${deviceName.value}    工作设备：1 / 5 台")
                        Text(if (deviceConfirmed.value) "设备身份已确认，可选择待检物料" else "请先确认本机 PDA 名称", color = MaterialTheme.colorScheme.primary)
                        Text("批号：${selectedMaterial.value?.lot ?: "请先选择待检物料"}")
                        Text("物料：${selectedMaterial.value?.name ?: "-"}    MSD等级：MSD-3")
                        Text(apiStatus.value, color = MaterialTheme.colorScheme.primary)
                        Text("逐项检测进度：$completed / ${iqcItems.size}")
                        OutlinedTextField(value = operator.value, onValueChange = { operator.value = it }, label = { Text("IQC检验员") }, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            itemsIndexed(iqcItems) { index, item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("${index + 1}. ${item.title}", style = MaterialTheme.typography.titleSmall)
                        Text(item.checks.mapIndexed { i, value -> "${i + 1}) $value" }.joinToString("\n"))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { recordResult(index, "合格") }, enabled = selectedMaterial.value != null, modifier = Modifier.weight(1f)) { Text("合格") }
                            Button(onClick = { recordResult(index, "不合格") }, enabled = selectedMaterial.value != null, modifier = Modifier.weight(1f)) { Text("不合格") }
                        }
                        Text(results[index] ?: "待检测", color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("缺陷类型、严重程度、样本数、不良数、照片、批次备注")
                        Text("最终评审结果：${if (completed == iqcItems.size) "可提交批准" else "待完成全部项目"}")
                        Button(onClick = {}, enabled = selectedMaterial.value != null && completed == iqcItems.size, modifier = Modifier.fillMaxWidth()) { Text("批准提交 IQC 结果") }
                    }
                }
            }
        }
    }
}
