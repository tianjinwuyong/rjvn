package com.smt.materialloader.ui.materialloader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.smt.materialloader.R
import com.smt.materialloader.data.api.dto.WorkOrderDto
import com.smt.materialloader.ui.components.BarcodeScanner

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MaterialLoadScreen(
    viewModel: MaterialLoadViewModel = viewModel(),
    onBack: () -> Unit,
    initialWoCode: String? = null
) {
    val state by viewModel.state.collectAsState()

    // Auto-transition to scan flow once work-start succeeds
    LaunchedEffect(state.workStarted) {
        if (state.workStarted && state.view == MaterialLoadView.MATERIAL_LIST) {
            viewModel.startScan()
        }
    }

    // Auto-select WO if passed from WoListScreen
    LaunchedEffect(initialWoCode) {
        if (initialWoCode != null) {
            viewModel.selectWoByCode(initialWoCode)
        }
    }

    // Auto-navigate to COMPLETE_CONFIRM when all materials are loaded
    LaunchedEffect(state.allMaterialsLoaded) {
        if (state.allMaterialsLoaded && state.view == MaterialLoadView.SCAN_FLOW) {
            viewModel.confirmComplete()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = when (state.view) {
                                MaterialLoadView.WO_SELECT -> stringResource(R.string.material_load_select_wo)
                                MaterialLoadView.MATERIAL_LIST -> stringResource(R.string.material_load_list)
                                MaterialLoadView.SCAN_FLOW -> stringResource(R.string.material_load_scan)
                                MaterialLoadView.COMPLETE_CONFIRM -> stringResource(R.string.material_load_complete)
                            },
                            fontWeight = FontWeight.Bold
                        )
                        state.selectedWo?.let {
                            Text(it.code, fontSize = 13.sp, color = Color(0xFF64748b))
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = {
                        if (state.view == MaterialLoadView.WO_SELECT) onBack() else viewModel.goBack()
                    }) {
                        Icon(Icons.Default.ArrowBack, contentDescription = stringResource(R.string.back))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF1e293b),
                    titleContentColor = Color(0xFFf1f5f9),
                    navigationIconContentColor = Color(0xFFf1f5f9)
                )
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF0f172a))
        ) {
            when (state.view) {
                MaterialLoadView.WO_SELECT -> WoSelectView(state, viewModel)
                MaterialLoadView.MATERIAL_LIST -> MaterialListView(state, viewModel)
                MaterialLoadView.SCAN_FLOW -> ScanFlowView(state, viewModel)
                MaterialLoadView.COMPLETE_CONFIRM -> CompleteConfirmView(state, viewModel)
            }
        }
    }

    if (state.showScanner) {
        BarcodeScanner(
            onBarcodeDetected = { barcode ->
                viewModel.onBarcodeScanned(barcode)
            },
            onError = { },
            modifier = Modifier.fillMaxSize()
        )
    }

    // Return dialog
    state.returnDialogReq?.let { req ->
        ReturnDialog(
            req = req,
            state = state,
            onReasonCodeChange = viewModel::setReturnReasonCode,
            onReasonNoteChange = viewModel::setReturnReasonNote,
            onVerdictChange = viewModel::setQualityVerdict,
            onSubmit = viewModel::submitReturn,
            onDismiss = viewModel::clearReturnDialog
        )
    }
}

@Composable
private fun WoSelectView(state: MaterialLoadUiState, viewModel: MaterialLoadViewModel) {
    Box(modifier = Modifier.fillMaxSize()) {
        when {
            state.isLoadingWos -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFF3b82f6))
                }
            }
            state.workOrders.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(stringResource(R.string.wo_no_results), color = Color(0xFF64748b), fontSize = 16.sp)
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(state.workOrders) { wo ->
                        WorkOrderCard(wo) { viewModel.selectWorkOrder(wo) }
                    }
                }
            }
        }

        // Loading overlay when a WO is being locked
        if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize().background(Color(0x88000000)),
                contentAlignment = Alignment.Center
            ) {
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))) {
                    Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = Color(0xFF3b82f6))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("正在锁定工单...", color = Color(0xFFf1f5f9), fontSize = 14.sp)
                    }
                }
            }
        }

        // Error banner
        state.error?.let { err ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(16.dp).align(Alignment.BottomCenter),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF450a0a))
            ) {
                Row(
                    modifier = Modifier.padding(12.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(err, color = Color(0xFFfca5a5), fontSize = 13.sp, modifier = Modifier.weight(1f))
                    Button(
                        onClick = { viewModel.clearError() },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFdc2626))
                    ) { Text("✕") }
                }
            }
        }
    }
}

@Composable
private fun WorkOrderCard(wo: WorkOrderDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(wo.code, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Color(0xFFf1f5f9), fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (wo.isLocked) {
                        Surface(color = Color(0xFF78350f), shape = MaterialTheme.shapes.small) {
                            Text("🔒 ${wo.lockedBy}", fontSize = 11.sp, color = Color(0xFFfcd34d), modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
                        }
                    }
                    Surface(color = when (wo.status) {
                        "released" -> Color(0xFF064e3b)
                        else -> Color(0xFF1e3a5f)
                    }, shape = MaterialTheme.shapes.small) {
                        Text(wo.status, fontSize = 11.sp, color = Color(0xFFf1f5f9), modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
                    }
                }
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(wo.productCode ?: "—", fontSize = 14.sp, color = Color(0xFF94a3b8))
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("${stringResource(R.string.common_location)}: ${wo.lineCode ?: "—"}", fontSize = 13.sp, color = Color(0xFF64748b))
                Text("${stringResource(R.string.planned_qty)}: ${wo.plannedQty}", fontSize = 13.sp, color = Color(0xFF64748b))
            }
        }
    }
}

@Composable
private fun MaterialListView(state: MaterialLoadUiState, viewModel: MaterialLoadViewModel) {
    var materialFilter by remember { mutableStateOf("all") } // "all" | "smt" | "nonSmt"
    val filteredRequirements = when (materialFilter) {
        "smt" -> state.requirements.filter { it.isSmt }
        "nonSmt" -> state.requirements.filter { !it.isSmt }
        else -> state.requirements
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Summary bar
        Row(
            modifier = Modifier.fillMaxWidth().background(Color(0xFF0f172a)).padding(vertical = 10.dp, horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            StatItem(state.requirements.size.toString(), stringResource(R.string.common_total))
            StatItem(state.requirements.count { it.status == "pending" || it.status == "loading" || it.status == "error" }.toString(), stringResource(R.string.common_pending), Color(0xFFfbbf24))
            StatItem(state.fulfilledCount.toString(), stringResource(R.string.common_fulfilled), Color(0xFF22c55e))
            StatItem(state.requirements.count { it.isSmt }.toString(), "SMT", Color(0xFF3b82f6))
            StatItem(state.requirements.count { !it.isSmt }.toString(), "辅料", Color(0xFFd97706))
        }

        // Material type filter chips
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf("all" to "全部", "smt" to "SMT", "nonSmt" to "辅料").forEach { (value, label) ->
                FilterChip(
                    selected = materialFilter == value,
                    onClick = { materialFilter = value },
                    label = { Text(label, fontSize = 12.sp) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = when (value) {
                            "smt" -> Color(0xFF3b82f6)
                            "nonSmt" -> Color(0xFFd97706)
                            else -> Color(0xFF22c55e)
                        }
                    )
                )
            }
        }

        // Error banner if any
        state.error?.let { error ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF450a0a))
            ) {
                Row(
                    modifier = Modifier.padding(12.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(error, color = Color(0xFFfca5a5), fontSize = 13.sp, modifier = Modifier.weight(1f))
                    Button(
                        onClick = { viewModel.clearError() },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFdc2626))
                    ) { Text("✕") }
                }
            }
        }

        // Stock warning banner (e.g. insufficient stock)
        state.stockWarning?.let { warning ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF451a03))
            ) {
                Row(
                    modifier = Modifier.padding(12.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "⚠ ${warning.code.replace("_", " ")}",
                            color = Color(0xFFfbbf24),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = warning.message,
                            color = Color(0xFFfde68a),
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                        warning.shortage?.let { sh ->
                            Text(
                                text = "Shortage: ${sh.toInt()} units",
                                color = Color(0xFFfca5a5),
                                fontSize = 11.sp,
                                modifier = Modifier.padding(top = 2.dp)
                            )
                        }
                    }
                    Button(
                        onClick = { viewModel.clearStockWarning() },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFd97706))
                    ) { Text("✕") }
                }
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().weight(1f),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(filteredRequirements) { req ->
                MaterialRequirementCard(req = req, viewModel = viewModel)
            }
        }

        // Footer
        Row(
            modifier = Modifier.fillMaxWidth().background(Color(0xFF1e293b)).padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            val hasUnfinished = state.requirements.any { it.status == "pending" || it.status == "loading" || it.status == "error" }

            // Work-start loading or error
            if (state.workStartLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp).weight(1f),
                    color = Color(0xFF3b82f6), strokeWidth = 2.dp
                )
            } else {
                // Work-start error banner
                state.workStartError?.let { err ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF450a0a))
                    ) {
                        Row(
                            modifier = Modifier.padding(8.dp).fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(err, color = Color(0xFFfca5a5), fontSize = 12.sp, modifier = Modifier.weight(1f))
                            Button(
                                onClick = { viewModel.triggerWorkStart() },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFdc2626)),
                                modifier = Modifier.height(28.dp)
                            ) { Text("重试", fontSize = 11.sp) }
                        }
                    }
                }

                Button(
                    onClick = {
                        if (!state.workStarted && !state.workStartError.isNullOrEmpty()) {
                            viewModel.triggerWorkStart()
                        } else if (hasUnfinished) {
                            if (state.workStarted) {
                                viewModel.startScan()
                            } else {
                                viewModel.triggerWorkStart()
                            }
                        } else {
                            viewModel.confirmComplete()
                        }
                    },
                    modifier = Modifier.weight(2f).height(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = when {
                            !state.workStarted && state.workStartError.isNullOrEmpty() -> Color(0xFFd97706) // 开工未点
                            hasUnfinished -> Color(0xFF3b82f6)
                            else -> Color(0xFF22c55e)
                        }
                    ),
                    enabled = !state.isLoading
                ) {
                    Text(
                        text = when {
                            !state.workStarted -> "开工"
                            hasUnfinished -> stringResource(R.string.material_load_scan)
                            else -> stringResource(R.string.common_finish)
                        },
                        fontSize = 16.sp, fontWeight = FontWeight.Bold
                    )
                }
            }

            OutlinedButton(
                onClick = { viewModel.goBack() },
                modifier = Modifier.weight(1f).height(52.dp)
            ) {
                Text(stringResource(R.string.common_back), color = Color(0xFF94a3b8))
            }
        }
    }
}

@Composable
private fun MaterialRequirementCard(req: MaterialRequirement, viewModel: MaterialLoadViewModel) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = when (req.status) {
                "fulfilled" -> Color(0xFF064e3b)
                "loading" -> Color(0xFF1e3a5f)
                "error" -> Color(0xFF450a0a)
                else -> Color(0xFF1e293b)
            }
        )
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Seq ${req.seq}", fontSize = 12.sp, color = Color(0xFF64748b), fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    when (req.status) {
                        "fulfilled" -> {
                            Surface(color = Color(0xFF064e3b), shape = MaterialTheme.shapes.small) {
                                Text("✓ LOADED", fontSize = 11.sp, color = Color(0xFF34d399), modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
                            }
                        }
                        "loading" -> {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color(0xFF38bdf8), strokeWidth = 2.dp)
                            Text(" LOADING...", fontSize = 11.sp, color = Color(0xFF38bdf8))
                        }
                        "error" -> {
                            Surface(color = Color(0xFFdc2626), shape = MaterialTheme.shapes.small) {
                                Text("✕ ERROR", fontSize = 11.sp, color = Color(0xFFf1f5f9), modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
                            }
                        }
                        else -> {
                            Surface(color = Color(0xFF334155), shape = MaterialTheme.shapes.small) {
                                Text("○ PENDING", fontSize = 11.sp, color = Color(0xFF94a3b8), modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp))
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(req.materialCode, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Color(0xFFf1f5f9), fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                Surface(
                    shape = MaterialTheme.shapes.small,
                    color = if (req.isSmt) Color(0xFF1d4ed8) else Color(0xFF92400e)
                ) {
                    Text(
                        if (req.isSmt) "SMT" else "辅料",
                        fontSize = 10.sp,
                        color = Color(0xFFf1f5f9),
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }
            Text(req.materialNameZh, fontSize = 13.sp, color = Color(0xFF94a3b8))
            Spacer(modifier = Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("${stringResource(R.string.required_qty)}: ${req.requiredQty} ${req.unit}", fontSize = 12.sp, color = Color(0xFF64748b))
            }

            // Loaded info
            if (req.status == "fulfilled" && req.scannedLotNo != null) {
                Spacer(modifier = Modifier.height(6.dp))
                Text("Lot: ${req.scannedLotNo} | Qty: ${req.scannedQty}", fontSize = 12.sp, color = Color(0xFF34d399), fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                req.txNo?.let { Text("TX: $it", fontSize = 10.sp, color = Color(0xFF64748b)) }
                Spacer(modifier = Modifier.height(6.dp))
                Button(
                    onClick = { viewModel.openReturnDialog(req) },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFdc2626)),
                    modifier = Modifier.height(32.dp)
                ) {
                    Text("↩ ${stringResource(R.string.common_return)}", fontSize = 12.sp)
                }
            }

            // Error message with retry
            if (req.status == "error" && req.errorMessage != null) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(req.errorMessage, fontSize = 12.sp, color = Color(0xFFfca5a5))
                Spacer(modifier = Modifier.height(6.dp))
                Button(
                    onClick = { viewModel.retryCurrentMaterial() },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF3b82f6)),
                    modifier = Modifier.height(36.dp)
                ) {
                    Text("Retry", fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
private fun ScanFlowView(state: MaterialLoadUiState, viewModel: MaterialLoadViewModel) {
    var showRealConfirm by remember { mutableStateOf(false) }
    var pendingRealLot by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize()) {
        // Progress
        val progress = if (state.requirements.isNotEmpty()) state.fulfilledCount.toFloat() / state.requirements.size else 0f
        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier.fillMaxWidth().height(6.dp).padding(horizontal = 16.dp).padding(top = 16.dp),
            color = Color(0xFF22c55e),
            trackColor = Color(0xFF334155),
        )
        Text(
            "${state.fulfilledCount} / ${state.requirements.size} ${stringResource(R.string.common_loaded)}",
            fontSize = 13.sp, color = Color(0xFF64748b), modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp).fillMaxWidth(), textAlign = TextAlign.Center
        )

        // 3-QR scan phase stepper — show only relevant phases for current material
        val currentLoadingReq = state.requirements.firstOrNull { it.status == "loading" }
        val isNonSmt = currentLoadingReq?.isSmt == false
        // Non-SMT skips MACHINE/SLOT/FEEDER → only show 料盘 step
        val visiblePhases = if (isNonSmt) {
            listOf(ScanPhase.LOT to "料盘")
        } else {
            listOf(
                ScanPhase.MACHINE to "机台",
                ScanPhase.SLOT to "槽位",
                ScanPhase.FEEDER to "飞达",
                ScanPhase.LOT to "料盘"
            )
        }
        Card(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1e3a5f))
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    text = if (isNonSmt) "扫码流程 (辅料跳过机台/槽位/飞达)" else "扫码流程",
                    fontSize = 12.sp, color = Color(0xFF64748b), fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    visiblePhases.forEach { (phase, label) ->
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Surface(
                                shape = androidx.compose.foundation.shape.CircleShape,
                                color = when {
                                    state.scanPhase == phase -> Color(0xFF3b82f6)
                                    state.scanPhase.ordinal > phase.ordinal -> Color(0xFF22c55e)
                                    else -> Color(0xFF334155)
                                },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Text(
                                        text = when {
                                            state.scanPhase.ordinal > phase.ordinal -> "✓"
                                            state.scanPhase == phase -> "●"
                                            else -> "○"
                                        },
                                        fontSize = 12.sp, color = Color(0xFFf1f5f9)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(label, fontSize = 10.sp, color = if (state.scanPhase == phase) Color(0xFF38bdf8) else Color(0xFF64748b))
                        }
                    }
                }
                // Scanned values display
                if (state.scannedMachine != null || state.scannedSlot != null || state.scannedFeeder != null) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        state.scannedMachine?.let {
                            Surface(shape = MaterialTheme.shapes.small, color = Color(0xFF064e3b)) {
                                Text("机台:$it", fontSize = 10.sp, color = Color(0xFF34d399), modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                            }
                        }
                        state.scannedSlot?.let {
                            Surface(shape = MaterialTheme.shapes.small, color = Color(0xFF064e3b)) {
                                Text("槽位:$it", fontSize = 10.sp, color = Color(0xFF34d399), modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                            }
                        }
                        state.scannedFeeder?.let {
                            Surface(shape = MaterialTheme.shapes.small, color = Color(0xFF064e3b)) {
                                Text("飞达:$it", fontSize = 10.sp, color = Color(0xFF34d399), modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                            }
                        }
                    }
                }
            }
        }

        // Current material / slot info card
        state.requirements.firstOrNull { it.status == "loading" }?.let { req ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1e3a5f))
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        text = when (state.scanPhase) {
                            ScanPhase.MACHINE -> "扫描机台二维码"
                            ScanPhase.SLOT -> "扫描槽位二维码 (1L~20L, 1R~20R)"
                            ScanPhase.FEEDER -> "扫描飞达二维码"
                            ScanPhase.LOT -> "扫描料盘二维码"
                        },
                        fontSize = 14.sp, color = Color(0xFF38bdf8), fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(req.materialCode, fontSize = 15.sp, color = Color(0xFFf1f5f9), fontWeight = FontWeight.SemiBold)
                        Surface(
                            shape = MaterialTheme.shapes.small,
                            color = if (req.isSmt) Color(0xFF1d4ed8) else Color(0xFF92400e)
                        ) {
                            Text(
                                if (req.isSmt) "SMT" else "辅料",
                                fontSize = 10.sp,
                                color = Color(0xFFf1f5f9),
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                            )
                        }
                    }
                    Text(req.materialNameZh, fontSize = 13.sp, color = Color(0xFF94a3b8))
                    Text("${stringResource(R.string.required_qty)}: ${req.requiredQty} ${req.unit}", fontSize = 12.sp, color = Color(0xFF94a3b8))
                }
            }
        }

        // Feedback (shown above scanner)
        state.lastFeedback?.let { (ok, msg) ->
            Card(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                colors = CardDefaults.cardColors(containerColor = if (ok) Color(0xFF064e3b) else Color(0xFF450a0a))
            ) {
                Text(text = "${if (ok) "✓" else "✕"} $msg", color = if (ok) Color(0xFF34d399) else Color(0xFFfca5a5), fontWeight = FontWeight.Bold, modifier = Modifier.padding(14.dp))
            }
        }

        // Slot map (shown in SLOT phase)
        if (state.scanPhase == ScanPhase.SLOT && state.scannedMachine != null) {
            SlotMapView(
                machineCode = state.scannedMachine!!,
                scannedSlot = state.scannedSlot,
                occupiedSlots = state.occupiedSlots,
                onSlotSelected = { slot -> viewModel.onBarcodeScanned(slot) },
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            )
        }

        // Scanner — full width, real barcode scanning only
        Box(
            modifier = Modifier.fillMaxSize().weight(1f).padding(horizontal = 16.dp, vertical = 8.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                if (state.isLoading) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = Color(0xFF3b82f6))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(stringResource(R.string.processing), color = Color(0xFF94a3b8), fontSize = 14.sp)
                    }
                } else {
                    BarcodeScanner(
                        onBarcodeDetected = { barcode -> viewModel.onBarcodeScanned(barcode) },
                        onError = { },
                        modifier = Modifier.fillMaxWidth().aspectRatio(4f / 3f)
                    )
                }
            }
        }

        // Footer
        Row(
            modifier = Modifier.fillMaxWidth().background(Color(0xFF1e293b)).padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (state.scanPhase == ScanPhase.LOT && state.pendingReelBarcode != null) {
                // Confirm + return to feeder buttons
                Button(
                    onClick = { viewModel.confirmReelScan() },
                    modifier = Modifier.weight(1f).height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF22c55e)),
                    enabled = !state.isLoading
                ) {
                    Text("确认上料", fontSize = 15.sp, fontWeight = FontWeight.Bold)
                }
                OutlinedButton(
                    onClick = { viewModel.resetToFeederPhase() },
                    modifier = Modifier.weight(1f).height(52.dp)
                ) {
                    Text("返回飞达", color = Color(0xFF94a3b8), fontSize = 15.sp)
                }
            } else {
                OutlinedButton(
                    onClick = { viewModel.goBack() },
                    modifier = Modifier.fillMaxWidth().height(52.dp)
                ) {
                    Text(stringResource(R.string.common_back), color = Color(0xFF94a3b8), fontSize = 15.sp)
                }
            }
        }
    }

    // REAL button confirmation dialog — warns before writing real data
    if (showRealConfirm) {
        AlertDialog(
            onDismissRequest = { showRealConfirm = false },
            title = { Text("确认真实上料？", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text("此操作会向服务器发送真实的物料上料请求。")
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("批次: $pendingRealLot", color = Color(0xFFeab308), fontWeight = FontWeight.SemiBold)
                    state.requirements.firstOrNull { it.status == "loading" }?.let { req ->
                        Text("物料: ${req.materialCode}", color = Color(0xFF94a3b8))
                        Text("数量: ${req.requiredQty}", color = Color(0xFF94a3b8))
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.simulateTrayReal(pendingRealLot)
                        showRealConfirm = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFeab308))
                ) {
                    Text("确认上料", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showRealConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }
}

@Composable
private fun CompleteConfirmView(state: MaterialLoadUiState, viewModel: MaterialLoadViewModel) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = stringResource(R.string.material_load_confirm_title),
            fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFFf1f5f9)
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            text = stringResource(R.string.material_load_confirm_msg),
            fontSize = 15.sp, color = Color(0xFF94a3b8), textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))

        state.selectedWo?.let { wo ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("WO: ${wo.code}", fontSize = 16.sp, color = Color(0xFFf1f5f9), fontWeight = FontWeight.SemiBold)
                    Text("Product: ${wo.productCode}", fontSize = 13.sp, color = Color(0xFF94a3b8))
                    Text("${stringResource(R.string.common_fulfilled)}: ${state.fulfilledCount} / ${state.requirements.size}", fontSize = 13.sp, color = Color(0xFF34d399))
                }
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        if (state.isLoading) {
            CircularProgressIndicator(color = Color(0xFF3b82f6))
            Spacer(modifier = Modifier.height(12.dp))
            Text(stringResource(R.string.processing), color = Color(0xFF94a3b8))
        } else {
            Button(
                onClick = { viewModel.finishWorkOrder() },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF22c55e))
            ) {
                Text(stringResource(R.string.common_confirm), fontSize = 16.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedButton(
                onClick = { viewModel.cancelComplete() },
                modifier = Modifier.fillMaxWidth().height(52.dp)
            ) {
                Text(stringResource(R.string.common_back), color = Color(0xFF94a3b8), fontSize = 15.sp)
            }
        }

        state.error?.let { err ->
            Spacer(modifier = Modifier.height(12.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF450a0a))
            ) {
                Text(err, color = Color(0xFFfca5a5), fontSize = 13.sp, modifier = Modifier.padding(12.dp))
            }
        }
    }
}

@Composable
private fun ReturnDialog(
    req: MaterialRequirement,
    state: MaterialLoadUiState,
    onReasonCodeChange: (String) -> Unit,
    onReasonNoteChange: (String) -> Unit,
    onVerdictChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit
) {
    val verdictOptions = listOf("PASS" to "✓ 正常 (PASS)", "NG" to "✗ NG不良", "DAMAGED" to "⚠ 损坏 (DAMAGED)")

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Color(0xFF1e293b),
        title = {
            Text("退料 / Return Material", color = Color(0xFFf1f5f9), fontWeight = FontWeight.Bold)
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                // Material info
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF334155))) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(req.materialCode, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color(0xFFf1f5f9))
                        Text(req.materialNameZh, fontSize = 12.sp, color = Color(0xFF94a3b8))
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("Lot: ${req.scannedLotNo ?: "—"} | Qty: ${req.scannedQty ?: req.requiredQty}", fontSize = 12.sp, color = Color(0xFF34d399))
                    }
                }

                // Reason code picker
                Text("退料原因 *", fontSize = 12.sp, color = Color(0xFF94a3b8))
                if (state.returnReasons.isNotEmpty()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        state.returnReasons.forEach { reason ->
                            val isSelected = state.returnReasonCode == reason.code
                            Surface(
                                modifier = Modifier.fillMaxWidth().clickable { onReasonCodeChange(reason.code) },
                                color = if (isSelected) Color(0xFF3b82f6) else Color(0xFF334155),
                                shape = MaterialTheme.shapes.small
                            ) {
                                Text(
                                    text = "${reason.nameZh} (${reason.code})",
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                    fontSize = 13.sp,
                                    color = Color(0xFFf1f5f9)
                                )
                            }
                        }
                    }
                } else {
                    OutlinedTextField(
                        value = state.returnReasonCode,
                        onValueChange = onReasonCodeChange,
                        label = { Text("原因代码", color = Color(0xFF94a3b8)) },
                        modifier = Modifier.fillMaxWidth(),
                        textStyle = androidx.compose.ui.text.TextStyle(fontSize = 13.sp, color = Color(0xFFf1f5f9)),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color(0xFF3b82f6),
                            unfocusedBorderColor = Color(0xFF475569),
                            focusedTextColor = Color(0xFFf1f5f9),
                            unfocusedTextColor = Color(0xFFf1f5f9),
                            cursorColor = Color(0xFF3b82f6)
                        )
                    )
                }

                // Reason note
                OutlinedTextField(
                    value = state.returnReasonNote,
                    onValueChange = onReasonNoteChange,
                    label = { Text("备注 (可选)", color = Color(0xFF94a3b8)) },
                    modifier = Modifier.fillMaxWidth(),
                    textStyle = androidx.compose.ui.text.TextStyle(fontSize = 13.sp, color = Color(0xFFf1f5f9)),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF3b82f6),
                        unfocusedBorderColor = Color(0xFF475569),
                        focusedTextColor = Color(0xFFf1f5f9),
                        unfocusedTextColor = Color(0xFFf1f5f9),
                        cursorColor = Color(0xFF3b82f6)
                    )
                )

                // Quality verdict picker
                Text("质量判定 *", fontSize = 12.sp, color = Color(0xFF94a3b8))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    verdictOptions.forEach { (verdict, label) ->
                        val isSelected = state.qualityVerdict == verdict
                        val bgColor = when {
                            verdict == "PASS" && isSelected -> Color(0xFF22c55e)
                            verdict == "NG" && isSelected -> Color(0xFFef4444)
                            verdict == "DAMAGED" && isSelected -> Color(0xFFd97706)
                            else -> Color(0xFF334155)
                        }
                        Surface(
                            modifier = Modifier.weight(1f).clickable { onVerdictChange(verdict) },
                            color = bgColor,
                            shape = MaterialTheme.shapes.small
                        ) {
                            Text(
                                text = label,
                                modifier = Modifier.padding(vertical = 10.dp, horizontal = 4.dp),
                                fontSize = 11.sp,
                                color = Color(0xFFf1f5f9),
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }

                // Error message
                state.returnError?.let { err ->
                    Text(err, fontSize = 12.sp, color = Color(0xFFfca5a5))
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onSubmit,
                enabled = !state.returnSubmitting && state.returnReasonCode.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFdc2626))
            ) {
                if (state.returnSubmitting) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color(0xFFffffff), strokeWidth = 2.dp)
                } else {
                    Text("确认退料")
                }
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) {
                Text("取消", color = Color(0xFF94a3b8))
            }
        }
    )
}

@Composable
private fun StatItem(value: String, label: String, valueColor: Color = Color(0xFFf1f5f9)) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = valueColor)
        Text(label, fontSize = 11.sp, color = Color(0xFF64748b))
    }
}