package com.smt.materialloader.ui.navigation

import androidx.compose.runtime.*
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.smt.materialloader.MaterialLoaderApp
import com.smt.materialloader.data.api.dto.ShelfCell
import com.smt.materialloader.ui.dashboard.DashboardScreen
import com.smt.materialloader.ui.history.HistoryScreen
import com.smt.materialloader.ui.issue.IssueScreen
import com.smt.materialloader.ui.login.LoginScreen
import com.smt.materialloader.ui.materialloader.MaterialLoadScreen
import com.smt.materialloader.ui.query.QueryScreen
import com.smt.materialloader.ui.rack.RackDetailScreen
import com.smt.materialloader.ui.returnmaterial.ReturnScreen
import com.smt.materialloader.ui.shelfin.ShelfInScreen
import com.smt.materialloader.ui.shelfout.ShelfOutScreen
import com.smt.materialloader.ui.count.CountScreen
import com.smt.materialloader.ui.wolist.WoListScreen
import com.smt.materialloader.ui.wobind.WoBindScreen
import com.smt.materialloader.ui.document.InboundListScreen
import com.smt.materialloader.ui.document.OutboundListScreen
import com.smt.materialloader.ui.document.RequisitionListScreen
import com.smt.materialloader.ui.document.ReturnSlipListScreen
import com.smt.materialloader.ui.document.ReplenishmentListScreen
import com.smt.materialloader.ui.document.InboundDetailScreen
import com.smt.materialloader.ui.document.OutboundDetailScreen
import com.smt.materialloader.ui.document.RequisitionDetailScreen
import com.smt.materialloader.ui.document.ReturnSlipDetailScreen
import com.smt.materialloader.ui.document.ReplenishmentDetailScreen
import com.smt.materialloader.ui.document.InboundEditScreen
import com.smt.materialloader.ui.document.OutboundEditScreen
import com.smt.materialloader.ui.document.RequisitionEditScreen
import com.smt.materialloader.ui.document.ReturnSlipEditScreen
import com.smt.materialloader.ui.document.ReplenishmentEditScreen

object Routes {
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val ISSUE = "issue"
    const val RETURN = "return"
    const val QUERY = "query"
    const val RACK_DETAIL = "rack_detail"
    const val SHELF_IN = "shelf_in"
    const val SHELF_OUT = "shelf_out"
    const val HISTORY = "history"
    const val MATERIAL_LOAD = "material_load"
    const val WO_LIST = "wo_list"
    const val WO_BIND = "wo_bind"
    const val COUNT = "count"
    const val INBOUND = "inbound"
    const val OUTBOUND = "outbound"
    const val REQUISITION = "requisition"
    const val RETURN_SLIP = "return_slip"
    const val REPLENISHMENT = "replenishment"
    // Detail routes
    const val INBOUND_DETAIL = "inbound_detail"
    const val OUTBOUND_DETAIL = "outbound_detail"
    const val REQUISITION_DETAIL = "requisition_detail"
    const val RETURN_SLIP_DETAIL = "return_slip_detail"
    const val REPLENISHMENT_DETAIL = "replenishment_detail"
    // Edit routes
    const val INBOUND_EDIT = "inbound_edit"
    const val OUTBOUND_EDIT = "outbound_edit"
    const val REQUISITION_EDIT = "requisition_edit"
    const val RETURN_SLIP_EDIT = "return_slip_edit"
    const val REPLENISHMENT_EDIT = "replenishment_edit"
    // New document routes (no docId)
    const val INBOUND_EDIT_NEW = "inbound_edit_new"
    const val OUTBOUND_EDIT_NEW = "outbound_edit_new"
    const val REQUISITION_EDIT_NEW = "requisition_edit_new"
    const val RETURN_SLIP_EDIT_NEW = "return_slip_edit_new"
    const val REPLENISHMENT_EDIT_NEW = "replenishment_edit_new"
}

@Composable
fun AppNavHost(
    navController: NavHostController = rememberNavController()
) {
    val prefs = MaterialLoaderApp.instance.prefs
    val startDestination = if (prefs.hasToken()) Routes.DASHBOARD else Routes.LOGIN

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.DASHBOARD) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.DASHBOARD) {
            DashboardScreen(
                onNavigateToIssue = { navController.navigate(Routes.ISSUE) },
                onNavigateToReturn = { navController.navigate(Routes.RETURN) },
                onNavigateToQuery = { navController.navigate(Routes.QUERY) },
                onNavigateToRack = { shelfCode ->
                    navController.navigate("${Routes.RACK_DETAIL}/$shelfCode")
                },
                onNavigateToShelfIn = { shelfCode, cellNumber, cellLabel ->
                    navController.navigate("${Routes.SHELF_IN}/$shelfCode/$cellNumber/$cellLabel")
                },
                onNavigateToShelfOut = { shelfCode, cellJson ->
                    navController.navigate("${Routes.SHELF_OUT}/$shelfCode/$cellJson")
                },
                onNavigateToHistory = { navController.navigate(Routes.HISTORY) },
                onNavigateToMaterialLoad = { navController.navigate(Routes.MATERIAL_LOAD) },
                onNavigateToWoList = { navController.navigate(Routes.WO_LIST) },
                onNavigateToWoBind = { navController.navigate(Routes.WO_BIND) },
                onNavigateToCount = { navController.navigate(Routes.COUNT) },
                onNavigateToInbound = { navController.navigate(Routes.INBOUND) },
                onNavigateToOutbound = { navController.navigate(Routes.OUTBOUND) },
                onNavigateToRequisition = { navController.navigate(Routes.REQUISITION) },
                onNavigateToReturnSlip = { navController.navigate(Routes.RETURN_SLIP) },
                onNavigateToReplenishment = { navController.navigate(Routes.REPLENISHMENT) },
                onLogout = {
                    MaterialLoaderApp.instance.authRepository.logout()
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.ISSUE) {
            IssueScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.RETURN) {
            ReturnScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.QUERY) {
            QueryScreen(onBack = { navController.popBackStack() })
        }

        composable("${Routes.RACK_DETAIL}/{shelfCode}") { backStackEntry ->
            val shelfCode = backStackEntry.arguments?.getString("shelfCode") ?: ""
            RackDetailScreen(
                shelfCode = shelfCode,
                onBack = { navController.popBackStack() },
                onCellPress = { cell ->
                    if (cell.cellStatus == com.smt.materialloader.data.api.dto.CellStatus.OCCUPIED) {
                        val cellJson = "${cell.cellNumber}|${cell.cellLabel}|${cell.materialCode ?: ""}|${cell.lotNo ?: ""}|${cell.labelId ?: ""}|${cell.qty ?: 0}"
                        navController.navigate("${Routes.SHELF_OUT}/$shelfCode/$cellJson")
                    } else {
                        navController.navigate("${Routes.SHELF_IN}/$shelfCode/${cell.cellNumber}/${cell.cellLabel}")
                    }
                }
            )
        }

        composable("${Routes.SHELF_IN}/{shelfCode}/{cellNumber}/{cellLabel}") { backStackEntry ->
            val shelfCode = backStackEntry.arguments?.getString("shelfCode") ?: ""
            val cellNumber = backStackEntry.arguments?.getString("cellNumber") ?: ""
            val cellLabel = backStackEntry.arguments?.getString("cellLabel") ?: ""
            ShelfInScreen(
                shelfCode = shelfCode,
                cellNumber = cellNumber,
                cellLabel = cellLabel,
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() }
            )
        }

        composable("${Routes.SHELF_OUT}/{shelfCode}/{cellJson}") { backStackEntry ->
            val shelfCode = backStackEntry.arguments?.getString("shelfCode") ?: ""
            val cellJson = backStackEntry.arguments?.getString("cellJson") ?: ""
            val parts = cellJson.split("|")
            val cell = ShelfCell(
                shelfCode = shelfCode,
                cellNumber = parts.getOrElse(0) { "" },
                cellLabel = parts.getOrElse(1) { "" },
                materialCode = parts.getOrElse(2) { null },
                lotNo = parts.getOrElse(3) { null },
                labelId = parts.getOrElse(4) { null },
                qty = parts.getOrElse(5) { "0" }.toIntOrNull(),
                cellStatus = com.smt.materialloader.data.api.dto.CellStatus.OCCUPIED
            )
            ShelfOutScreen(
                shelfCode = shelfCode,
                cell = cell,
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() }
            )
        }

        composable(Routes.HISTORY) {
            HistoryScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.MATERIAL_LOAD) {
            MaterialLoadScreen(
                initialWoCode = null,
                onBack = { navController.popBackStack() }
            )
        }

        composable("${Routes.MATERIAL_LOAD}/{woCode}") { backStackEntry ->
            val woCode = backStackEntry.arguments?.getString("woCode")
            MaterialLoadScreen(
                initialWoCode = woCode,
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.WO_LIST) {
            WoListScreen(
                onBack = { navController.popBackStack() },
                onWoSelected = { woCode ->
                    navController.navigate("${Routes.MATERIAL_LOAD}/$woCode")
                }
            )
        }

        composable(Routes.WO_BIND) {
            WoBindScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.COUNT) {
            CountScreen(onBack = { navController.popBackStack() })
        }

        composable(Routes.INBOUND) {
            InboundListScreen(
                onBack = { navController.popBackStack() },
                onNavigateToDetail = { docId -> navController.navigate("${Routes.INBOUND_DETAIL}/$docId") },
                onNavigateToCreate = { navController.navigate(Routes.INBOUND_EDIT_NEW) }
            )
        }

        composable(Routes.OUTBOUND) {
            OutboundListScreen(
                onBack = { navController.popBackStack() },
                onNavigateToDetail = { docId -> navController.navigate("${Routes.OUTBOUND_DETAIL}/$docId") },
                onNavigateToCreate = { navController.navigate(Routes.OUTBOUND_EDIT_NEW) }
            )
        }

        composable(Routes.REQUISITION) {
            RequisitionListScreen(
                onBack = { navController.popBackStack() },
                onNavigateToDetail = { docId -> navController.navigate("${Routes.REQUISITION_DETAIL}/$docId") },
                onNavigateToCreate = { navController.navigate(Routes.REQUISITION_EDIT_NEW) }
            )
        }

        composable(Routes.RETURN_SLIP) {
            ReturnSlipListScreen(
                onBack = { navController.popBackStack() },
                onNavigateToDetail = { docId -> navController.navigate("${Routes.RETURN_SLIP_DETAIL}/$docId") },
                onNavigateToCreate = { navController.navigate(Routes.RETURN_SLIP_EDIT_NEW) }
            )
        }

        composable(Routes.REPLENISHMENT) {
            ReplenishmentListScreen(
                onBack = { navController.popBackStack() },
                onNavigateToDetail = { docId -> navController.navigate("${Routes.REPLENISHMENT_DETAIL}/$docId") },
                onNavigateToCreate = { navController.navigate(Routes.REPLENISHMENT_EDIT_NEW) }
            )
        }

        // ── Document Detail Routes ────────────────────────────────────

        composable("${Routes.INBOUND_DETAIL}/{docId}") { backStackEntry ->
            val docId = backStackEntry.arguments?.getString("docId")?.toLongOrNull() ?: 0L
            InboundDetailScreen(
                onBack = { navController.popBackStack() },
                docId = docId,
                onNavigateToEdit = { id -> navController.navigate("${Routes.INBOUND_EDIT}/$id") },
                onNavigateToList = { navController.popBackStack(Routes.INBOUND, false) }
            )
        }

        composable("${Routes.OUTBOUND_DETAIL}/{docId}") { backStackEntry ->
            val docId = backStackEntry.arguments?.getString("docId")?.toLongOrNull() ?: 0L
            OutboundDetailScreen(
                onBack = { navController.popBackStack() },
                docId = docId,
                onNavigateToEdit = { id -> navController.navigate("${Routes.OUTBOUND_EDIT}/$id") },
                onNavigateToList = { navController.popBackStack(Routes.OUTBOUND, false) }
            )
        }

        composable("${Routes.REQUISITION_DETAIL}/{docId}") { backStackEntry ->
            val docId = backStackEntry.arguments?.getString("docId")?.toLongOrNull() ?: 0L
            RequisitionDetailScreen(
                onBack = { navController.popBackStack() },
                docId = docId,
                onNavigateToEdit = { id -> navController.navigate("${Routes.REQUISITION_EDIT}/$id") },
                onNavigateToList = { navController.popBackStack(Routes.REQUISITION, false) }
            )
        }

        composable("${Routes.RETURN_SLIP_DETAIL}/{docId}") { backStackEntry ->
            val docId = backStackEntry.arguments?.getString("docId")?.toLongOrNull() ?: 0L
            ReturnSlipDetailScreen(
                onBack = { navController.popBackStack() },
                docId = docId,
                onNavigateToEdit = { id -> navController.navigate("${Routes.RETURN_SLIP_EDIT}/$id") },
                onNavigateToList = { navController.popBackStack(Routes.RETURN_SLIP, false) }
            )
        }

        composable("${Routes.REPLENISHMENT_DETAIL}/{docId}") { backStackEntry ->
            val docId = backStackEntry.arguments?.getString("docId")?.toLongOrNull() ?: 0L
            ReplenishmentDetailScreen(
                onBack = { navController.popBackStack() },
                docId = docId,
                onNavigateToEdit = { id -> navController.navigate("${Routes.REPLENISHMENT_EDIT}/$id") },
                onNavigateToList = { navController.popBackStack(Routes.REPLENISHMENT, false) }
            )
        }

        // ── Document Edit Routes ──────────────────────────────────────

        composable("${Routes.INBOUND_EDIT}/{docId}") { backStackEntry ->
            val docIdStr = backStackEntry.arguments?.getString("docId")
            val editId = docIdStr?.toLongOrNull()
            InboundEditScreen(
                onBack = { navController.popBackStack() },
                editId = editId
            )
        }

        composable("${Routes.OUTBOUND_EDIT}/{docId}") { backStackEntry ->
            val docIdStr = backStackEntry.arguments?.getString("docId")
            val editId = docIdStr?.toLongOrNull()
            OutboundEditScreen(
                onBack = { navController.popBackStack() },
                editId = editId
            )
        }

        composable("${Routes.REQUISITION_EDIT}/{docId}") { backStackEntry ->
            val docIdStr = backStackEntry.arguments?.getString("docId")
            val editId = docIdStr?.toLongOrNull()
            RequisitionEditScreen(
                onBack = { navController.popBackStack() },
                editId = editId
            )
        }

        composable("${Routes.RETURN_SLIP_EDIT}/{docId}") { backStackEntry ->
            val docIdStr = backStackEntry.arguments?.getString("docId")
            val editId = docIdStr?.toLongOrNull()
            ReturnSlipEditScreen(
                onBack = { navController.popBackStack() },
                editId = editId
            )
        }

        composable("${Routes.REPLENISHMENT_EDIT}/{docId}") { backStackEntry ->
            val docIdStr = backStackEntry.arguments?.getString("docId")
            val editId = docIdStr?.toLongOrNull()
            ReplenishmentEditScreen(
                onBack = { navController.popBackStack() },
                editId = editId
            )
        }

        // ── New Document Routes ───────────────────────────────────────

        composable(Routes.INBOUND_EDIT_NEW) {
            InboundEditScreen(onBack = { navController.popBackStack() }, editId = null)
        }

        composable(Routes.OUTBOUND_EDIT_NEW) {
            OutboundEditScreen(onBack = { navController.popBackStack() }, editId = null)
        }

        composable(Routes.REQUISITION_EDIT_NEW) {
            RequisitionEditScreen(onBack = { navController.popBackStack() }, editId = null)
        }

        composable(Routes.RETURN_SLIP_EDIT_NEW) {
            ReturnSlipEditScreen(onBack = { navController.popBackStack() }, editId = null)
        }

        composable(Routes.REPLENISHMENT_EDIT_NEW) {
            ReplenishmentEditScreen(onBack = { navController.popBackStack() }, editId = null)
        }
    }
}