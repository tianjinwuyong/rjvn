package com.smt.materialloader.ui.materialloader

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.smt.materialloader.data.api.dto.FeederBindingConfirmResponse

/**
 * Visual 40-slot grid for NPM machines.
 * Dual-track layout: left track 1L~20L, right track 1R~20R.
 * Shows slot occupancy state fetched from feeder-binding-list API.
 */
@Composable
fun SlotMapView(
    machineCode: String,
    scannedSlot: String?,
    occupiedSlots: List<FeederBindingConfirmResponse>,
    onSlotSelected: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    // Build slot list: left track 1L~20L, right track 1R~20R
    val leftSlots = (1..20).map { "${it}L" }
    val rightSlots = (1..20).map { "${it}R" }

    // Build a map of slot -> binding info
    val occupiedMap = occupiedSlots.associateBy { it.slotNo }

    Column(modifier = modifier) {
        // Machine header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF1e3a5f))
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "机台: $machineCode",
                color = Color(0xFFf1f5f9),
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SlotLegendItem(color = Color(0xFF334155), label = "空闲")
                SlotLegendItem(color = Color(0xFF22c55e), label = "已占用")
                SlotLegendItem(color = Color(0xFF3b82f6), label = "已扫描")
                SlotLegendItem(color = Color(0xFFdc2626), label = "错误")
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Slot grid
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            // Left track
            SlotColumn(
                slots = leftSlots,
                trackLabel = "左轨 L",
                scannedSlot = scannedSlot,
                occupiedMap = occupiedMap,
                onSlotClick = onSlotSelected,
                modifier = Modifier.weight(1f)
            )
            // Right track
            SlotColumn(
                slots = rightSlots,
                trackLabel = "右轨 R",
                scannedSlot = scannedSlot,
                occupiedMap = occupiedMap,
                onSlotClick = onSlotSelected,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun SlotColumn(
    slots: List<String>,
    trackLabel: String,
    scannedSlot: String?,
    occupiedMap: Map<String, FeederBindingConfirmResponse>,
    onSlotClick: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        // Track label
        Text(
            text = trackLabel,
            color = Color(0xFF64748b),
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center
        )

        // Slots in 4 rows × 5 cols
        slots.chunked(5).forEach { rowSlots ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                rowSlots.forEach { slot ->
                    val isOccupied = occupiedMap.containsKey(slot)
                    val isScanned = slot == scannedSlot
                    SlotCell(
                        slot = slot,
                        binding = occupiedMap[slot],
                        isScanned = isScanned,
                        isOccupied = isOccupied,
                        onClick = { onSlotClick(slot) },
                        modifier = Modifier.weight(1f)
                    )
                }
                // Fill remaining cells in last row if less than 5
                repeat(5 - rowSlots.size) {
                    Spacer(modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun SlotCell(
    slot: String,
    binding: FeederBindingConfirmResponse?,
    isScanned: Boolean,
    isOccupied: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val backgroundColor = when {
        isScanned -> Color(0xFF3b82f6)
        isOccupied -> Color(0xFF22c55e)
        else -> Color(0xFF334155)
    }
    val borderColor = when {
        isScanned -> Color(0xFF60a5fa)
        isOccupied -> Color(0xFF16a34a)
        else -> Color(0xFF475569)
    }

    val textColor = when {
        isScanned || isOccupied -> Color(0xFFf1f5f9)
        else -> Color(0xFF94a3b8)
    }

    val slotNumber = slot.dropLast(1)
    val track = slot.takeLast(1)

    Box(
        modifier = modifier
            .aspectRatio(1f)
            .clip(RoundedCornerShape(4.dp))
            .background(backgroundColor)
            .border(1.dp, borderColor, RoundedCornerShape(4.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = slotNumber,
                color = textColor,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )
            Text(
                text = track,
                color = textColor.copy(alpha = 0.7f),
                fontSize = 8.sp
            )
        }
    }
}

@Composable
private fun SlotLegendItem(color: Color, label: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        Box(
            modifier = Modifier
                .size(10.dp)
                .background(color, RoundedCornerShape(2.dp))
        )
        Text(
            text = label,
            color = Color(0xFF94a3b8),
            fontSize = 9.sp
        )
    }
}
