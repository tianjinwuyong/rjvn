package com.smt.materialloader.ui.login

import android.app.Activity
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smt.materialloader.MaterialLoaderApp
import com.smt.materialloader.BuildConfig
import com.smt.materialloader.data.repository.AuthRepository
import com.smt.materialloader.data.api.dto.UserInfo
import com.smt.materialloader.alarm.ManagerAlarmService
import com.smt.materialloader.util.LocaleManager
import com.smt.materialloader.util.PreferencesManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LoginUiState(
    val username: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val selectedLocale: String = "zh-CN",
    val isSuccess: Boolean = false
)

class LoginViewModel : ViewModel() {

    private val prefs: PreferencesManager = MaterialLoaderApp.instance.prefs
    private val authRepo: AuthRepository = MaterialLoaderApp.instance.authRepository

    private val _state = MutableStateFlow(
        LoginUiState(selectedLocale = prefs.getLocale())
    )
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun onUsernameChanged(value: String) {
        _state.value = _state.value.copy(username = value, error = null)
    }

    fun onPasswordChanged(value: String) {
        _state.value = _state.value.copy(password = value, error = null)
    }

    fun onLocaleChanged(locale: String) {
        _state.value = _state.value.copy(selectedLocale = locale)
        prefs.saveLocale(locale)
        // Restart activity to apply new locale immediately
        val activity = MaterialLoaderApp.instance.currentActivity
        if (activity != null) {
            LocaleManager.applyLocale(activity, locale)
            activity.recreate()
        }
    }

    /** Virtual employees are unavailable in production builds by construction. */
    val demoAccounts: List<DemoAccount> = when {
        !BuildConfig.TEST_ACTION_BYPASS_ENABLED -> emptyList()
        BuildConfig.PLANT_MANAGER_APP -> VirtualEmployeeCatalog.seniorManagers
        // The full Unified Management PDA exposes the complete local role
        // catalog, including plant-manager identities, so one APK can be
        // used for receiving, IQC, warehouse, MES, PMC, production,
        // engineering, line leadership, and approvals.
        else -> VirtualEmployeeCatalog.standard + VirtualEmployeeCatalog.seniorManagers + VirtualEmployeeCatalog.plantManager
    }

    fun login() {
        val s = _state.value
        if (s.username.isBlank() || s.password.isBlank()) {
            _state.value = s.copy(error = "Please fill in all fields")
            return
        }

        _state.value = s.copy(isLoading = true, error = null)

        viewModelScope.launch {
            val result = authRepo.login(s.username, s.password)
            result.fold(
                onSuccess = {
                    ManagerAlarmService.start(MaterialLoaderApp.instance)
                    _state.value = _state.value.copy(isLoading = false, isSuccess = true)
                },
                onFailure = { error ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = error.message ?: "Login failed"
                    )
                }
            )
        }
    }

    fun quickLogin(account: DemoAccount) {
        val effectiveRoleKey = account.roleKey
        _state.value = _state.value.copy(
            username = account.username,
            password = account.password,
            isLoading = BuildConfig.TEST_ACTION_BYPASS_ENABLED,
            error = null
        )

        // Test builds may still seed a local identity for roles that have no DB
        // account (pure UI demo roles). For real operator accounts (VN_WC_*,
        // VN_WH_*, VN_LM_*, line managers, plant managers) the quick login goes
        // through the REAL authenticated login so material collection/issue is
        // recorded under the actual 工号 (实名) — never under a shared test user.
        if (BuildConfig.TEST_ACTION_BYPASS_ENABLED) {
            viewModelScope.launch {
                val real = authRepo.login(account.username, account.password)
                if (real.isSuccess) {
                    // Real authenticated session: DB user recorded as the actor.
                    // Persist the REAL identity (id/role/display) so landing
                    // routes and screens match the JWT — a stale pref user was
                    // the cause of PDAs landing on the wrong home screen.
                    val u = real.getOrNull()?.user
                    prefs.saveLocale(u?.locale ?: account.let { "zh-CN" })
                    account.lineCode?.takeIf { it.isNotBlank() }
                        ?.let { prefs.saveLineCode(it) }
                    if (u != null) {
                        prefs.saveUser(UserInfo(
                            id = u.id,
                            username = u.username,
                            displayName = u.displayName,
                            locale = u.locale,
                            roleKey = u.roleKey,
                            permissions = u.permissions ?: EmployeeRightsCatalog
                                .forRole(effectiveRoleKey, account.lineCode, account.seniority).permissions.toList(),
                            lineCode = u.lineCode,
                            seniority = account.seniority
                        ))
                    } else {
                        // Server did not echo a user profile — mirror the local
                        // account so the role key is still correct for routing.
                        val testPermissions = EmployeeRightsCatalog
                            .forRole(effectiveRoleKey, account.lineCode, account.seniority).permissions.toList()
                        prefs.saveUser(UserInfo(
                            id = account.username,
                            username = account.username,
                            displayName = account.label,
                            locale = "zh-CN",
                            roleKey = effectiveRoleKey,
                            permissions = testPermissions,
                            lineCode = account.lineCode,
                            seniority = account.seniority
                        ))
                    }
                    ManagerAlarmService.start(MaterialLoaderApp.instance)
                    _state.value = _state.value.copy(isLoading = false, isSuccess = true)
                    return@launch
                }
                // No DB account for this demo role — fall back to the shared WMS
                // test session and a local identity (lab-only, never production).
                authRepo.login("VN_WH_001", "Factory@123")
                val testPermissions = EmployeeRightsCatalog
                    .forRole(effectiveRoleKey, account.lineCode, account.seniority)
                    .permissions
                    .toList()
                prefs.saveUser(UserInfo(
                    id = "test-${effectiveRoleKey.lowercase()}",
                    username = account.username,
                    displayName = account.label,
                    locale = "zh-CN",
                    roleKey = effectiveRoleKey,
                    permissions = testPermissions,
                    lineCode = account.lineCode,
                    seniority = account.seniority
                ))
                account.lineCode?.let { prefs.saveLineCode(it) }
                ManagerAlarmService.start(MaterialLoaderApp.instance)
                _state.value = _state.value.copy(isLoading = false, isSuccess = true)
            }
            return
        }

        viewModelScope.launch {
            val result = authRepo.login(account.username, account.password)
            result.fold(
                onSuccess = {
                    ManagerAlarmService.start(MaterialLoaderApp.instance)
                    _state.value = _state.value.copy(isLoading = false, isSuccess = true)
                },
                onFailure = { error ->
                    _state.value = _state.value.copy(
                        isLoading = false,
                        error = error.message ?: "Login failed"
                    )
                }
            )
        }
    }
}
