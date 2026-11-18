package com.ruijing.manualline.pda

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ManualLineMaterialLoadingScreen() }
    }
}

@Composable
private fun ManualLineMaterialLoadingScreen() {
    var showMap by remember { mutableStateOf(false) }
    Scaffold(topBar = { TopAppBar(title = { Text("Manual Line Material Loading") }) }) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text("Domain: manual-line", style = MaterialTheme.typography.titleMedium)
            Text("MES issues the authorized material list; PDA executes and reports.")
            Card {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Loading readiness", style = MaterialTheme.typography.titleMedium)
                    Text("PMC → MES → PDA → WMS")
                    Text("Scan: work order · machine · channel · feeder · material lot")
                    Text("Validation: BOM · IQC · lot status · quantity · operator")
                }
            }
            Button(onClick = { showMap = !showMap }) { Text(if (showMap) "Hide manual-line map" else "Show manual-line map") }
            if (showMap) {
                Text("HR: operator and training\nLine manager: station assignment and approval\nMES: route, BOM, permission, history\nWMS: lot, IQC, stock, issue and return")
            }
        }
    }
}
