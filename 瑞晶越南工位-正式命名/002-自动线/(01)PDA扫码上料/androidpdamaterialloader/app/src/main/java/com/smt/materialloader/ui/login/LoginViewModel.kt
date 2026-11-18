package com.smt.materialloader.ui.login

import android.app.Activity
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.smt.materialloader.MaterialLoaderApp
import com.smt.materialloader.data.repository.AuthRepository
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

    data class DemoAccount(
        val username: String,
        val label: String,
        val role: String,
        val password: String = "Factory@123"
    )

    val demoAccounts = listOf(
        DemoAccount("VN_OP_001", "操作员", "SMT Operator"),
        DemoAccount("VN_WH_001", "仓库", "Warehouse"),
        DemoAccount("PMC_CN_01", "PMC", "Production Control"),
        DemoAccount("QC_VN_01", "质检", "Quality"),
        DemoAccount("FIN_VN_001", "财务", "Finance")
    )

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
        _state.value = _state.value.copy(
            username = account.username,
            password = account.password,
            isLoading = true,
            error = null
        )
        viewModelScope.launch {
            val result = authRepo.login(account.username, account.password)
            result.fold(
                onSuccess = {
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
