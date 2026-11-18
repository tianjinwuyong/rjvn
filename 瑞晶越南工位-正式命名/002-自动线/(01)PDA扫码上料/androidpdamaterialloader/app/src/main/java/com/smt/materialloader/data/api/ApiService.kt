package com.smt.materialloader.data.api

import com.smt.materialloader.data.api.dto.*
import com.smt.materialloader.data.api.dto.ShelfListResponse
import com.smt.materialloader.data.api.dto.ShelfDetailResponse
import com.smt.materialloader.data.api.dto.ShelfInRequest
import com.smt.materialloader.data.api.dto.ShelfOutRequest
import com.smt.materialloader.data.api.dto.ShelfActionResponse
import com.smt.materialloader.data.api.dto.TransactionHistoryResponse
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    // ── Auth ────────────────────────────────────────────────────────

    @POST("/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<ApiEnvelope<LoginResponse>>

    @GET("/auth/session")
    suspend fun getSession(): Response<ApiEnvelope<SessionResponse>>

    // ── WMS / Material Lots ─────────────────────────────────────────

    @GET("/wms/material-lots")
    suspend fun getMaterialLots(
        @Query("lotNo") lotNo: String? = null,
        @Query("iqcStatus") iqcStatus: String? = null,
        @Query("q") q: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<ApiEnvelope<ListEnvelope<MaterialLotDto>>>

    @GET("/wms/stock")
    suspend fun getStock(
        @Query("materialCode") materialCode: String? = null,
        @Query("iqcStatus") iqcStatus: String? = null
    ): Response<ApiEnvelope<ListEnvelope<StockDto>>>

    @GET("/wms/lot-transactions/{lotId}")
    suspend fun getLotTransactions(
        @Path("lotId") lotId: String
    ): Response<ApiEnvelope<ListEnvelope<InventoryTransactionDto>>>

    // ── WMS / Issue & Return ────────────────────────────────────────

    @POST("/wms/issue-to-line")
    suspend fun issueToLine(
        @Body request: IssueRequest
    ): Response<ApiEnvelope<IssueResponse>>

    @POST("/wms/return-from-line")
    suspend fun returnFromLine(
        @Body request: ReturnRequest
    ): Response<ApiEnvelope<ReturnResponse>>

    // ── PMC / Work Orders ──────────────────────────────────────────

    @GET("/pmc/work-orders")
    suspend fun getWorkOrders(
        @Query("q") q: String? = null,
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<ApiEnvelope<ListEnvelope<WorkOrderDto>>>

    @GET("/erp/boms/product/{productCode}")
    suspend fun getBomForProduct(
        @Path("productCode") productCode: String
    ): Response<ApiEnvelope<BomDto>>

    // ── PMC / WO Lock/Unlock ───────────────────────────────────────

    @POST("/pmc/work-orders/{code}/lock")
    suspend fun lockWorkOrder(
        @Path("code") code: String,
        @Body payload: Map<String, String>
    ): Response<ApiEnvelope<Map<String, Any?>>>

    @POST("/pmc/work-orders/{code}/unlock")
    suspend fun unlockWorkOrder(
        @Path("code") code: String,
        @Body payload: Map<String, String>
    ): Response<ApiEnvelope<Map<String, Any?>>>

    @POST("/pmc/work-orders/{code}/complete")
    suspend fun completeWorkOrder(
        @Path("code") code: String,
        @Body payload: Map<String, String>
    ): Response<ApiEnvelope<Map<String, Any?>>>

    // ── MES / Feeder Loading ───────────────────────────────────────

    @POST("/mes/feeder-loading")
    suspend fun confirmFeederLoad(
        @Body request: FeederLoadRequest
    ): Response<ApiEnvelope<FeederLoadResponse>>

    @DELETE("/mes/feeder-loading/{id}")
    suspend fun returnFeederLoad(
        @Path("id") id: String,
        @Body request: FeederUnloadRequest
    ): Response<ApiEnvelope<FeederUnloadResponse>>

    // ── MES / Work Start ────────────────────────────────────────────

    @POST("/mes/work-start")
    suspend fun workStart(
        @Body request: WorkStartRequest
    ): Response<ApiEnvelope<WorkStartResponse>>

    @POST("/mes/feeder-validate")
    suspend fun validateFeeder(
        @Body request: FeederValidateRequest
    ): Response<ApiEnvelope<FeederValidateResponse>>

    // ── MES / Feeder Binding (4-way anti-error) ───────────────────────

    @POST("/mes/feeder-binding/validate")
    suspend fun feederBindingValidate(
        @Body request: FeederBindingValidateRequest
    ): Response<ApiEnvelope<FeederBindingValidateResponse>>

    @POST("/mes/feeder-binding/confirm")
    suspend fun feederBindingConfirm(
        @Body request: FeederBindingConfirmRequest
    ): Response<ApiEnvelope<FeederBindingConfirmResponse>>

    @DELETE("/mes/feeder-binding/{id}")
    suspend fun feederBindingUnbind(
        @Path("id") id: String,
        @Body request: FeederBindingUnbindRequest
    ): Response<ApiEnvelope<FeederBindingUnbindResponse>>

    @GET("/mes/feeder-binding/{workOrderCode}")
    suspend fun feederBindingList(
        @Path("workOrderCode") workOrderCode: String
    ): Response<ApiEnvelope<List<FeederBindingConfirmResponse>>>

    // ── MES / Return Reason Codes ─────────────────────────────────────

    @GET("/mes/return-reason-codes")
    suspend fun getReturnReasonCodes(): Response<ApiEnvelope<ListEnvelope<ReturnReasonDto>>>

    // ── WMS / Smart Shelf ───────────────────────────────────────────

    @GET("/wms/shelf/list")
    suspend fun getShelfList(): Response<ApiEnvelope<ShelfListResponse>>

    @GET("/wms/shelf/{shelfCode}")
    suspend fun getShelfDetail(@Path("shelfCode") shelfCode: String): Response<ApiEnvelope<ShelfDetailResponse>>

    @POST("/wms/shelf/shelf-in")
    suspend fun shelfIn(@Body request: ShelfInRequest): Response<ApiEnvelope<ShelfActionResponse>>

    @POST("/wms/shelf/shelf-out")
    suspend fun shelfOut(@Body request: ShelfOutRequest): Response<ApiEnvelope<ShelfActionResponse>>

    @POST("/api/wms/shelf/place-wo")
    suspend fun placeWo(@Body request: PlaceWoRequest): Response<ApiEnvelope<PlaceWoResponse>>

    @GET("/wms/shelf/transactions")
    suspend fun getShelfTransactions(
        @Query("shelfCode") shelfCode: String? = null,
        @Query("action") action: String? = null,
        @Query("limit") limit: Int? = null,
        @Query("offset") offset: Int? = null
    ): Response<ApiEnvelope<TransactionHistoryResponse>>

    // ── WMS / Count Sessions ──────────────────────────────────────────

    @GET("/wms/count-sessions")
    suspend fun getCountSessions(
        @Query("status") status: String? = null,
        @Query("locationCode") locationCode: String? = null,
        @Query("triggerType") triggerType: String? = null,
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0
    ): Response<ApiEnvelope<ListEnvelope<CountSessionDto>>>

    @GET("/wms/count-sessions/{id}")
    suspend fun getCountSessionDetail(
        @Path("id") id: String
    ): Response<ApiEnvelope<CountSessionDetailResponse>>

    @POST("/wms/count-sessions/{id}/claim")
    suspend fun claimCountSession(
        @Path("id") id: String
    ): Response<ApiEnvelope<CountClaimResponse>>

    @POST("/wms/count-items/{id}/count")
    suspend fun countItem(
        @Path("id") id: String,
        @Body request: CountItemCountRequest
    ): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/count-sessions/{id}/submit")
    suspend fun submitCountSession(
        @Path("id") id: String,
        @Body request: CountSubmitRequest
    ): Response<ApiEnvelope<CountSubmitResponse>>

    @GET("/wms/count-alerts")
    suspend fun getCountAlerts(
        @Query("acknowledged") acknowledged: Boolean? = null,
        @Query("alertType") alertType: String? = null,
        @Query("limit") limit: Int = 50
    ): Response<ApiEnvelope<ListEnvelope<CountAlertDto>>>

    @PATCH("/wms/count-alerts/{id}/acknowledge")
    suspend fun acknowledgeCountAlert(
        @Path("id") id: String
    ): Response<ApiEnvelope<Map<String, Any>>>

    // ── Document Management ────────────────────────────────────────

    @GET("/wms/inbound")
    suspend fun getInboundOrders(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 20
    ): Response<ApiEnvelope<DocListResponse>>

    @GET("/wms/inbound/{id}")
    suspend fun getInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/inbound")
    suspend fun createInboundOrder(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @PATCH("/wms/inbound/{id}")
    suspend fun updateInboundOrder(@Path("id") id: Long, @Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @DELETE("/wms/inbound/{id}")
    suspend fun deleteInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/inbound/submit/{id}")
    suspend fun submitInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/inbound/approve/{id}")
    suspend fun approveInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/inbound/reject/{id}")
    suspend fun rejectInboundOrder(@Path("id") id: Long, @Body body: Map<String, Any> = emptyMap()): Response<ApiEnvelope<DocDto>>

    @POST("/wms/inbound/execute/{id}")
    suspend fun executeInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/inbound/complete/{id}")
    suspend fun completeInboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @GET("/wms/outbound")
    suspend fun getOutboundOrders(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 20
    ): Response<ApiEnvelope<DocListResponse>>

    @GET("/wms/outbound/{id}")
    suspend fun getOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/outbound")
    suspend fun createOutboundOrder(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @PATCH("/wms/outbound/{id}")
    suspend fun updateOutboundOrder(@Path("id") id: Long, @Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @DELETE("/wms/outbound/{id}")
    suspend fun deleteOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/outbound/submit/{id}")
    suspend fun submitOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/outbound/approve/{id}")
    suspend fun approveOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/outbound/reject/{id}")
    suspend fun rejectOutboundOrder(@Path("id") id: Long, @Body body: Map<String, Any> = emptyMap()): Response<ApiEnvelope<DocDto>>

    @POST("/wms/outbound/execute/{id}")
    suspend fun executeOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/outbound/complete/{id}")
    suspend fun completeOutboundOrder(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @GET("/wms/requisition")
    suspend fun getRequisitions(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 20
    ): Response<ApiEnvelope<DocListResponse>>

    @GET("/wms/requisition/{id}")
    suspend fun getRequisition(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/requisition")
    suspend fun createRequisition(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @PATCH("/wms/requisition/{id}")
    suspend fun updateRequisition(@Path("id") id: Long, @Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @DELETE("/wms/requisition/{id}")
    suspend fun deleteRequisition(@Path("id") id: Long): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/requisition/submit/{id}")
    suspend fun submitRequisition(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/requisition/approve/{id}")
    suspend fun approveRequisition(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/requisition/reject/{id}")
    suspend fun rejectRequisition(@Path("id") id: Long, @Body body: Map<String, Any> = emptyMap()): Response<ApiEnvelope<DocDto>>

    @POST("/wms/requisition/execute/{id}")
    suspend fun executeRequisition(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/requisition/complete/{id}")
    suspend fun completeRequisition(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @GET("/wms/return")
    suspend fun getReturnSlips(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 20
    ): Response<ApiEnvelope<DocListResponse>>

    @GET("/wms/return/{id}")
    suspend fun getReturnSlip(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/return")
    suspend fun createReturnSlip(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @PATCH("/wms/return/{id}")
    suspend fun updateReturnSlip(@Path("id") id: Long, @Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @DELETE("/wms/return/{id}")
    suspend fun deleteReturnSlip(@Path("id") id: Long): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/return/submit/{id}")
    suspend fun submitReturnSlip(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/return/reject/{id}")
    suspend fun rejectReturnSlip(@Path("id") id: Long, @Body body: Map<String, Any> = emptyMap()): Response<ApiEnvelope<DocDto>>

    @POST("/wms/return/execute/{id}")
    suspend fun executeReturnSlip(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/return/complete/{id}")
    suspend fun completeReturnSlip(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @GET("/wms/replenishment")
    suspend fun getReplenishments(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 20
    ): Response<ApiEnvelope<DocListResponse>>

    @GET("/wms/replenishment/{id}")
    suspend fun getReplenishment(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/replenishment")
    suspend fun createReplenishment(@Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @PATCH("/wms/replenishment/{id}")
    suspend fun updateReplenishment(@Path("id") id: Long, @Body body: Map<String, @JvmSuppressWildcards Any>): Response<ApiEnvelope<DocDto>>

    @DELETE("/wms/replenishment/{id}")
    suspend fun deleteReplenishment(@Path("id") id: Long): Response<ApiEnvelope<Map<String, Any>>>

    @POST("/wms/replenishment/submit/{id}")
    suspend fun submitReplenishment(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/replenishment/approve/{id}")
    suspend fun approveReplenishment(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/replenishment/reject/{id}")
    suspend fun rejectReplenishment(@Path("id") id: Long, @Body body: Map<String, Any> = emptyMap()): Response<ApiEnvelope<DocDto>>

    @POST("/wms/replenishment/execute/{id}")
    suspend fun executeReplenishment(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>

    @POST("/wms/replenishment/complete/{id}")
    suspend fun completeReplenishment(@Path("id") id: Long): Response<ApiEnvelope<DocDto>>
}
