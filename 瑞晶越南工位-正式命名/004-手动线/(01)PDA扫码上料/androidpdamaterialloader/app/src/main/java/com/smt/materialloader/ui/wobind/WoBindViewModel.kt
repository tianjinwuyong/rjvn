package com.smt.materialloader.ui.wobind

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smt.materialloader.MaterialLoaderApp
import com.smt.materialloader.data.api.dto.WorkOrderDto
import com.smt.materialloader.data.repository.WorkOrderRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class BomItem(
    val seq: Int,
    val materialCode: String,
    val materialName: String,
    val unit: String,
    val requiredQty: Int,
    val pickedQty: Int,
    val status: String  // pending / partial / fulfilled
)

data class WoBindUiState(
    val isLoading: Boolean = true,
    val searchQuery: String = "",
    val workOrders: List<WorkOrderDto> = emptyList(),
    val filteredWos: List<WorkOrderDto> = emptyList(),
    val selectedWo: WorkOrderDto? = null,
    val isLoadingBom: Boolean = false,
    val bomItems: List<BomItem> = emptyList(),
    val bindSlot: String = "",
    val bindResult: Pair<Boolean, String>? = null,
    val isBinding: Boolean = false,
    val error: String? = null
)

class WoBindViewModel : ViewModel() {
    private val woRepo: WorkOrderRepository = MaterialLoaderApp.instance.workOrderRepository

    private val _state = MutableStateFlow(WoBindUiState())
    val state: StateFlow<WoBindUiState> = _state.asStateFlow()

    init {
        loadWorkOrders()
    }

    private fun loadWorkOrders() {
        _state.value = _state.value.copy(isLoading = true)
        viewModelScope.launch {
            woRepo.getWorkOrders(status = "released").fold(
                onSuccess = { wos ->
                    _state.value = _state.value.copy(
                        workOrders = wos,
                        filteredWos = wos,
                        isLoading = false
                    )
                },
                onFailure = {
                    _state.value = _state.value.copy(workOrders = emptyList(), filteredWos = emptyList(), isLoading = false)
                }
            )
        }
    }

    fun onSearchChanged(query: String) {
        _state.value = _state.value.copy(searchQuery = query)
        if (query.isBlank()) {
            _state.value = _state.value.copy(filteredWos = _state.value.workOrders)
        } else {
            val q = query.uppercase()
            _state.value = _state.value.copy(
                filteredWos = _state.value.workOrders.filter { wo ->
                    wo.code.uppercase().contains(q) ||
                    (wo.productCode?.uppercase()?.contains(q) == true) ||
                    (wo.lineCode?.uppercase()?.contains(q) == true)
                }
            )
        }
    }

    fun selectWorkOrder(wo: WorkOrderDto) {
        _state.value = _state.value.copy(selectedWo = wo, isLoadingBom = true, bomItems = emptyList())
        val productCode = wo.productCode
        if (productCode.isNullOrBlank()) {
            _state.value = _state.value.copy(isLoadingBom = false)
            return
        }
        viewModelScope.launch {
            woRepo.getBomForProduct(productCode).fold(
                onSuccess = { bom ->
                    val bomItems = bom.lines.mapIndexed { idx, line ->
                        BomItem(
                            seq = idx + 1,
                            materialCode = line.materialCode,
                            materialName = line.materialNameZh,
                            unit = line.unit,
                            requiredQty = (line.qtyPer * wo.plannedQty).toInt(),
                            pickedQty = 0,
                            status = "pending"
                        )
                    }
                    _state.value = _state.value.copy(bomItems = bomItems, isLoadingBom = false)
                },
                onFailure = {
                    _state.value = _state.value.copy(bomItems = emptyList(), isLoadingBom = false)
                }
            )
        }
    }

    fun onSlotChanged(slot: String) {
        _state.value = _state.value.copy(bindSlot = slot.uppercase())
    }

    fun executeBind() {
        val wo = _state.value.selectedWo ?: return
        val slot = _state.value.bindSlot
        if (slot.isBlank()) return

        _state.value = _state.value.copy(isBinding = true, bindResult = null)
        // Mock bind — real impl would call Flask /api/loading-scan
        viewModelScope.launch {
            kotlinx.coroutines.delay(800)
            _state.value = _state.value.copy(
                isBinding = false,
                bindResult = Pair(true, "Bound ${wo.code} → Slot $slot"),
                bindSlot = ""
            )
        }
    }

    fun clearResult() {
        _state.value = _state.value.copy(bindResult = null)
    }

    fun deselectWo() {
        _state.value = _state.value.copy(selectedWo = null, bomItems = emptyList())
    }
}
