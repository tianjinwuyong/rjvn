package com.smt.materialloader.ui.wobind

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.smt.materialloader.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WoBindScreen(
    viewModel: WoBindViewModel = viewModel(),
    onBack: () -> Unit
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.bindResult) {
        state.bindResult?.let { (_, msg) ->
            snackbarHostState.showSnackbar(message = msg)
            viewModel.clearResult()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.wo_bind_title), fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = {
                        if (state.selectedWo != null) {
                            viewModel.deselectWo()
                        } else {
                            onBack()
                        }
                    }) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back)
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF1e293b),
                    titleContentColor = Color(0xFFf1f5f9),
                    navigationIconContentColor = Color(0xFFf1f5f9)
                )
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color(0xFF0f172a))
        ) {
            if (state.selectedWo == null) {
                WoSelectPhase(state = state, viewModel = viewModel)
            } else {
                BindPhase(state = state, viewModel = viewModel)
            }
        }
    }
}

@Composable
private fun WoSelectPhase(state: WoBindUiState, viewModel: WoBindViewModel) {
    Column(modifier = Modifier.fillMaxSize()) {
        OutlinedTextField(
            value = state.searchQuery,
            onValueChange = viewModel::onSearchChanged,
            placeholder = { Text(stringResource(R.string.wo_list_search_hint)) },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = Color(0xFF64748b)) },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFF3b82f6),
                unfocusedBorderColor = Color(0xFF334155),
                focusedTextColor = Color(0xFFf1f5f9),
                unfocusedTextColor = Color(0xFFf1f5f9)
            )
        )

        when {
            state.isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFF3b82f6))
                }
            }
            state.filteredWos.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(stringResource(R.string.wo_no_results), color = Color(0xFF64748b), fontSize = 16.sp)
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(
                        items = state.filteredWos,
                        key = { it.id }
                    ) { wo: com.smt.materialloader.data.api.dto.WorkOrderDto ->
                        WoSelectCard(wo = wo, onClick = { viewModel.selectWorkOrder(wo) })
                    }
                }
            }
        }
    }
}

@Composable
private fun WoSelectCard(
    wo: com.smt.materialloader.data.api.dto.WorkOrderDto,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    wo.code,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp,
                    color = Color(0xFFf1f5f9),
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                )
                Surface(
                    color = if (wo.status == "released") Color(0xFF064e3b) else Color(0xFF1e3a5f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Text(
                        wo.status,
                        fontSize = 11.sp,
                        color = Color(0xFFf1f5f9),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                    )
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(wo.productCode ?: "—", fontSize = 14.sp, color = Color(0xFF94a3b8))
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                modifier = Modifier.padding(top = 4.dp)
            ) {
                Text(
                    "${stringResource(R.string.common_location)}: ${wo.lineCode ?: "—"}",
                    fontSize = 12.sp,
                    color = Color(0xFF64748b)
                )
                Text(
                    "${stringResource(R.string.planned_qty)}: ${wo.plannedQty}",
                    fontSize = 12.sp,
                    color = Color(0xFF64748b)
                )
            }
        }
    }
}

@Composable
private fun BindPhase(state: WoBindUiState, viewModel: WoBindViewModel) {
    val wo = state.selectedWo ?: return

    when {
        state.isLoadingBom -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = Color(0xFF3b82f6))
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        stringResource(R.string.loading),
                        color = Color(0xFF64748b),
                        fontSize = 14.sp
                    )
                }
            }
        }
        else -> {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // WO header
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(
                            stringResource(R.string.wo_info),
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = Color(0xFF60a5fa)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        InfoRow(stringResource(R.string.issue_work_order), wo.code)
                        InfoRow(stringResource(R.string.material_code), wo.productCode ?: "—")
                        InfoRow(stringResource(R.string.common_location), wo.lineCode ?: "—")
                        InfoRow(stringResource(R.string.planned_qty), wo.plannedQty.toString())
                    }
                }

                // BOM material list
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1e293b))
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(
                            stringResource(R.string.wo_bind_material_list),
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = Color(0xFF60a5fa)
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        if (state.bomItems.isEmpty()) {
                            Text(
                                stringResource(R.string.wo_no_results),
                                fontSize = 13.sp,
                                color = Color(0xFF64748b)
                            )
                        } else {
                            state.bomItems.forEachIndexed { idx, item ->
                                BomItemRow(item = item)
                                if (idx < state.bomItems.lastIndex) {
                                    HorizontalDivider(
                                        color = Color(0xFF334155),
                                        modifier = Modifier.padding(vertical = 6.dp)
                                    )
                                }
                            }
                        }
                    }
                }

                // Slot input
                OutlinedTextField(
                    value = state.bindSlot,
                    onValueChange = viewModel::onSlotChanged,
                    label = { Text(stringResource(R.string.wo_bind_slot)) },
                    placeholder = { Text(stringResource(R.string.wo_bind_slot_hint)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFF3b82f6),
                        unfocusedBorderColor = Color(0xFF334155),
                        focusedTextColor = Color(0xFFf1f5f9),
                        unfocusedTextColor = Color(0xFFf1f5f9)
                    )
                )

                // Bind button
                Button(
                    onClick = { viewModel.executeBind() },
                    enabled = state.bindSlot.isNotBlank() && !state.isBinding,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF3b82f6))
                ) {
                    if (state.isBinding) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(24.dp)
                        )
                    } else {
                        Text(
                            stringResource(R.string.wo_bind_execute),
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp
                        )
                    }
                }

                // Change WO button
                OutlinedButton(
                    onClick = { viewModel.deselectWo() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                ) {
                    Text(
                        stringResource(R.string.wo_bind_change_wo),
                        color = Color(0xFF94a3b8)
                    )
                }
            }
        }
    }
}

@Composable
private fun BomItemRow(item: BomItem) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    item.materialCode,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = Color(0xFFf1f5f9),
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                )
                Text(item.materialName, fontSize = 12.sp, color = Color(0xFF94a3b8))
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "${item.pickedQty} / ${item.requiredQty} ${item.unit}",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = when (item.status) {
                        "fulfilled" -> Color(0xFF22c55e)
                        "partial" -> Color(0xFFfbbf24)
                        else -> Color(0xFF94a3b8)
                    }
                )
                Text(
                    text = item.status.uppercase(),
                    fontSize = 11.sp,
                    color = when (item.status) {
                        "fulfilled" -> Color(0xFF22c55e)
                        "partial" -> Color(0xFFfbbf24)
                        else -> Color(0xFF64748b)
                    }
                )
            }
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, fontSize = 13.sp, color = Color(0xFF94a3b8))
        Text(value, fontSize = 13.sp, fontWeight = FontWeight.Medium, color = Color(0xFFf1f5f9))
    }
}
