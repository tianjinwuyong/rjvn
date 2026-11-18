package com.smt.materialloader.ui.login

/**
 * Effective rights for one employee session. MES remains the authority for
 * production users; this resolver only defines the shared PDA capability shape
 * used by the local test catalog and the UI capability checks.
 */
data class EmployeeRights(
    val roleKey: String,
    val lineCode: String?,
    val seniority: String = "STANDARD",
    val permissions: Set<String>
) {
    fun allows(permission: String): Boolean = permission in permissions
}

object EmployeeRightsCatalog {
    private val employeeBase = setOf(
        "pda.view",
        "employee.self.view",
        "employee.attendance.view",
        "employee.leave.submit"
    )

    private val rolePermissions: Map<String, Set<String>> = mapOf(
        "MATERIAL_LOADER" to setOf("smt.loading.view", "smt.loading.bind"),
        "MANUAL_LINE_LOADER" to setOf("smt.loading.view", "smt.loading.bind"),
        "AUTO_LINE_LOADER" to setOf("smt.loading.view", "smt.loading.bind"),
        "SMT_LOADER" to setOf("smt.loading.view", "smt.loading.bind"),
        "SMT_OPERATOR" to setOf("smt.loading.view", "smt.loading.bind"),
        "MATERIAL_OPERATOR" to setOf("smt.loading.view", "smt.loading.bind"),
        "GROUP_LEADER" to setOf(
            "manager.view",
            "ng.pickup.ack",
            "ng.alert.ack",
            "repair.handover.ack"
        ),
        "LINE_MANAGER" to setOf(
            "manager.view",
            "manager.team.view",
            "ng.pickup.ack",
            "ng.alert.ack",
            "repair.handover.ack",
            "approval.request.review"
        ),
        "PLANT_MANAGER" to setOf(
            "manager.view",
            "manager.team.view",
            "manager.site.view",
            "approval.request.review",
            "approval.final.release"
        ),
        "WAREHOUSE" to setOf("wms.view", "wms.transaction"),
        "MATERIAL_FETCHER" to setOf("wms.view", "wms.fetch.view", "wms.fetch.execute"),
        "WAREHOUSE_MANAGER" to setOf("wms.view", "wms.execute"),
        "MATERIAL_COLLECTOR" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_COLLECTOR_SMT" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_COLLECTOR_AUTO" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_COLLECTOR_MAN" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_PICKER_SMT" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_PICKER_AUTO" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_PICKER_MAN" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_PICKER_PACKAGING" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MATERIAL_PICKER" to setOf("wms.view", "wms.collect.view", "wms.collect.execute", "wms.issue"),
        "MES" to setOf("manager.view", "approval.view"),
        "PMC" to setOf("manager.view", "approval.view"),
        "IQC" to setOf("manager.view", "approval.view"),
        "ENGINEERING" to setOf("manager.view", "approval.view"),
        "PRODUCTION" to setOf("manager.view", "approval.view")
    )

    /** Role inheritance keeps the domain model explicit and prevents permission drift. */
    private val roleParents: Map<String, List<String>> = mapOf(
        "MATERIAL_LOADER" to listOf("EMPLOYEE"),
        "MANUAL_LINE_LOADER" to listOf("MATERIAL_LOADER"),
        "AUTO_LINE_LOADER" to listOf("MATERIAL_LOADER"),
        "SMT_LOADER" to listOf("MATERIAL_LOADER"),
        "SMT_OPERATOR" to listOf("MATERIAL_LOADER"),
        "MATERIAL_OPERATOR" to listOf("MATERIAL_LOADER"),
        "GROUP_LEADER" to listOf("EMPLOYEE"),
        "LINE_MANAGER" to listOf("GROUP_LEADER"),
        "LINE_MANAGER_SMT" to listOf("LINE_MANAGER"),
        "LINE_MANAGER_AUTO" to listOf("LINE_MANAGER"),
        "LINE_MANAGER_MANUAL" to listOf("LINE_MANAGER"),
        "PLANT_MANAGER" to listOf("LINE_MANAGER"),
        "WAREHOUSE" to listOf("EMPLOYEE"),
        "MATERIAL_FETCHER" to listOf("EMPLOYEE"),
        "MES" to listOf("EMPLOYEE"),
        "PMC" to listOf("EMPLOYEE"),
        "IQC" to listOf("EMPLOYEE"),
        "ENGINEERING" to listOf("EMPLOYEE"),
        "PRODUCTION" to listOf("EMPLOYEE")
    )

    @JvmOverloads
    fun forRole(roleKey: String, lineCode: String?, seniority: String = "SENIOR"): EmployeeRights {
        val normalizedRole = roleKey.trim().uppercase()
        val normalizedSeniority = seniority.trim().uppercase().ifBlank { "STANDARD" }
        return EmployeeRights(
            roleKey = normalizedRole,
            lineCode = lineCode?.trim()?.uppercase()?.takeIf { it.isNotBlank() },
            seniority = normalizedSeniority,
            permissions = permissionsFor(normalizedRole, normalizedSeniority)
        )
    }

    private fun permissionsFor(roleKey: String, seniority: String = "SENIOR", visiting: Set<String> = emptySet()): Set<String> {
        if (roleKey in visiting) return emptySet()
        val parents = roleParents[roleKey].orEmpty()
        val seniorOnly = if (roleKey == "PLANT_MANAGER" && seniority != "JUNIOR") setOf("approval.final.release") else emptySet()
        return rolePermissions[roleKey].orEmpty() + seniorOnly + parents.flatMap {
            permissionsFor(it, seniority, visiting + roleKey)
        }.toSet() + employeeBase
    }
}
