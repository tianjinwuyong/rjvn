from __future__ import annotations

LOCALES=("zh","en","vi")

TEXT={
"zh":{"preview":"预览 · 已禁止写入","production":"生产模式","no_alarm":"无新报警 · 历史报警保持静默","product_context":"产品上下文","product_sn":"产品SN","work_order":"工单","gate":"产品门禁","reason":"原因","normal_next":"正常下一站","mes_controlled":"MES管理","waiting_mes":"等待MES","workspace":"生产工作区","result_next":"结果 / 下一动作","idle":"空闲","scan_gate":"扫描产品并请求MES门禁","authorization":"授权：MES","repair_route":"NG维修路由","action":"动作","retest":"复测次数","destination":"维修目的地","receipt_sla":"收单SLA","repair_sla":"维修SLA","return":"返回路由","policy":"策略","open_repair":"打开维修闭环","writes_blocked":"不写MES · 不重放报警"},
"en":{"preview":"PREVIEW · WRITES BLOCKED","production":"PRODUCTION","no_alarm":"No new alarm · historical alarms stay silent","product_context":"PRODUCT CONTEXT","product_sn":"Product SN","work_order":"Work order","gate":"Product Gate","reason":"Reason","normal_next":"Normal next","mes_controlled":"MES controlled","waiting_mes":"Waiting for MES","workspace":"PRODUCTION WORKSPACE","result_next":"RESULT / NEXT ACTION","idle":"IDLE","scan_gate":"Scan product and request MES gate","authorization":"Authorization: MES","repair_route":"NG REPAIR ROUTE","action":"Action","retest":"Retest limit","destination":"Destination","receipt_sla":"Receipt SLA","repair_sla":"Repair SLA","return":"Return route","policy":"Policy","open_repair":"OPEN REPAIR CLOSED LOOP","writes_blocked":"No MES write · no alarm replay"},
"vi":{"preview":"XEM THỬ · CHẶN GHI DỮ LIỆU","production":"SẢN XUẤT","no_alarm":"Không có cảnh báo mới · cảnh báo cũ không phát lại","product_context":"NGỮ CẢNH SẢN PHẨM","product_sn":"SN sản phẩm","work_order":"Lệnh sản xuất","gate":"Kiểm soát sản phẩm","reason":"Lý do","normal_next":"Công đoạn tiếp","mes_controlled":"MES quản lý","waiting_mes":"Chờ MES","workspace":"KHU VỰC SẢN XUẤT","result_next":"KẾT QUẢ / HÀNH ĐỘNG TIẾP","idle":"CHỜ","scan_gate":"Quét sản phẩm và yêu cầu MES kiểm tra","authorization":"Phê duyệt: MES","repair_route":"TUYẾN SỬA CHỮA NG","action":"Hành động","retest":"Số lần thử lại","destination":"Nơi sửa chữa","receipt_sla":"SLA nhận","repair_sla":"SLA sửa chữa","return":"Tuyến trả về","policy":"Chính sách","open_repair":"MỞ QUY TRÌNH SỬA CHỮA","writes_blocked":"Không ghi MES · không phát lại cảnh báo"}}

STATIONS={
"mod_manu_pda_loading":("扫码上料","Material Loading","Nạp vật liệu"),"mod_manu_aoi":("AOI质量","A-O-I Quality","Chất lượng A-O-I"),"mod_manu_ict":("ICT测试","I-C-T Test","Kiểm tra I-C-T"),"mod_manu_fct":("FCT测试","F-C-T Test","Kiểm tra F-C-T"),"mod_manu_depanel":("PCBA分板","PCBA Depanel","Tách bảng PCBA"),"mod_manu_case_binding":("外壳绑码","Case Binding","Liên kết vỏ"),"mod_manu_assembly_ate":("组装ATE","Assembly A-T-E","A-T-E lắp ráp"),"mod_manu_supersonic":("超声波/外观","Ultrasonic / Visual","Siêu âm / Ngoại quan"),"mod_manu_aging":("成品老化","Product Aging","Lão hóa sản phẩm"),"mod_manu_hivolt_ate":("高压ATE","High-voltage A-T-E","A-T-E cao áp"),"mod_manu_packing_ate":("包装ATE","Packing A-T-E","A-T-E đóng gói"),"mod_manu_outer_box_binding":("外箱绑码","Outer-box Binding","Liên kết thùng"),"mod_manu_pallet_binding":("栈板绑码","Pallet Binding","Liên kết pallet")}

def t(locale,key): return TEXT.get(locale,TEXT["en"]).get(key,TEXT["en"].get(key,key))
def station_name(locale,code):
    names=STATIONS.get(code,(code,code,code)); return names[{"zh":0,"en":1,"vi":2}.get(locale,1)]
def validate():
    baseline=set(TEXT["en"])
    for locale in LOCALES:
        missing=baseline-set(TEXT[locale]); extra=set(TEXT[locale])-baseline
        if missing or extra: raise ValueError(f"{locale} dictionary mismatch: missing={missing}, extra={extra}")
    for code,names in STATIONS.items():
        if len(names)!=3 or not all(names): raise ValueError("Incomplete station translation: "+code)
    return True
