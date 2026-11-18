# -*- coding: utf-8 -*-
"""
FCT station - ATE测试质量监控工位
功能：
1. 轮询ATE Excel报表目录，检测NG SN
2. NG时锁定ATE设备(pssuspend)，等待MES解锁run
3. SN三重查重：内存池→SQLite→NG注册表
4. 本地SQLite记录全部SN + NG SN，5年追溯
5. Tkinter GUI显示实时状态
"""

import os, sys, json, time, threading, subprocess, sqlite3, urllib.request, urllib.error, urllib.parse, wave, struct, math, ctypes, tempfile, re, socket, queue, winreg, asyncio
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
from openpyxl import load_workbook
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from station_data_sync import mes_scan_gate

# WebSocket 服务器
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[ATE质量中心] websockets not installed. WebSocket broadcast disabled. Run: pip install websockets")
import tkinter as tk
from tkinter import ttk, messagebox

# ===== Trilingual Support (zh/vi/en) =====
_CURRENT_LANG = 'zh'


def _T(key):
    """Translate key to current language"""
    d = LANG.get(_CURRENT_LANG, LANG['zh'])
    return d.get(key, key)


def _set_lang(lang):
    global _CURRENT_LANG
    _CURRENT_LANG = lang

LANG = {
    'zh': {
        'title': '包装工位',
        'monitor_tab': ' 实时监控 ',
        'resources_tab': ' 资源查看 ',
        'status_label': '状态',
        'running': '运行中',
        'stopped': '停止',
        'locked': '已锁定',
        'device_label': '设备',
        'unlocked': '未锁定',
        'pass_label': '今日合格',
        'fail_label': '今日不良',
        'dup_label': '重码',
        'total_label': '合计',
        'file_label': '当前文件',
        'waiting': '等待中...',
        'check_title': 'SN查重状态（6项）',
        'scan_log': '入箱记录',
        'pool_sn': 'SN池',
        'pool_ng': 'NG池',
        'registry_sn': 'SN注册表',
        'registry_ng': 'NG注册表',
        'btn_delete_sn': '删除SN池',
        'btn_delete_ng': '删除NG池',
        'btn_clear_sn': '清空SN库',
        'btn_clear_ng': '清空NG库',
        'ng_alarm_title': '不良品警告',
        'dup_alarm_title': '重码警告',
        'found_ng': '发现不良品！',
        'found_dup': '发现重复编码！',
        'source_ng_pool': '来源: [NG池]',
        'source_excel': '来源: [Excel检测]',
        'source_pool': '来源: [Pool]',
        'source_local': '来源: [Local]',
        'source_mes': '来源: [MES]',
        'ban_ng': '禁止不良品离开本站！',
        'ban_dup': '禁止重复品离开本站！',
        'admin_label': '管理员:',
        'password_label': '密码:',
        'confirm_btn': '确认处理',
        'bypass_btn': '快速确认',
        'auth_failed': '管理员认证失败',
        'current_sn': '最新',
        'pool_status': 'SN池: 全部{total} | 不良{ng} | 重码{dup}',
        'col_sn': 'SN',
        'col_result': '结果',
        'col_channel': '通道',
        'col_errorcode': '错误码',
        'col_time': '时间',
        'col_station_ip': '工位IP',
        'col_sp': 'SN Pool',
        'col_sl': 'SN Local',
        'col_sm': 'SN MES',
        'col_np': 'NG Pool',
        'col_nl': 'NG Local',
        'col_nm': 'NG MES',
        'lang_zh': '中文',
        'lang_vi': 'Tiếng Việt',
        'lang_en': 'English',
        'alarm_closed': '告警已关闭',
        'mes_on': 'MES: ON',
        'mes_off': 'MES: OFF',
        'source_layer': '来源: [{layer}]',
        'simulate_scan': '📥 扫码',
        'simulate_ng': '🔴 模拟NG',
        'simulate_dup': '🔁 模拟重码',
        'simulate_gen': '🎲 生成SN',
        'simulate_clear': '🧹 清空池',
        'simulate_sn_hint': '输入SN或点击生成',
        'instructions_tab': ' 操作说明 ',
        'startup_tab': ' 开机流程 ',
        'channel_full': '通道: {channel}',
        'errorcode_full': '错误码: {errorcode}',
        # ---- Instruction tab content ----
        'inst_sec1_title': '1. 扫码检测流程',
        'inst_sec1_content': [
            '• 使用扫码枪扫描产品SN条码',
            '• 系统按优先级依次执行以下检测，任一命中即阻断：',
            '',
            '  优先级1 🔴 NG Pool检测（内存，立即）',
            '    - 检查当前Excel中的不良SN内存池',
            '    - 命中 → 锁定ATE + 语音报警 + 弹窗',
            '',
            '  优先级2 🟡 DUP Pool检测（内存，立即）',
            '    - 检查当前Excel中是否已有该SN',
            '    - 命中 → 重码报警',
            '',
            '  优先级3 🔴 MES NG历史查询（网络，后台）',
            '    - 查询MES ng_registry表',
            '    - 命中 → 锁定ATE + 语音报警',
            '',
            '  优先级4 🟡 本地SQLite查重（磁盘，后台）',
            '    - 检查本地数据库sn_records表',
            '    - 命中 → 重码报警',
            '',
            '  优先级5 🟡 MES数据库查重（网络，后台）',
            '    - 查询MES product表',
            '    - 命中 → 重码报警',
            '',
            '• 以上全部通过后 → SN加入内存池+SQLite，状态记为PASS',
            '• 所有检查均不阻塞扫码枪，后台检查不影响下一SN扫描',
        ],
        'inst_sec2_title': '2. NG(不良品)处理',
        'inst_sec2_content': [
            '• 当检测到NG时，系统自动执行：',
            '    ① 禁用USB扫码枪（防止误扫）',
            '    ② 锁定ATE设备（pssuspend暂停ATE进程）',
            '    ③ 弹出不良品警告窗口',
            '    ④ 播放越南语语音警报',
            '    ⑤ 记录NG信息到本地NG池和SQLite',
            '• 管理员需在弹窗中输入密码确认处理方式：',
            '    - 复测：产品重新测试',
            '    - 垃圾桶：产品报废',
            '    - 拿去向产线：退回产线处理',
        ],
        'inst_sec3_title': '3. 重码(Duplicate)处理',
        'inst_sec3_content': [
            '• 当检测到重复SN时，系统自动执行：',
            '    ① 弹出重码警告窗口',
            '    ② 播放越南语语音警报',
            '    ③ 锁定ATE设备',
            '    ④ 记录重码信息',
            '• 管理员需在弹窗中确认处理方式',
        ],
        'inst_sec4_title': '4. ATE设备操作流程',
        'inst_sec4_content': [
            '▸ 开机流程：',
            '    ① 打开ATE测试设备电源（ATS231010）',
            '    ② 启动ATE测试软件（ats231010.exe）',
            '    ③ 确认软件连接正常，通道状态显示就绪',
            '    ④ 打开本质量监控系统（ATE质量中心越南）',
            '    ⑤ 确认状态栏显示「运行中」，Excel文件路径正确',
            '',
            '▸ 测试操作：',
            '    ① 将产品放入ATE测试治具',
            '    ② 测试软件自动运行测试',
            '    ③ 测试完成后扫码枪扫描产品SN',
            '    ④ 系统自动检测NG/重码，通过后记录入库',
            '    ⑤ 合格产品放行至下一工站',
            '',
            '▸ 异常处理：',
            '    - 设备锁定时，管理员通过弹窗认证后解锁',
            '    - 扫码无反应时，检查USB扫码枪连接',
            '    - 软件卡死时，在资源管理器重启ats231010.exe',
            '    - 系统误报时，联系品管主管处理',
            '',
            '▸ 关机流程：',
            '    ① 确认所有产品测试完成',
            '    ② 关闭ATE质量中心越南系统',
            '    ③ 关闭ATE测试软件',
            '    ④ 关闭ATE设备电源',
        ],
        'inst_sec5_title': '5. 日常点检项目',
        'inst_sec5_content': [
            '  点检时间：每日开班前',
            '',
            '  □ 设备状态检查：',
            '    □ ATE测试设备电源正常',
            '    □ ats231010.exe 软件正常启动',
            '    □ 所有测试通道状态就绪',
            '    □ 测试治具无损坏，探针接触良好',
            '',
            '  □ 系统状态检查：',
            '    □ ATE质量中心已启动，状态显示「运行中」',
            '    □ Excel监控文件夹路径正确',
            '    □ 昨日测试数据正常存档',
            '    □ 系统时间与北京时间一致',
            '',
            '  □ 扫码设备检查：',
            '    □ USB扫码枪连接正常',
            '    □ 扫码枪指示灯正常',
            '    □ 扫描SN能正常识别',
            '    □ TCP端口(1003)正常监听',
            '',
            '  □ 报警系统检查：',
            '    □ 音箱电源开启，音量正常',
            '    □ 语音播报功能正常',
            '    □ 不良品弹窗能正常弹出',
            '    □ 警笛声正常播放',
            '',
            '  □ 网络与数据检查：',
            '    □ MES后端连接正常（http://192.168.6.155:8080）',
            '    □ 本地SQLite数据库正常',
            '    □ 数据文件夹可正常读写',
            '',
            '  ✅ 全部点检完成后，确认无误方可开始生产',
        ],
        'inst_sec6_title': '6. 每日重置',
        'inst_sec6_content': [
            '• 每天12:00自动重置SN池、NG池和统计数据',
            '• 新的Excel文件自动开始监控',
            '• Excel表头自动识别，无需手动配置数据起始行',
        ],
        'inst_sec7_title': '7. 注意事项',
        'inst_sec7_content': [
            '⚠ 确保Excel文件夹路径正确（当前路径在下方显示）',
            '⚠ 请勿手动删除正在监控的Excel文件',
            '⚠ 设备锁定后必须由管理员在弹窗中确认解锁',
            '⚠ 语音提示为越南语，请确保音箱正常工作',
            '⚠ 系统自动检测Excel数据起始行，无需修改配置文件',
        ],
        'inst_sec8_title': '8. 当前配置',
        # ---- Startup tab content ----
        'start_step1_title': '步骤一：ATE测试设备通电',
        'start_step1_content': ['1. 确认ATE设备电源线连接正常', '2. 打开ATE设备总电源开关', '3. 等待设备指示灯亮起（绿色）', '4. 确认设备风扇运转正常'],
        'start_step2_title': '步骤二：启动ATE测试软件',
        'start_step2_content': ['1. 在桌面双击 ats231010.exe 图标', '2. 等待软件加载完成（约10-30秒）', '3. 确认软件界面显示所有通道就绪', '4. 检查各通道电压/电流读数在正常范围'],
        'start_step3_title': '步骤三：启动ATE质量中心系统',
        'start_step3_content': ['1. 双击桌面 ATE质量中心越南 图标', '2. 等待系统加载完成', '3. 确认标题栏显示「运行中」状态', '4. 检查底部状态栏信息：', '   • 数据文件夹路径是否正确', '   • MES连接状态是否正常', '   • 本地API端口 3000 是否监听'],
        'start_step4_title': '步骤四：扫码设备检查',
        'start_step4_content': ['1. 确认USB扫码枪已插入电脑', '2. 确认扫码枪红灯/蓝灯正常亮起', '3. 扫描一个测试SN，检查是否正常识别', '4. 确认日志区显示扫描记录', '5. 检查TCP端口 1003 是否正常监听'],
        'start_step5_title': '步骤五：报警系统测试',
        'start_step5_content': ['1. 确认音箱电源已开启，音量适中', '2. 点击「模拟NG」按钮测试报警功能', '3. 确认以下报警动作正常：', '   • 越南语语音播报（Phat hien san pham loi）', '   • 警笛声播放', '   • 不良品弹窗弹出', '   • ATE设备锁定', '4. 管理员确认解锁后ATE恢复正常'],
        'start_step6_title': '步骤六：MES连接确认',
        'start_step6_content': ['1. 确认MES后端服务运行中', '2. 检查资源查看标签页MES状态为 ON', '3. 扫描一个测试SN确认MES查重正常', '4. 确认数据能正确写入本地SQLite'],
        'start_done_text': '☐ 已完成步骤{step}',
        'start_final_msg': '✅ 全部步骤完成，可以开始生产',
        'start_note1': '📌 如任何步骤异常，请立即通知设备管理员或品管主管',
        'start_note2': '📌 点检表请记录在「日常点检表」文档中，每日归档',
        # ---- Tooltips (zh) ----
        'tt_sim_scan': '模拟扫码 - 生成测试SN并触发扫码流程',
        'tt_sim_pass': '模拟合格品 - 生成测试SN走完整6层查重流程',
        'tt_sim_ng': '模拟NG - 注入测试SN到NG池，触发完整5重报警',
        'tt_sim_dup': '模拟重码 - 注入测试SN到SN池，触发重码告警',
        'tt_sim_clear': '清空所有数据 - 删除内存池 + SQLite 全部记录',
        'tt_sim_entry': 'SN测试输入框 - 输入SN或点击生成测试',
        'tt_btn_delete_sn': '删除SN池 - 清空内存中所有SN（不删SQLite）',
        'tt_btn_delete_ng': '删除NG池 - 清空内存中所有NG（不删SQLite）',
        'tt_btn_clear_sn': '⚠ 清空SN库 - 永久删除SQLite中所有SN记录',
        'tt_btn_clear_ng': '⚠ 清空NG库 - 永久删除5年NG追溯记录',
        'tt_mes_toggle': 'MES查重开关 - 关闭后只查内存池（速度更快但漏检）',
        'tt_confirm_btn': '确认 - 输入管理员账号密码后解锁ATE设备',
        'tt_bypass_btn': '快速确认 - 跳过密码直接解锁ATE（应急用）',
        'tt_admin_user': '管理员账号',
        'tt_admin_pass': '管理员密码',
        'tt_method_retest': '复测 - 产品重新测试，成功后从NG池移除',
        'tt_method_trash': '垃圾桶 - 产品报废，永久禁止入MES',
        'tt_method_return': '拿去向产线 - 退回产线处理',
        'tt_lang_combo': '界面语言 - 切换中文/越南语/English',
        # ---- Pallet Binding ----
        'binding_tab': ' 栈板绑码 ',
        'binding_title': '栈板绑码管理',
        'binding_info': '扫描绑码或输入绑码进行绑定/查询',
        'binding_code': '绑码:',
        'binding_pallet_id': '托盘ID:',
        'binding_carton_count': '箱数:',
        'binding_sn_count': 'SN总数:',
        'binding_status': '状态:',
        'binding_time': '时间:',
        'binding_success': '绑定成功',
        'binding_failed': '绑定失败',
        'binding_not_found': '未找到绑码记录',
        'binding_already_bound': '该绑码已使用',
        'binding_pending': '待绑定',
        'binding_verify_ok': '验码通过',
        'binding_verify_fail': '验码失败',
        'btn_bind': '绑定',
        'btn_unbind': '解绑',
        'btn_verify_binding': '验码',
        'btn_export_binding': '导出',
        'btn_refresh_binding': '刷新',
        'btn_print_binding': '打印标签',
        'btn_scan_binding': '扫绑码',
        'btn_create_binding': '生成绑码',
        'col_binding_code': '绑码',
        'col_pallet_id_bind': '托盘ID',
        'col_carton_count_bind': '箱数',
        'col_sn_total': 'SN总数',
        'col_binding_time': '时间',
        'col_binding_status': '状态',
        'binding_history': '绑码记录',
        'unbind_confirm': '确定解绑此托盘？',
        'unbind_title': '解绑确认',
        'binding_confirm_title': '绑定确认',
        'binding_confirm_msg': '确定绑定此托盘？',
        'btn_confirm_bind': '确认绑定',
        'binding_already': '已绑定',
        'unbind_success': '解绑成功',
        'export_success': '导出成功',
        'export_failed': '导出失败',
        'workorder': '工单',
        'no_workorder': '未选择工单',
        'btn_select_wo': '选定工单',
        'btn_manual_wo': '手动输入',
    },
    'vi': {
        'title': '包装工位',
        'monitor_tab': ' Giám sát ',
        'resources_tab': ' Tài nguyên ',
        'status_label': 'Trạng thái',
        'running': 'Đang chạy',
        'stopped': 'Dừng',
        'locked': 'Đã khóa',
        'device_label': 'Thiết bị',
        'unlocked': 'Chưa khóa',
        'pass_label': 'Hôm nay Đạt',
        'fail_label': 'Hôm nay Lỗi',
        'dup_label': 'Trùng',
        'total_label': 'Tổng',
        'file_label': 'Tệp hiện tại',
        'waiting': 'Đang chờ...',
        'check_title': 'Kiểm tra trùng SN (6 mục)',
        'scan_log': 'Nhật ký đóng gói',
        'pool_sn': 'Kho SN',
        'pool_ng': 'Kho NG',
        'registry_sn': 'Sổ SN',
        'registry_ng': 'Sổ NG',
        'btn_delete_sn': 'Xóa kho SN',
        'btn_delete_ng': 'Xóa kho NG',
        'btn_clear_sn': 'Xóa sổ SN',
        'btn_clear_ng': 'Xóa sổ NG',
        'ng_alarm_title': 'Cảnh báo Lỗi',
        'dup_alarm_title': 'Cảnh báo Trùng',
        'found_ng': 'Phát hiện Sản phẩm Lỗi!',
        'found_dup': 'Phát hiện Mã trùng!',
        'source_ng_pool': 'Nguồn: [Kho NG]',
        'source_excel': 'Nguồn: [Excel]',
        'source_pool': 'Nguồn: [Pool]',
        'source_local': 'Nguồn: [Local]',
        'source_mes': 'Nguồn: [MES]',
        'ban_ng': 'Cấm SP lỗi rời trạm!',
        'ban_dup': 'Cấm mã trùng rời trạm!',
        'admin_label': 'Quản trị:',
        'password_label': 'Mật khẩu:',
        'confirm_btn': 'Xác nhận',
        'bypass_btn': 'Bỏ qua',
        'auth_failed': 'Xác thực thất bại',
        'current_sn': 'Mới nhất',
        'pool_status': 'Kho SN: Tổng{total} | Lỗi{ng} | Trùng{dup}',
        'col_sn': 'SN',
        'col_result': 'Kết quả',
        'col_channel': 'Kênh',
        'col_errorcode': 'Mã lỗi',
        'col_time': 'Thời gian',
        'col_station_ip': 'IP Trạm',
        'col_sp': 'Kho SN',
        'col_sl': 'SQL SN',
        'col_sm': 'MES SN',
        'col_np': 'Kho NG',
        'col_nl': 'SQL NG',
        'col_nm': 'MES NG',
        'lang_zh': '中文',
        'lang_vi': 'Tiếng Việt',
        'lang_en': 'English',
        'alarm_closed': 'Đã đóng cảnh báo',
        'mes_on': 'MES: BẬT',
        'mes_off': 'MES: TẮT',
        'source_layer': 'Nguồn: [{layer}]',
        'channel_full': 'Kênh: {channel}',
        'errorcode_full': 'Mã lỗi: {errorcode}',
        'instructions_tab': ' Hướng dẫn ',
        'startup_tab': ' Quy trình khởi động ',
        'simulate_scan': '📥 Quét',
        'simulate_ng': '🔴 Mô phỏng Lỗi',
        'simulate_dup': '🔁 Mô phỏng Trùng',
        'simulate_gen': '🎲 Tạo SN',
        'simulate_clear': '🧹 Xóa bộ nhớ',
        'simulate_sn_hint': 'Nhập SN hoặc bấm tạo',
        # ---- Instruction tab content (Tiếng Việt) ----
        'inst_sec1_title': '1. Quy trình quét mã',
        'inst_sec1_content': [
            '• Dùng máy quét để quét mã SN sản phẩm',
            '• Hệ thống kiểm tra theo thứ tự ưu tiên, bất kỳ mục nào trúng sẽ chặn:',
            '',
            '  Ưu tiên 1 🔴 Kiểm tra NG Pool (RAM, tức thì)',
            '    - Kiểm tra bộ nhớ SN lỗi trong Excel hiện tại',
            '    - Trúng → Khóa ATE + Báo động + Cửa sổ cảnh báo',
            '',
            '  Ưu tiên 2 🟡 Kiểm tra DUP Pool (RAM, tức thì)',
            '    - Kiểm tra SN đã tồn tại trong Excel hiện tại chưa',
            '    - Trúng → Cảnh báo trùng',
            '',
            '  Ưu tiên 3 🔴 Tra cứu NG MES (Mạng, nền)',
            '    - Tra bảng ng_registry trên MES',
            '    - Trúng → Khóa ATE + Báo động',
            '',
            '  Ưu tiên 4 🟡 Kiểm tra trùng SQLite (Đĩa, nền)',
            '    - Kiểm tra bảng sn_records trong CSDL địa phương',
            '    - Trúng → Cảnh báo trùng',
            '',
            '  Ưu tiên 5 🟡 Kiểm tra trùng MES (Mạng, nền)',
            '    - Tra bảng product trên MES',
            '    - Trúng → Cảnh báo trùng',
            '',
            '• Qua hết tất cả → SN vào Pool RAM + SQLite, ghi nhận PASS',
            '• Tất cả kiểm tra không chặn máy quét, nền không ảnh hưởng SN kế tiếp',
        ],
        'inst_sec2_title': '2. Xử lý NG (Sản phẩm lỗi)',
        'inst_sec2_content': [
            '• Khi phát hiện NG, hệ thống tự động:',
            '    ① Vô hiệu hóa máy quét USB (tránh quét nhầm)',
            '    ② Khóa thiết bị ATE (pssuspend tạm dừng ATE)',
            '    ③ Hiện cửa sổ cảnh báo sản phẩm lỗi',
            '    ④ Phát báo động tiếng Việt',
            '    ⑤ Ghi nhận NG vào bộ nhớ NG và SQLite',
            '• Quản trị viên nhập mật khẩu trong cửa sổ để xác nhận:',
            '    - Kiểm tra lại: Sản phẩm kiểm tra lại',
            '    - Thùng rác: Sản phẩm bỏ đi',
            '    - Đưa về dây chuyền: Trả lại dây chuyền xử lý',
        ],
        'inst_sec3_title': '3. Xử lý trùng (Duplicate)',
        'inst_sec3_content': [
            '• Khi phát hiện mã trùng, hệ thống tự động:',
            '    ① Hiện cửa sổ cảnh báo trùng',
            '    ② Phát báo động tiếng Việt',
            '    ③ Khóa thiết bị ATE',
            '    ④ Ghi nhận thông tin trùng',
            '• Quản trị viên xác nhận trong cửa sổ',
        ],
        'inst_sec4_title': '4. Quy trình vận hành ATE',
        'inst_sec4_content': [
            '▸ Khởi động:',
            '    ① Bật nguồn thiết bị kiểm tra ATE (ATS231010)',
            '    ② Khởi động phần mềm ATE (ats231010.exe)',
            '    ③ Xác nhận kết nối phần mềm bình thường, kênh sẵn sàng',
            '    ④ Mở hệ thống giám sát chất lượng (ATE质量中心越南)',
            '    ⑤ Xác nhận trạng thái «Đang chạy», đường dẫn Excel đúng',
            '',
            '▸ Kiểm tra:',
            '    ① Đặt sản phẩm vào đồ gá ATE',
            '    ② Phần mềm tự động chạy kiểm tra',
            '    ③ Sau kiểm tra, quét mã SN sản phẩm',
            '    ④ Hệ thống tự động phát hiện NG/trùng, nếu qua thì ghi nhận',
            '    ⑤ Sản phẩm đạt chuyển sang trạm tiếp theo',
            '',
            '▸ Xử lý bất thường:',
            '    - Thiết bị bị khóa, quản trị viên xác nhận trong cửa sổ để mở khóa',
            '    - Quét không phản hồi, kiểm tra kết nối máy quét USB',
            '    - Phần mềm treo, khởi động lại ats231010.exe trong Task Manager',
            '    - Báo động sai, liên hệ quản lý phẩm chất',
            '',
            '▸ Tắt máy:',
            '    ① Xác nhận tất cả sản phẩm đã kiểm tra xong',
            '    ② Đóng hệ thống ATE质量中心越南',
            '    ③ Đóng phần mềm ATE',
            '    ④ Tắt nguồn thiết bị ATE',
        ],
        'inst_sec5_title': '5. Điểm danh hàng ngày',
        'inst_sec5_content': [
            '  Thời gian điểm danh: Trước mỗi ca làm việc',
            '',
            '  □ Kiểm tra thiết bị:',
            '    □ Nguồn thiết bị ATE bình thường',
            '    □ ats231010.exe khởi động bình thường',
            '    □ Tất cả kênh kiểm tra sẵn sàng',
            '    □ Đồ gá không hư hỏng, kim tiếp xúc tốt',
            '',
            '  □ Kiểm tra hệ thống:',
            '    □ ATE质量中心 đã khởi động, trạng thái «Đang chạy»',
            '    □ Đường dẫn thư mục Excel đúng',
            '    □ Dữ liệu hôm qua đã lưu bình thường',
            '    □ Giờ hệ thống khớp với giờ Việt Nam',
            '',
            '  □ Kiểm tra máy quét:',
            '    □ Máy quét USB kết nối bình thường',
            '    □ Đèn máy quét sáng bình thường',
            '    □ Quét SN nhận dạng bình thường',
            '    □ Cổng TCP (1003) đang lắng nghe',
            '',
            '  □ Kiểm tra báo động:',
            '    □ Loa bật nguồn, âm lượng bình thường',
            '    □ Chức năng phát giọng nói bình thường',
            '    □ Cửa sổ cảnh báo sản phẩm lỗi hiện ra',
            '    □ Còi báo phát bình thường',
            '',
            '  □ Kiểm tra mạng và dữ liệu:',
            '    □ Kết nối MES bình thường (http://192.168.6.155:8080)',
            '    □ CSDL SQLite địa phương bình thường',
            '    □ Thư mục dữ liệu đọc ghi bình thường',
            '',
            '  ✅ Sau khi điểm danh xong, xác nhận không lỗi mới bắt đầu sản xuất',
        ],
        'inst_sec6_title': '6. Đặt lại hàng ngày',
        'inst_sec6_content': [
            '• Tự động đặt lại SN Pool, NG Pool và thống kê lúc 12:00 hàng ngày',
            '• File Excel mới tự động được giám sát',
            '• Tiêu đề Excel tự động nhận dạng, không cần cấu hình thủ công',
        ],
        'inst_sec7_title': '7. Lưu ý',
        'inst_sec7_content': [
            '⚠ Đảm bảo đường dẫn thư mục Excel đúng (hiển thị bên dưới)',
            '⚠ Không xóa thủ công file Excel đang giám sát',
            '⚠ Thiết bị khóa phải do quản trị viên xác nhận mở khóa',
            '⚠ Giọng nói là tiếng Việt, đảm bảo loa hoạt động bình thường',
            '⚠ Hệ thống tự động nhận dạng dòng dữ liệu Excel, không cần sửa cấu hình',
        ],
        'inst_sec8_title': '8. Cấu hình hiện tại',
        # ---- Startup tab content (Tiếng Việt) ----
        'start_step1_title': 'Bước 1: Cấp nguồn thiết bị ATE',
        'start_step1_content': ['1. Xác nhận dây nguồn thiết bị ATE kết nối bình thường', '2. Bật công tắc nguồn chính của thiết bị ATE', '3. Chờ đèn thiết bị sáng (màu xanh)', '4. Xác nhận quạt thiết bị chạy bình thường'],
        'start_step2_title': 'Bước 2: Khởi động phần mềm ATE',
        'start_step2_content': ['1. Nhấp đúp biểu tượng ats231010.exe trên desktop', '2. Chờ phần mềm tải xong (khoảng 10-30 giây)', '3. Xác nhận màn hình hiển thị tất cả kênh sẵn sàng', '4. Kiểm tra điện áp/dòng điện từng kênh trong phạm vi bình thường'],
        'start_step3_title': 'Bước 3: Khởi động hệ thống ATE质量中心',
        'start_step3_content': ['1. Nhấp đúp biểu tượng ATE质量中心越南 trên desktop', '2. Chờ hệ thống tải xong', '3. Xác nhận thanh tiêu đề hiển thị trạng thái «Đang chạy»', '4. Kiểm tra thanh trạng thái dưới cùng:', '   • Đường dẫn thư mục dữ liệu có đúng không', '   • Kết nối MES có bình thường không', '   • API cổng 3000 có đang lắng nghe không'],
        'start_step4_title': 'Bước 4: Kiểm tra máy quét',
        'start_step4_content': ['1. Xác nhận máy quét USB đã cắm vào máy tính', '2. Xác nhận đèn máy quét đỏ/xanh sáng bình thường', '3. Quét một SN kiểm tra, xem nhận dạng bình thường không', '4. Xác nhận khu vực nhật ký hiển thị bản ghi quét', '5. Kiểm tra cổng TCP 1003 đang lắng nghe'],
        'start_step5_title': 'Bước 5: Kiểm tra hệ thống báo động',
        'start_step5_content': ['1. Xác nhận loa bật nguồn, âm lượng phù hợp', '2. Nhấn nút «Mô phỏng Lỗi» để kiểm tra báo động', '3. Xác nhận các hành động báo động bình thường:', '   • Phát giọng nói tiếng Việt (Phát hiện sản phẩm lỗi)', '   • Còi báo phát', '   • Cửa sổ cảnh báo sản phẩm lỗi hiện ra', '   • Thiết bị ATE bị khóa', '4. Quản trị viên xác nhận mở khóa, ATE trở lại bình thường'],
        'start_step6_title': 'Bước 6: Xác nhận kết nối MES',
        'start_step6_content': ['1. Xác nhận dịch vụ MES đang chạy', '2. Kiểm tra tab Tài nguyên, trạng thái MES là ON', '3. Quét SN kiểm tra xác nhận dò trùng MES bình thường', '4. Xác nhận dữ liệu ghi vào SQLite địa phương bình thường'],
        'start_done_text': '☐ Đã hoàn thành bước {step}',
        'start_final_msg': '✅ Tất cả các bước hoàn thành, có thể bắt đầu sản xuất',
        'start_note1': '📌 Nếu bất kỳ bước nào bất thường, báo ngay quản lý thiết bị hoặc quản lý phẩm chất',
        'start_note2': '📌 Phiếu điểm danh ghi vào tài liệu «Phiếu điểm danh hàng ngày», lưu trữ hàng ngày',
        # ---- Tooltips (vi) ----
        'tt_sim_scan': 'Mô phỏng quét - Tạo SN thử và kích hoạt quy trình quét',
        'tt_sim_pass': 'Mô phỏng đạt - Tạo SN thử đi qua 6 lớp kiểm tra trùng',
        'tt_sim_ng': 'Mô phỏng NG - Tiêm SN thử vào kho NG, kích hoạt 5 báo động',
        'tt_sim_dup': 'Mô phỏng trùng - Tiêm SN thử vào kho SN, kích hoạt cảnh báo trùng',
        'tt_sim_clear': 'Xóa tất cả dữ liệu - Xóa bộ nhớ + toàn bộ SQLite',
        'tt_sim_entry': 'Ô nhập SN thử - Nhập SN hoặc bấm tạo',
        'tt_btn_delete_sn': 'Xóa kho SN - Xóa tất cả SN trong bộ nhớ (không xóa SQLite)',
        'tt_btn_delete_ng': 'Xóa kho NG - Xóa tất cả NG trong bộ nhớ (không xóa SQLite)',
        'tt_btn_clear_sn': '⚠ Xóa sổ SN - Xóa vĩnh viễn tất cả SN trong SQLite',
        'tt_btn_clear_ng': '⚠ Xóa sổ NG - Xóa vĩnh viễn bản ghi NG 5 năm',
        'tt_mes_toggle': 'Công tắc MES - Tắt chỉ kiểm bộ nhớ (nhanh hơn nhưng dễ sót)',
        'tt_confirm_btn': 'Xác nhận - Nhập mật khẩu quản trị để mở khóa ATE',
        'tt_bypass_btn': 'Bỏ qua nhanh - Mở khóa ATE không cần mật khẩu (khẩn cấp)',
        'tt_admin_user': 'Tài khoản quản trị',
        'tt_admin_pass': 'Mật khẩu quản trị',
        'tt_method_retest': 'Kiểm tra lại - Sản phẩm kiểm tra lại, xóa khỏi kho NG nếu đạt',
        'tt_method_trash': 'Thùng rác - Bỏ đi, cấm vĩnh viễn vào MES',
        'tt_method_return': 'Đưa về dây chuyền - Trả lại dây chuyền xử lý',
        'tt_lang_combo': 'Ngôn ngữ giao diện - Chuyển 中文/Tiếng Việt/English',
        # ---- Pallet Binding ----
        'binding_tab': ' Mã Pallet ',
        'binding_title': 'Quản lý Mã Pallet',
        'binding_info': 'Quét mã pallet hoặc nhập mã để ràng buộc/xác minh',
        'binding_code': 'Mã:',
        'binding_pallet_id': 'Mã Pallet:',
        'binding_carton_count': 'SL Thùng:',
        'binding_sn_count': 'Tổng SN:',
        'binding_status': 'Trạng thái:',
        'binding_time': 'Thời gian:',
        'binding_success': 'Ràng buộc thành công',
        'binding_failed': 'Ràng buộc thất bại',
        'binding_not_found': 'Không tìm thấy mã',
        'binding_already_bound': 'Mã đã được sử dụng',
        'binding_pending': 'Chờ ràng buộc',
        'binding_verify_ok': 'Xác minh OK',
        'binding_verify_fail': 'Xác minh thất bại',
        'btn_bind': 'Ràng buộc',
        'btn_unbind': 'Hủy ràng buộc',
        'btn_verify_binding': 'Xác minh',
        'btn_export_binding': 'Xuất',
        'btn_refresh_binding': 'Làm mới',
        'btn_print_binding': 'In nhãn',
        'btn_scan_binding': 'Quét mã',
        'btn_create_binding': 'Tạo mã',
        'col_binding_code': 'Mã Pallet',
        'col_pallet_id_bind': 'Mã Pallet',
        'col_carton_count_bind': 'SL Thùng',
        'col_sn_total': 'Tổng SN',
        'col_binding_time': 'Thời gian',
        'col_binding_status': 'Trạng thái',
        'binding_history': 'Lịch sử Mã Pallet',
        'unbind_confirm': 'Xác nhận hủy ràng buộc?',
        'unbind_title': 'Xác nhận Hủy',
        'binding_confirm_title': 'Xác nhận Ràng buộc',
        'binding_confirm_msg': 'Xác nhận ràng buộc pallet này?',
        'btn_confirm_bind': 'Xác nhận',
        'binding_already': 'Đã ràng buộc',
        'unbind_success': 'Hủy thành công',
        'export_success': 'Xuất thành công',
        'export_failed': 'Xuất thất bại',
        'workorder': 'Lệnh SX',
        'no_workorder': 'Chưa chọn lệnh SX',
        'btn_select_wo': 'Chọn lệnh SX',
        'btn_manual_wo': 'Nhập tay',
    },
    'en': {
        'title': '包装工位',
        'monitor_tab': ' Monitor ',
        'resources_tab': ' Resources ',
        'status_label': 'Status',
        'running': 'Running',
        'stopped': 'Stopped',
        'locked': 'Locked',
        'device_label': 'Device',
        'unlocked': 'Unlocked',
        'pass_label': 'Today Pass',
        'fail_label': 'Today Fail',
        'dup_label': 'Dup',
        'total_label': 'Total',
        'file_label': 'Current File',
        'waiting': 'Waiting...',
        'check_title': 'SN Dup Check (6 items)',
        'scan_log': 'Packing Log',
        'pool_sn': 'SN Pool',
        'pool_ng': 'NG Pool',
        'registry_sn': 'SN Registry',
        'registry_ng': 'NG Registry',
        'btn_delete_sn': 'Delete SN Pool',
        'btn_delete_ng': 'Delete NG Pool',
        'btn_clear_sn': 'Clear SN DB',
        'btn_clear_ng': 'Clear NG DB',
        'ng_alarm_title': 'NG Warning',
        'dup_alarm_title': 'Dup Warning',
        'found_ng': 'Defective Product Found!',
        'found_dup': 'Duplicate Code Found!',
        'source_ng_pool': 'Source: [NG Pool]',
        'source_excel': 'Source: [Excel]',
        'source_pool': 'Source: [Pool]',
        'source_local': 'Source: [Local]',
        'source_mes': 'Source: [MES]',
        'ban_ng': 'NG product must NOT leave!',
        'ban_dup': 'Duplicate must NOT leave!',
        'admin_label': 'Admin:',
        'password_label': 'Password:',
        'confirm_btn': 'Confirm',
        'bypass_btn': 'Quick Auth',
        'auth_failed': 'Auth Failed',
        'current_sn': 'Latest',
        'pool_status': 'SN Pool: Total{total} | Fail{ng} | Dup{dup}',
        'col_sn': 'SN',
        'col_result': 'Result',
        'col_channel': 'Channel',
        'col_errorcode': 'Error',
        'col_time': 'Time',
        'col_station_ip': 'Station IP',
        'col_sp': 'SN Pool',
        'col_sl': 'SN Local',
        'col_sm': 'SN MES',
        'col_np': 'NG Pool',
        'col_nl': 'NG Local',
        'col_nm': 'NG MES',
        'lang_zh': '中文',
        'lang_vi': 'Tiếng Việt',
        'lang_en': 'English',
        'alarm_closed': 'Alarm Closed',
        'mes_on': 'MES: ON',
        'mes_off': 'MES: OFF',
        'source_layer': 'Source: [{layer}]',
        'channel_full': 'Channel: {channel}',
        'errorcode_full': 'Error: {errorcode}',
        'instructions_tab': ' Instructions ',
        'startup_tab': ' Startup ',
        'simulate_scan': '📥 Scan',
        'simulate_ng': '🔴 Sim NG',
        'simulate_dup': '🔁 Sim Dup',
        'simulate_gen': '🎲 Generate SN',
        'simulate_clear': '🧹 Clear Pools',
        'simulate_sn_hint': 'Enter SN or click generate',
        # ---- Instruction tab content (English) ----
        'inst_sec1_title': '1. Scan & Check Process',
        'inst_sec1_content': [
            '• Use barcode scanner to scan product SN',
            '• System checks by priority; ANY hit blocks the SN:',
            '',
            '  Priority 1 🔴 NG Pool check (RAM, instant)',
            '    - Check in-memory pool of defective SNs from current Excel',
            '    - Hit → Lock ATE + Voice alarm + Popup window',
            '',
            '  Priority 2 🟡 DUP Pool check (RAM, instant)',
            '    - Check if SN already exists in current Excel data',
            '    - Hit → Duplicate alarm',
            '',
            '  Priority 3 🔴 MES NG history query (Network, background)',
            '    - Query MES ng_registry table',
            '    - Hit → Lock ATE + Voice alarm',
            '',
            '  Priority 4 🟡 Local SQLite check (Disk, background)',
            '    - Check local sn_records database',
            '    - Hit → Duplicate alarm',
            '',
            '  Priority 5 🟡 MES DB check (Network, background)',
            '    - Query MES product table',
            '    - Hit → Duplicate alarm',
            '',
            '• All checks passed → SN enters RAM pool + SQLite, marked PASS',
            '• All checks run in background, scanner not blocked',
        ],
        'inst_sec2_title': '2. NG (Defect) Handling',
        'inst_sec2_content': [
            '• When NG is detected, system automatically:',
            '    ① Disable USB scanner (prevent false scans)',
            '    ② Lock ATE device (pssuspend pauses ATE process)',
            '    ③ Show defect warning window',
            '    ④ Play Vietnamese voice alert',
            '    ⑤ Log NG info to local NG pool and SQLite',
            '• Admin must enter password in popup to confirm:',
            '    - Retest: Product retested',
            '    - Trash: Product scrapped',
            '    - Return to Line: Send back to production line',
        ],
        'inst_sec3_title': '3. Duplicate Handling',
        'inst_sec3_content': [
            '• When duplicate SN is detected, system automatically:',
            '    ① Show duplicate warning window',
            '    ② Play Vietnamese voice alert',
            '    ③ Lock ATE device',
            '    ④ Log duplicate info',
            '• Admin confirms action in popup window',
        ],
        'inst_sec4_title': '4. ATE Device Operation',
        'inst_sec4_content': [
            '▸ Startup Procedure:',
            '    ① Power on ATE test device (ATS231010)',
            '    ② Launch ATE test software (ats231010.exe)',
            '    ③ Confirm software connection OK, channels ready',
            '    ④ Open this quality monitoring system (ATE质量中心越南)',
            '    ⑤ Confirm status bar shows «Running», Excel path correct',
            '',
            '▸ Testing Operation:',
            '    ① Place product into ATE test fixture',
            '    ② Test software runs automatically',
            '    ③ After test, scan product SN with barcode scanner',
            '    ④ System auto-detects NG/dup; if passed, record saved',
            '    ⑤ Passed product moves to next station',
            '',
            '▸ Exception Handling:',
            '    - Device locked: admin unlocks via popup authentication',
            '    - Scanner no response: check USB scanner connection',
            '    - Software frozen: restart ats231010.exe in Task Manager',
            '    - False alarm: contact QC supervisor',
            '',
            '▸ Shutdown Procedure:',
            '    ① Confirm all products tested',
            '    ② Close ATE质量中心越南 system',
            '    ③ Close ATE test software',
            '    ④ Power off ATE device',
        ],
        'inst_sec5_title': '5. Daily Inspection Checklist',
        'inst_sec5_content': [
            '  Check time: Before each shift',
            '',
            '  □ Device Status:',
            '    □ ATE test device power normal',
            '    □ ats231010.exe starts normally',
            '    □ All test channels ready',
            '    □ Test fixture undamaged, probe contact good',
            '',
            '  □ System Status:',
            '    □ ATE质量中心 running, status shows «Running»',
            '    □ Excel monitoring folder path correct',
            '    □ Yesterday test data archived normally',
            '    □ System time matches local time',
            '',
            '  □ Scanner Check:',
            '    □ USB scanner connected',
            '    □ Scanner indicator LED normal',
            '    □ SN scan identifies correctly',
            '    □ TCP port 1003 listening',
            '',
            '  □ Alarm System Check:',
            '    □ Speaker powered on, volume normal',
            '    □ Voice announcement functional',
            '    □ Defect popup window displays correctly',
            '    □ Siren sound plays normally',
            '',
            '  □ Network & Data Check:',
            '    □ MES backend connected (http://192.168.6.155:8080)',
            '    □ Local SQLite database normal',
            '    □ Data folder readable/writable',
            '',
            '  ✅ All checks complete, start production only when all passed',
        ],
        'inst_sec6_title': '6. Daily Reset',
        'inst_sec6_content': [
            '• Auto-reset SN pool, NG pool, and statistics at 12:00 daily',
            '• New Excel file auto-starts monitoring',
            '• Excel header auto-detected, no manual config needed',
        ],
        'inst_sec7_title': '7. Cautions',
        'inst_sec7_content': [
            '⚠ Ensure Excel folder path is correct (shown below)',
            '⚠ Do NOT manually delete monitored Excel files',
            '⚠ When locked, admin must confirm unlock in popup',
            '⚠ Voice prompts in Vietnamese; ensure speaker works',
            '⚠ System auto-detects Excel data start row; no config file edit needed',
        ],
        'inst_sec8_title': '8. Current Configuration',
        # ---- Startup tab content (English) ----
        'start_step1_title': 'Step 1: Power on ATE device',
        'start_step1_content': ['1. Confirm ATE power cable connected', '2. Turn on ATE main power switch', '3. Wait for device LED to light up (green)', '4. Confirm device fan running'],
        'start_step2_title': 'Step 2: Launch ATE test software',
        'start_step2_content': ['1. Double-click ats231010.exe on desktop', '2. Wait for software to load (10-30 seconds)', '3. Confirm all channels show ready status', '4. Check channel voltage/current readings in normal range'],
        'start_step3_title': 'Step 3: Launch ATE Quality Center',
        'start_step3_content': ['1. Double-click ATE质量中心越南 icon on desktop', '2. Wait for system to load', '3. Confirm title bar shows «Running» status', '4. Check bottom status bar:', '   • Data folder path correct?', '   • MES connection normal?', '   • Local API port 3000 listening?'],
        'start_step4_title': 'Step 4: Scanner Check',
        'start_step4_content': ['1. Confirm USB scanner plugged into PC', '2. Confirm scanner red/blue LED on', '3. Scan a test SN; verify recognition', '4. Confirm log area shows scan record', '5. Check TCP port 1003 listening'],
        'start_step5_title': 'Step 5: Alarm System Test',
        'start_step5_content': ['1. Confirm speaker powered on, volume moderate', '2. Click «Sim NG» button to test alarm', '3. Confirm alarm actions work:', '   • Vietnamese voice announcement (Phat hien san pham loi)', '   • Siren sound', '   • Defect popup window', '   • ATE device locked', '4. Admin unlocks, ATE returns to normal'],
        'start_step6_title': 'Step 6: MES Connection Confirm',
        'start_step6_content': ['1. Confirm MES backend service is running', '2. Check Resources tab MES status is ON', '3. Scan test SN to confirm MES dup check works', '4. Confirm data writes to local SQLite correctly'],
        'start_done_text': '☐ Step {step} completed',
        'start_final_msg': '✅ All steps completed, ready for production',
        'start_note1': '📌 If any step is abnormal, notify equipment admin or QC supervisor immediately',
        'start_note2': '📌 Record daily checklist in the «Daily Checklist» document and archive daily',
        # ---- Tooltips (en) ----
        'tt_sim_scan': 'Simulate scan — generate a test SN and trigger the scan flow',
        'tt_sim_pass': 'Simulate PASS — generate a test SN through all 6 dup-check layers',
        'tt_sim_ng': 'Simulate NG — inject a test SN into the NG pool and trigger the 5-alarm cascade',
        'tt_sim_dup': 'Simulate DUP — inject a test SN into the SN pool and trigger the dup alarm',
        'tt_sim_clear': 'Clear all data — wipe in-memory pools + all SQLite records',
        'tt_sim_entry': 'Test SN input — type an SN or click to generate one',
        'tt_btn_delete_sn': 'Delete SN pool — clear all SNs from memory (does not touch SQLite)',
        'tt_btn_delete_ng': 'Delete NG pool — clear all NGs from memory (does not touch SQLite)',
        'tt_btn_clear_sn': '⚠ Clear SN DB — permanently delete all SN records from SQLite',
        'tt_btn_clear_ng': '⚠ Clear NG DB — permanently delete the 5-year NG retention records',
        'tt_mes_toggle': 'MES check toggle — when OFF, only in-memory pool is checked (faster but may miss)',
        'tt_confirm_btn': 'Confirm — enter admin credentials to release the ATE lock',
        'tt_bypass_btn': 'Quick bypass — release the ATE lock without password (emergency only)',
        'tt_admin_user': 'Admin username',
        'tt_admin_pass': 'Admin password',
        'tt_method_retest': 'Retest — re-test the product, removes from NG pool if it passes',
        'tt_method_trash': 'Trash — scrap the product, permanently banned from MES',
        'tt_method_return': 'Return to line — send the product back to the production line',
        'tt_lang_combo': 'Interface language — switch between 中文 / Tiếng Việt / English',
        # ---- Pallet Binding ----
        'binding_tab': ' Pallet Binding ',
        'binding_title': 'Pallet Binding Management',
        'binding_info': 'Scan binding code or enter code to bind/verify',
        'binding_code': 'Code:',
        'binding_pallet_id': 'Pallet ID:',
        'binding_carton_count': 'Cartons:',
        'binding_sn_count': 'Total SN:',
        'binding_status': 'Status:',
        'binding_time': 'Time:',
        'binding_success': 'Binding Success',
        'binding_failed': 'Binding Failed',
        'binding_not_found': 'Binding record not found',
        'binding_already_bound': 'Code already used',
        'binding_pending': 'Pending',
        'binding_verify_ok': 'Verify OK',
        'binding_verify_fail': 'Verify Failed',
        'btn_bind': 'Bind',
        'btn_unbind': 'Unbind',
        'btn_verify_binding': 'Verify',
        'btn_export_binding': 'Export',
        'btn_refresh_binding': 'Refresh',
        'btn_print_binding': 'Print Label',
        'btn_scan_binding': 'Scan Code',
        'btn_create_binding': 'Create Code',
        'col_binding_code': 'Binding Code',
        'col_pallet_id_bind': 'Pallet ID',
        'col_carton_count_bind': 'Cartons',
        'col_sn_total': 'Total SN',
        'col_binding_time': 'Time',
        'col_binding_status': 'Status',
        'binding_history': 'Binding History',
        'unbind_confirm': 'Confirm unbind this pallet?',
        'unbind_title': 'Confirm Unbind',
        'binding_confirm_title': 'Confirm Binding',
        'binding_confirm_msg': 'Confirm binding this pallet?',
        'btn_confirm_bind': 'Confirm',
        'binding_already': 'Already Bound',
        'unbind_success': 'Unbind Successful',
        'export_success': 'Export Successful',
        'export_failed': 'Export Failed',
        'workorder': 'Work Order',
        'no_workorder': 'No Work Order',
        'btn_select_wo': 'Select WO',
        'btn_manual_wo': 'Manual',
    }
}

# ===== Station IP (unique ID per station PC) =====
def _get_station_ip():
    """Get this PC's LAN IP from ipconfig, used as station ID - prefers WLAN"""
    configured_ip = os.environ.get("MES_STATION_IP", "192.168.6.161").strip()
    if configured_ip:
        return configured_ip
    try:
        result = subprocess.run(["ipconfig"], capture_output=True, text=True, encoding="gbk")
        wifi_ip = None
        for line in result.stdout.split("\n"):
            line = line.strip()
            if "IPv4" in line and "127." not in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    ip = parts[1].strip()
                    if ip.startswith("192.168.") or ip.startswith("10."):
                        # WiFi adapter name contains "WLAN"
                        iface = line.split(":")[0].strip()
                        if "WLAN" in iface or "Wi-Fi" in iface or "无线" in iface or "5G" in iface:
                            log(f"[station] IP = {ip} (WLAN)")
                            return ip
                        if wifi_ip is None:
                            wifi_ip = ip
        if wifi_ip:
            log(f"[station] IP = {wifi_ip}")
            return wifi_ip
    except:
        pass
    return "unknown"

_STATION_IP = _get_station_ip()

# ===== 路径配置 =====
APP_FOLDER = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
# ATE Excel 报表根目录。poll_excel() / load_*_from_excel() 会递归扫描所有子目录，
# 自动选取最新的 .xlsx。每个产品一个子目录（如 CW-5V3A-RJ172、26V5056(EPS18R1G-36)）。
# 默认 D:\ATS\测试报表\；若该路径不可用，回退到本地备份目录。
ATE_EXCEL_ROOT = r"D:\SRC"
ATE_EXCEL_FALLBACK = r"D:\瑞晶适配器生产线mes\stations\ate\包装工位越南"

def _resolve_data_folder():
    """Pick the first existing root, falling back to the local backup."""
    for p in [ATE_EXCEL_ROOT, ATE_EXCEL_FALLBACK]:
        if os.path.exists(p):
            return p
    return ATE_EXCEL_ROOT

DATA_FOLDER = _resolve_data_folder()  # legacy alias (kept for back-compat)
MES_API = os.environ.get("MES_API", "http://192.168.6.155:8080/api")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from station_scrap_workflow import request_direct_scrap, start_sync_worker
from station_runtime_safety import acquire_single_instance
LOCAL_PORT = 8090
WS_PORT = 11013  # WebSocket broadcast port; isolated from scanner TCP ports
SYNC_PORT = 0  # Legacy local sync server disabled; MES 8080 is authoritative.
API_KEY = os.environ.get("STATION_API_KEY", "VN-FACTORY-2024")

class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def _auth(self):
        key = self.headers.get("X-Api-Key") or self.path.split("?key=")[-1].split("&")[0]
        if key != API_KEY:
            self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}'); return False
        return True
    def _json(self, data, code=200):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    def do_GET(self):
        if not self._auth(): return
        from datetime import datetime as _dt
        if self.path.startswith("/stats"):
            try:
                today = _dt.now().strftime("%Y-%m-%d")
                conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM sn_records"); total = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM sn_records WHERE LOWER(result)='pass'"); passed = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM sn_records WHERE LOWER(result)='fail'"); failed = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM (SELECT sn FROM sn_records GROUP BY sn HAVING COUNT(*)>1)"); dup = cur.fetchone()[0] or 0
                conn.close()
                self._json({"total": total, "pass": passed, "fail": failed, "dup": dup, "date": today})
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/pools"):
            self._json({"sn_pool": list(_sn_pool), "ng_pool": list(_ng_pool), "dup_pool": list(_dup_pool),
                "sn_pool_count": len(_sn_pool), "ng_pool_count": len(_ng_pool), "dup_pool_count": len(_dup_pool)})
        elif self.path.startswith("/sn_records"):
            try:
                limit = 100
                if "limit=" in self.path: limit = int(self.path.split("limit=")[-1].split("&")[0])
                conn = sqlite3.connect(DB_FILE)
                rows = conn.execute("SELECT sn, result, scan_time FROM sn_records ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                conn.close()
                self._json([{"sn": r[0], "result": r[1], "time": r[2]} for r in rows])
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/ng_pool"):
            try:
                conn = sqlite3.connect(NG_SQLITE)
                rows = conn.execute("SELECT sn, result, channel, errorCode, time FROM ng_pool ORDER BY id DESC LIMIT 100").fetchall()
                conn.close()
                self._json([{"sn": r[0], "result": r[1], "channel": r[2], "errorCode": r[3], "time": r[4]} for r in rows])
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/dup_pool"):
            self._json({"dup_pool": list(_dup_pool), "count": len(_dup_pool)})
        elif self.path.startswith("/health"):
            self._json({"status": "ok"})
        else:
            self._json({"error": "not found"}, 404)

def start_sync_server():
    return
    try:
        import subprocess
        subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule",
            f"name=StationSync_Port{SYNC_PORT}", "dir=in", "action=allow",
            f"localport={SYNC_PORT}", "protocol=tcp", "enable=yes"],
            capture_output=True, timeout=10)
    except: pass
    try:
        server = ThreadingHTTPServer(("0.0.0.0", SYNC_PORT), SyncHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="SyncServer-8089")
        t.start(); log(f"[sync] Sync server: http://0.0.0.0:{SYNC_PORT}")
    except Exception as e: log(f"[sync] Failed: {e}")

# ===== MES Bridge (新MES平台 smt-factory-system, port 8080) =====
# 把本工位的扫码事件/NG/重码/扫码通过推送到新MES，让MES看板能看到产线实时状态。
# 配置可通过环境变量覆盖：MES_NEW_API / MES_NEW_STATION / MES_NEW_OPERATOR / MES_NEW_ENABLED
MES_NEW_API = os.environ.get("MES_NEW_API", "http://192.168.6.155:8080/api")
MES_NEW_ENABLED = os.environ.get("MES_NEW_ENABLED", "1") == "1"
MES_NEW_STATION = os.environ.get("MES_NEW_STATION", "manu_pallet_binding")  # canonical pallet-binding station code
PDA_EVENT_URL = os.environ.get("PDA_EVENT_URL", "http://192.168.6.155:8080/api/pda/events")
MES_NEW_OPERATOR = os.environ.get("MES_NEW_OPERATOR", "ATE_OPERATOR")
MES_NEW_USERNAME = os.environ.get("MES_NEW_USERNAME", "VN_OP_001")
MES_NEW_PASSWORD = os.environ.get("MES_NEW_PASSWORD", "Factory@123")
MES_NEW_QUEUE_MAX = 1000  # 网络断开时的最大离线缓存条数

_mes_new_lock = threading.Lock()
_mes_new_queue = deque()
_mes_new_sent = 0
_mes_new_failed = 0
_mes_new_dropped = 0
_mes_new_thread = None
_mes_new_token = ""


def _mes_new_login():
    """Login the station service account so MES accepts authoritative SN events."""
    global _mes_new_token
    body = json.dumps({"username": MES_NEW_USERNAME, "password": MES_NEW_PASSWORD}).encode("utf-8")
    req = urllib.request.Request(f"{MES_NEW_API}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    payload = data.get("data") or data
    _mes_new_token = payload.get("token", "")
    return _mes_new_token


def _mes_new_worker():
    """后台线程：把队列里的事件POST到新MES。失败后重试3次(每次间隔3秒)，仍失败则丢弃。"""
    global _mes_new_sent, _mes_new_failed, _mes_new_dropped
    while True:
        item = None
        with _mes_new_lock:
            if _mes_new_queue:
                item = _mes_new_queue.popleft()
        if item is None:
            time.sleep(1.0)
            continue
        try:
            url = f"{MES_NEW_API}{item['endpoint']}"
            body = json.dumps(item['payload']).encode('utf-8')
            token = _mes_new_token or _mes_new_login()
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                _ = r.read()
            with _mes_new_lock:
                _mes_new_sent += 1
        except urllib.error.HTTPError as e:
            if e.code == 401:
                globals()["_mes_new_token"] = ""
            with _mes_new_lock:
                _mes_new_failed += 1
                item['retries'] = item.get('retries', 0) + 1
                _mes_new_queue.append(item)
            log(f"[mes-bridge] HTTP {e.code}, queued for retry: {item['endpoint']}")
            time.sleep(3)
        except Exception as e:
            with _mes_new_lock:
                _mes_new_failed += 1
                # 重试3次后丢弃（防止网络长期故障时无限堆积）
                if item.get('retries', 0) < 3:
                    item['retries'] = item.get('retries', 0) + 1
                    _mes_new_queue.append(item)
                else:
                    _mes_new_dropped += 1
                    log(f"[mes-bridge] POST {item['endpoint']} 失败超3次，丢弃")
            log(f"[mes-bridge] POST {item['endpoint']} 失败 (重试中): {e}")
            time.sleep(3)


def start_mes_bridge():
    global _mes_new_thread
    if _mes_new_thread is None or not _mes_new_thread.is_alive():
        _mes_new_thread = threading.Thread(target=_mes_new_worker, daemon=True, name="mes-bridge")
        _mes_new_thread.start()
        log(f"[mes-bridge] 已启动 → {MES_NEW_API} (station={MES_NEW_STATION}, enabled={MES_NEW_ENABLED})")


def packaging_heartbeat_worker():
    while True:
        try:
            payload = {
                "type": "AGENT_HEARTBEAT",
                "stationCode": MES_NEW_STATION,
                "payload": {"agent": "packaging_station", "status": "running", "stationIp": _STATION_IP,
                            "timestamp": int(time.time() * 1000)},
            }
            request = urllib.request.Request(
                PDA_EVENT_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                response.read()
        except Exception:
            pass
        time.sleep(5)


def packaging_3d_container(payload):
    try:
        event = {"type": "CONTAINER_UPDATE", "stationCode": MES_NEW_STATION, "payload": payload}
        request = urllib.request.Request(PDA_EVENT_URL, data=json.dumps(event, ensure_ascii=False).encode("utf-8"), method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=3) as response:
            response.read()
    except Exception as exc:
        log(f"[3d-container] send failed: {exc}")


def _mes_new_enqueue(endpoint, payload):
    if not MES_NEW_ENABLED:
        return
    with _mes_new_lock:
        if len(_mes_new_queue) >= MES_NEW_QUEUE_MAX:
            global _mes_new_dropped
            _mes_new_dropped += 1
            log(f"[mes-bridge] 队列满({MES_NEW_QUEUE_MAX})，丢弃事件")
            return
        _mes_new_queue.append({'endpoint': endpoint, 'payload': payload, 'ts': time.time()})


def mes_bridge_event(sn, result, event_type="station_scan", error_code=None, channel=""):
    """推送一个station event到新MES。result: PASS|FAIL|REPAIRING|CLOSED"""
    payload = {
        "action": event_type,
        "payload": {
            "pcbSerial": sn,
            "stationCode": MES_NEW_STATION,
            "machineCode": ATE_PROCESS,
            "operator": MES_NEW_OPERATOR,
            "eventType": event_type,
            "result": result,
        },
    }
    if error_code:
        payload["payload"]["errorCode"] = error_code
    if channel:
        payload["payload"]["channel"] = channel
    # Unified MES registry: every PASS/NG/duplicate event registers the SN in
    # pcb_serials and appends its station history in station_events.
    _mes_new_enqueue("/mes/events", payload)


def mes_bridge_status():
    """返回桥接状态（用于状态页/调试）"""
    with _mes_new_lock:
        return {
            "enabled": MES_NEW_ENABLED,
            "api": MES_NEW_API,
            "station": MES_NEW_STATION,
            "queueSize": len(_mes_new_queue),
            "queueMax": MES_NEW_QUEUE_MAX,
            "sent": _mes_new_sent,
            "failed": _mes_new_failed,
            "dropped": _mes_new_dropped,
        }


# ================================================================
# WebSocket 服务器（扫码事件实时广播）
# ================================================================
_shutdown_event = threading.Event()
_ws_clients = set()
_ws_broadcast_queue = queue.Queue()


def ws_broadcast(msg: str):
    """把扫码结果广播给所有连接的WebSocket客户端"""
    if not WEBSOCKETS_AVAILABLE:
        return
    try:
        _ws_broadcast_queue.put_nowait(msg)
    except queue.Full:
        pass


async def _ws_handler(websocket, path):
    global _ws_clients
    _ws_clients.add(websocket)
    cid = id(websocket)
    log(f"[WS] 客户端连接: {cid} (总计: {len(_ws_clients)})")
    try:
        async for msg in websocket:
            log(f"[WS] <- {cid}: {msg}")
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)
        log(f"[WS] 客户端断开 (剩余: {len(_ws_clients)})")


async def _ws_broadcast_loop():
    while not _shutdown_event.is_set():
        try:
            msg = await asyncio.get_event_loop().run_in_executor(
                None, _ws_broadcast_queue.get, True, 0.5
            )
            if _ws_clients:
                await asyncio.gather(
                    *[ws.send(msg) for ws in list(_ws_clients)],
                    return_exceptions=True
                )
                log(f"[WS] 广播 -> {len(_ws_clients)} 客户端: {msg}")
        except queue.Empty:
            pass
        except Exception as e:
            log(f"[WS] broadcast error: {e}")


async def _ws_server_main():
    log(f"WebSocket 已启动: ws://0.0.0.0:{WS_PORT}")
    broadcast_task = asyncio.create_task(_ws_broadcast_loop())
    async with websockets.serve(_ws_handler, "0.0.0.0", WS_PORT):
        await _shutdown_event.wait()
    broadcast_task.cancel()


def start_ws_server():
    """启动WebSocket服务器线程"""
    if not WEBSOCKETS_AVAILABLE:
        log("[WS] websockets未安装，跳过WebSocket服务器")
        return
    def ws_loop():
        asyncio.run(_ws_server_main())
    t = threading.Thread(target=ws_loop, daemon=True, name="WS-Server")
    t.start()
    log(f"[WS] WebSocket服务器线程已启动 (port={WS_PORT})")

def _bundle_data_dir():
    """PyInstaller 6.x bundles data files under _internal/ subdirectory.
    Returns path to bundled data (pssuspend.exe, ate_sirens/, etc.) for both
    frozen EXE and dev (python 包装工位 station.py) modes."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, '_internal')
    return os.path.dirname(os.path.abspath(__file__))

_BUNDLE_DIR = _bundle_data_dir()
PSSUSPEND_EXE = os.path.join(_BUNDLE_DIR, "pssuspend.exe")
ATE_PROCESS = "ats231010.exe"
STATE_FILE = os.path.join(APP_FOLDER, "ate_center_state.json")
DB_FILE = os.path.join(APP_FOLDER, "ate_center.db")
NG_SQLITE = os.path.join(APP_FOLDER, "ate_ng_pool.db")
POLL_INTERVAL = 0.5
LOCK_FILE = os.path.join(APP_FOLDER, "ate_station.lock")

# ===== Station exe lifecycle (for /start and /stop endpoints) =====
def start_station_exe(exe_name=None):
    """Start the station exe. Returns {started: True/False, exe, pid, error}."""
    import os, subprocess
    if not exe_name:
        return {"started": False, "exe": exe_name, "error": "exe name required"}
    candidates = [
        os.path.join("D:\\Stations", exe_name),
        os.path.join("D:\\stations", exe_name),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                proc = subprocess.Popen([path], cwd=os.path.dirname(path),
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                return {"started": True, "exe": exe_name, "pid": proc.pid, "path": path}
            except Exception as e:
                return {"started": False, "exe": exe_name, "error": str(e)}
    return {"started": False, "exe": exe_name, "error": "exe not found in D:\\Stations"}


def stop_station_exe(exe_name=None):
    """Stop a running station exe by name. Returns {stopped: True/False, exe, error}."""
    import os, subprocess
    if not exe_name:
        return {"stopped": False, "exe": exe_name, "error": "exe name required"}
    try:
        subprocess.run(["taskkill", "/IM", exe_name, "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return {"stopped": True, "exe": exe_name}
    except Exception as e:
        return {"stopped": False, "exe": exe_name, "error": str(e)}


def get_station_status():
    """Check which station exe processes are running."""
    import subprocess
    names = ["ICT_station.exe", "FCT_station.exe", "PCBADividerStation.exe",
             "QRBinding_v2.exe", "AssemblyATE.exe", "ScannerHelper_ATE.exe",
             "UltrasonicStation.exe", "AgingCab.exe", "HiVoltATE.exe",
             "PackingATE.exe", "PackingStation.exe"]
    running = []
    try:
        out = subprocess.check_output("tasklist /FO CSV /NH", stderr=subprocess.DEVNULL, text=True)
        for line in out.splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 2:
                name = parts[0].strip('"')
                if name in names:
                    running.append({"name": name, "pid": int(parts[1].strip('"'))})
    except Exception:
        pass
    return {"running": running}

# ================================================================
# 看门狗（Watchdog）—— 崩溃自动重启
# ================================================================
WATCHDOG_MARKER_FILE = os.path.join(tempfile.gettempdir(), "ate_quality_center_watchdog.json")
CRASH_MARKER = os.path.join(tempfile.gettempdir(), "ate_quality_center_crash.json")
SHUTDOWN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ate_station.shutdown")


def write_watchdog_marker(restart_count: int):
    """写看门狗标记文件（供工作进程读取状态）"""
    try:
        with open(WATCHDOG_MARKER_FILE, 'w') as f:
            json.dump({
                "restart_count": restart_count,
                "watchdog_pid": os.getpid(),
            }, f)
    except Exception:
        pass


def read_watchdog_marker():
    """读取看门狗状态"""
    try:
        with open(WATCHDOG_MARKER_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"restart_count": 0, "watchdog_pid": 0}


def get_watchdog_status():
    """获取看门狗运行状态"""
    is_worker = "--worker" in sys.argv
    if is_worker:
        marker = read_watchdog_marker()
        return {
            "enabled": True,
            "is_worker": True,
            "restart_count": marker.get("restart_count", 0),
            "watchdog_pid": marker.get("watchdog_pid", 0),
        }
    return {
        "enabled": False,
        "is_worker": False,
        "restart_count": 0,
        "watchdog_pid": 0,
    }


def run_watchdog():
    """看门狗进程：启动工作子进程，崩溃后自动重启"""
    write_watchdog_marker(0)
    log("=" * 50)
    log("  看门狗已启动 — 工作进程崩溃后自动重启")
    log("=" * 50)

    try:
        while not _shutdown_event.is_set():
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "--worker"]
                sout = subprocess.DEVNULL
                serr = subprocess.DEVNULL
            else:
                cmd = [sys.executable, __file__, "--worker"]
                sout = None
                serr = None

            proc = subprocess.Popen(cmd, stdout=sout, stderr=serr)
            log(f"[WATCHDOG] 工作进程已启动 (PID: {proc.pid})")
            proc.wait()

            if _shutdown_event.is_set():
                break

            if proc.returncode == 0:
                log("[WATCHDOG] 工作进程正常退出，看门狗停止")
                break
            if proc.returncode == 42:
                log("[WATCHDOG] 工作进程请求重启")
                for _ in range(2):
                    if _shutdown_event.is_set():
                        return
                    time.sleep(1)
                continue

            write_watchdog_marker(
                read_watchdog_marker().get("restart_count", 0) + 1
            )
            log.warning(
                f"[WATCHDOG] 工作进程异常退出 (code: {proc.returncode})，"
                f"3秒后重启"
            )
            for _ in range(3):
                if _shutdown_event.is_set():
                    return
                time.sleep(1)
    except KeyboardInterrupt:
        log.info("[WATCHDOG] 收到 Ctrl+C")
    finally:
        _shutdown_event.set()
        log.info("[WATCHDOG] 已停止")


# ================================================================
# 自动启动（Windows 注册表）
# ================================================================
AUTO_START_NAME = "ATEQualityCenter"


def set_auto_start(enabled: bool):
    """设置开机自启（HKCU Run key）"""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            if getattr(sys, 'frozen', False):
                cmd = f'"{sys.executable}"'
            else:
                cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, AUTO_START_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, AUTO_START_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        log(f"开机自启 -> {'开启' if enabled else '关闭'}")
        return True
    except Exception as e:
        log(f"设置自启失败: {e}")
        return False


def get_auto_start():
    """检查开机自启状态"""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, AUTO_START_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def register_ip_to_mes():
    """启动时向MES注册本工位IP"""
    try:
        cfg = get_station_config()
        station_code = cfg.get("station", "PACK-01")
        ips = get_local_ips()
        ip = ips[0] if ips else "127.0.0.1"
        payload = json.dumps({"ip_address": ip}).encode("utf-8")
        req = urllib.request.Request(
            f"{MES_NEW_API}/api/mes/stations/{station_code}/ip",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        log(f"[IP REGISTER] reported {ip} for station {station_code} to MES OK")
    except Exception as e:
        log(f"[IP REGISTER] failed: {e}")


def get_local_ips():
    """获取本机所有非回环IPv4地址"""
    ips = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
            if primary and primary != "127.0.0.1":
                ips.append(primary)
    except:
        pass
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and not ip.startswith("127.") and ":" not in ip:
                if ip not in ips:
                    ips.append(ip)
    except:
        pass
    return ips


def open_browser():
    """使用 Edge 浏览器打开本地界面（AGENTS.md 规范）"""
    def _open():
        time.sleep(1.5)
        url = f"http://localhost:{LOCAL_PORT}/"
        log(f"Opening Edge browser: {url}")
        try:
            subprocess.Popen(["msedge", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            try:
                edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                subprocess.Popen([edge_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                log(f"Failed to open Edge: {e}")
    t = threading.Thread(target=_open, daemon=True)
    t.start()


# ===== Pallet Binding 数据库 =====
BINDING_DB = os.path.join(APP_FOLDER, "ate_binding.db")
BINDING_CODE_PREFIX = "BT"
BINDING_CODE_LENGTH = 16  # BT(2) + YYMMDD(6) + SEQ(6) + CHECK(2) = 16

# ===== 单实例保护 =====
def ensure_single_instance():
    """确保只有一个进程运行"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            # 检查进程是否存活
            if PID_VALID(pid):
                print(f"[FATAL] 已有进程 {pid} 运行中，当前进程退出")
                sys.exit(1)
            else:
                os.remove(LOCK_FILE)
        except:
            os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    import atexit
    atexit.register(lambda: _cleanup_lock())

def _cleanup_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except: pass

def PID_VALID(pid):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except:
        return False

# ===== SN格式验证 =====
SN_PATTERN = re.compile(r'^05K41G\d{4}\d{5}$')

def is_valid_sn(sn):
    """验证SN格式: 任意非空字符串"""
    normalized = str(sn or "").strip().upper()
    return bool(SN_PATTERN.fullmatch(normalized))

# ===== NG SQLite =====
def init_ng_sqlite():
    """Create ate_ng_pool SQLite if not exists"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ng_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sn TEXT NOT NULL,
                result TEXT,
                channel TEXT,
                errorCode TEXT,
                file TEXT,
                row INTEGER,
                time TEXT,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ng_sn ON ng_pool(sn)")
        conn.commit()
        conn.close()
        log(f"NG SQLite ready: {NG_SQLITE}")
    except Exception as e:
        log(f"NG SQLite init error: {e}")


# ===== station_config SQLite（工位/产线/操作员配置）=====
def init_station_config():
    """创建 station_config 表并写入默认配置"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS station_config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('station', 'PACK-01')")
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('line_name', 'AUTO-LINE-1')")
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('operator', '')")
        conn.commit()
        conn.close()
        log("station_config 初始化完成")
    except Exception as e:
        log(f"station_config init error: {e}")


def get_station_config():
    """读取 station_config 所有配置"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        rows = conn.execute("SELECT key, value FROM station_config").fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except:
        return {}


def save_station_config(cfg: dict):
    """保存 station_config（station / line_name / operator）"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        for key in ("station", "line_name", "operator"):
            if key in cfg:
                conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES (?, ?)",
                             (key, cfg[key]))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"save_station_config error: {e}")

def load_all_ng_from_excel():
    """Load NG SN from ALL Excel files (recursive across subfolders) into SQLite only (5-year permanent)"""
    if not os.path.exists(DATA_FOLDER):
        log(f"[excel] 数据文件夹不存在: {DATA_FOLDER}")
        return
    try:
        files = _scan_excel_files(DATA_FOLDER)
        if not files:
            log(f"[excel] {DATA_FOLDER} 下未找到 .xlsx（含子目录）")
            return

        total_loaded = 0
        for mtime, fname, fpath in files:
            file_ng = 0
            file_total = 0
            try:
                wb = load_workbook(fpath, read_only=True, data_only=True)
                ws = wb.active
                data_start = _detect_data_start_row(ws)
                max_row = ws.max_row
                rows = list(ws.iter_rows(min_row=data_start, values_only=True))
                wb.close()

                for r in rows:
                    result = str(r[1] or "").strip().upper()
                    barcode = str(r[3] or "").strip()
                    file_total += 1
                    if is_valid_sn(barcode) and result:
                        channel = str(r[2] or "").strip()
                        errorcode = str(r[5] or "").strip()
                        # 静默写入所有SN到pool + SQLite，不报警
                        process_one_sn(barcode, channel, result, errorcode, source=fname)
                        if result in ["NG", "FAIL"]:
                            file_ng += 1
                        total_loaded += 1
                # 标记已读到最后一行，避免poll_excel重新处理
                state["last_rows"][fname] = max_row
                _excel_load_result.append((fname, file_total, file_ng))
                log(f"[excel] ✅ 已读取 {fname}: {file_total} 条记录, {file_ng} NG")
            except Exception as e:
                log(f"[excel] 加载{fname}出错: {e}")
        log(f"[excel] 启动已加载 {total_loaded} 条记录到pool和SQLite")
    except Exception as e:
        log(f"[excel] load_all_ng_from_excel错误: {e}")

def _load_latest_excel_ng():
    """Load NG from latest Excel file (recursive across subfolders) into memory pool only (not SQLite)"""
    global _ng_pool
    if not os.path.exists(DATA_FOLDER):
        return
    try:
        files = _scan_excel_files(DATA_FOLDER)
        if not files:
            return
        mtime, fname, fpath = files[-1]   # latest

        wb = load_workbook(fpath, read_only=True, data_only=True)
        ws = wb.active
        data_start = _detect_data_start_row(ws)
        max_row = ws.max_row
        rows = list(ws.iter_rows(min_row=data_start, values_only=True))
        wb.close()

        count = 0
        total = 0
        for r in rows:
            result = str(r[1] or "").strip().upper()
            barcode = str(r[3] or "").strip()
            total += 1
            if is_valid_sn(barcode) and result:
                channel = str(r[2] or "").strip()
                errorcode = str(r[5] or "").strip()
                # 静默加载最新文件到内存池，不报警
                process_one_sn(barcode, channel, result, errorcode, source=fname)
                if result in ["NG", "FAIL"]:
                    count += 1
        # 标记已读到最后一行，避免poll_excel重新处理
        state["last_rows"][fname] = max_row
        _excel_latest_result = f"{fname}: {total} 条 / {count} NG"
        log(f"[excel] ✅ 最新文件已读取 {fname}: {total} 条记录, {count} NG → 内存池")
    except Exception as e:
        log(f"[excel] _load_latest_excel_ng错误: {e}")

def _write_ng_to_sqlite(sn, result="", channel="", errorcode="", file="", row=0, time_val=""):
    """Write NG to SQLite only (no memory pool)"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO ng_pool (sn, result, channel, errorCode, file, row, time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sn, result, channel, errorcode, file, row, time_val))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"_write_ng_to_sqlite error: {e}")

def save_ng_to_sqlite(sn, result="", channel="", errorCode="", file="", row=0, time_val="", source=""):
    """Save NG to ate_ng_pool.db SQLite (upsert, ignore if exists)"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO ng_pool (sn, result, channel, errorCode, file, row, time, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sn, result, channel, errorCode, file, row, time_val, source))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"save_ng_to_sqlite error: {e}")

def load_ng_from_sqlite():
    """Load all NG SNs from SQLite into _ng_pool"""
    if not os.path.exists(NG_SQLITE):
        return set()
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("SELECT sn FROM ng_pool")
        rows = cur.fetchall()
        conn.close()
        loaded = set(row[0] for row in rows)
        log(f"Loaded {len(loaded)} NG from SQLite")
        return loaded
    except Exception as e:
        log(f"load_ng_from_sqlite error: {e}")
        return set()

def clear_sn_pool():
    """清空SN池（内存+SQLite）"""
    global _sn_pool
    _sn_pool.clear()
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('DELETE FROM sn_records')
        conn.commit()
        conn.close()
    except: pass
    log("已清空SN池（内存+SQLite）")

def clear_ng_pool():
    """清空NG池（内存+SQLite）"""
    global _ng_pool
    _ng_pool.clear()
    try:
        conn = sqlite3.connect(NG_SQLITE)
        conn.execute('DELETE FROM ng_pool')
        conn.commit()
        conn.close()
    except: pass
    log("已清空NG池（内存+SQLite）")

def clear_sn_sqlite():
    """清空SN库（SQLite+内存）"""
    global _sn_pool
    _sn_pool.clear()
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('DELETE FROM sn_records')
        conn.commit()
        conn.close()
    except: pass
    log("已清空SN库（SQLite+内存）")

def clear_ng_sqlite():
    """清空NG库（SQLite+内存）"""
    global _ng_pool
    _ng_pool.clear()
    try:
        conn = sqlite3.connect(NG_SQLITE)
        conn.execute('DELETE FROM ng_pool')
        conn.commit()
        conn.close()
    except: pass
    log("已清空NG库（SQLite+内存）")

def clear_all_pools():
    """清空所有内存池和SQLite记录"""
    global _sn_pool, _ng_pool, _dup_pool
    _sn_pool.clear()
    _ng_pool.clear()
    _dup_pool.clear()
    try:
        conn = sqlite3.connect(NG_SQLITE)
        conn.execute('DELETE FROM ng_pool')
        conn.commit()
        conn.close()
    except: pass
    try:
        conn2 = sqlite3.connect(DB_FILE)
        conn2.execute('DELETE FROM sn_records')
        conn2.execute('DELETE FROM ng_records')
        conn2.execute('DELETE FROM ng_history')
        conn2.commit()
        conn2.close()
    except: pass
    state["stats"] = {"total": 0, "pass": 0, "fail": 0, "dup": 0}
    state["ng_history"] = []
    log("已清空所有数据")

# ===== 4个本地组件 =====
_sn_pool = set()     # 内存全部SN池
_ng_pool = set()     # 内存不良SN池
_dup_pool = set()    # 内存重码池
_silent_mode = True  # 首次加载期间=true，静默模式
_excel_load_result = []  # [(filename, total_rows, ng_count), ...]
_excel_latest_result = ""  # "filename: NNG / N total"

# ===== 状态 =====
state = {
    "mode": "stopped",  # stopped/running/locked/standby
    "locked": False,
    "last_rows": {},   # {filename: last_row}
    "data_start_rows": {},  # {filename: detected_start_row}
    "ng_history": [],
    "stats": {"total": 0, "pass": 0, "fail": 0},
    "date": "",
    "skip_mes_check": False,  # True=跳过MES/SQLite检查，只用内存池
}
pending_queue = []
processing = False
root_ref = [None]

# ---- USB 扫码枪控制 ----
SCANNER_VIDPID = "VID_2A7A&PID_9005"

class USBScannerGuard:
    def __init__(self): self._disabled_ids = []
    def _get_scanner_ids(self):
        try:
            r = subprocess.run(['powershell','-Command',
                "Get-PnpDevice -Class 'HIDClass' | Where-Object {$_.InstanceId -like '*"+SCANNER_VIDPID+"*' -and $_.Status -eq 'OK'} | Select-Object -ExpandProperty InstanceId"],
                creationflags=0x08000000, capture_output=True, text=True, encoding='gbk', errors='replace', timeout=3)
            return [l.strip() for l in r.stdout.splitlines() if l.strip() and SCANNER_VIDPID in l]
        except: return []
    def disable(self):
        threading.Thread(target=self._disable_impl, daemon=True).start()
    def _disable_impl(self):
        ids = self._get_scanner_ids()
        if not ids: return
        for iid in ids:
            try:
                subprocess.Popen(['powershell','-Command',f"Disable-PnpDevice -InstanceId '{iid}' -Confirm:$false"],
                    creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._disabled_ids.append(iid)
            except: pass
    def enable(self):
        def _reenable():
            for iid in self._disabled_ids:
                try:
                    subprocess.Popen(['powershell','-Command',f"Enable-PnpDevice -InstanceId '{iid}' -Confirm:$false"],
                        creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except: pass
            self._disabled_ids.clear()
        threading.Thread(target=_reenable, daemon=True).start()

_usb_guard = USBScannerGuard()

def cf(size=10, bold=False):
    return ("Microsoft JhengHei", str(size), "bold" if bold else "normal")

_LOG_PATH = os.path.join(tempfile.gettempdir(), "ate_debug.log")
_LOG_LOCK = threading.Lock()
_LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB per file
_LOG_KEEP_BACKUPS = 3              # keep ate_debug.log.1 .. .3

def _log_rotate_if_needed():
    """If the log file exceeds _LOG_MAX_BYTES, rotate: log -> .1, .1 -> .2, etc."""
    try:
        if not os.path.exists(_LOG_PATH):
            return
        if os.path.getsize(_LOG_PATH) < _LOG_MAX_BYTES:
            return
        # Drop the oldest backup if it exists
        oldest = f"{_LOG_PATH}.{_LOG_KEEP_BACKUPS}"
        if os.path.exists(oldest):
            os.remove(oldest)
        # Shift .N -> .(N+1)
        for i in range(_LOG_KEEP_BACKUPS - 1, 0, -1):
            src = f"{_LOG_PATH}.{i}"
            dst = f"{_LOG_PATH}.{i+1}"
            if os.path.exists(src):
                os.replace(src, dst)
        # Current -> .1
        os.replace(_LOG_PATH, f"{_LOG_PATH}.1")
    except Exception:
        pass

def log(msg):
    try:
        print(f"[ATE质量中心] {msg}", flush=True)
    except UnicodeEncodeError:
        safe_msg = msg.encode("gbk", errors="replace").decode("gbk")
        print(f"[ATE质量中心] {safe_msg}", flush=True)
    try:
        with _LOG_LOCK:
            _log_rotate_if_needed()
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except: pass

# ===== 语音系统（跟随 _CURRENT_LANG 自动切换 zh/vi/en） =====
try: import edge_tts
except: edge_tts = None

SIREN_DIR = os.path.join(tempfile.gettempdir(), "ate_sirens")
os.makedirs(SIREN_DIR, exist_ok=True)
SIREN_FILE  = os.path.join(SIREN_DIR, "siren.wav")

_voice_counter = 0

# ===== Multilingual Voice System =====
# Voice id + per-prompt text for each UI language.
# File naming: {lang}_{name}.mp3 -> zh_ng.mp3, vi_dup.mp3, en_startup.mp3, ...
VOICE_MSGS = {
    "zh": {
        "voice_id":    "zh-CN-XiaoxiaoNeural",
        "ng":          "检测到不良品，禁止不良品离开本站",
        "dup":         "重复编码，禁止重复品离开本站",
        "pass":        "通过",
        "startup":     "系统正常，请扫码",
        "heartbeat":   "请扫码",
        "lang_switch": "已切换到中文",
        "pass_pack": "通过,可以装箱",
        "remaining":  "还差{count}个",
        "full":       "箱已装满,请封箱",
        "seal":       "封箱完成,继续下一箱",
        "wo_selected": "工单已选择:{billno}",
        "cap_selected": "箱容量:{cap}个",
    },
    "vi": {
        "voice_id":    "vi-VN-HoaiMyNeural",
        "ng":          "Phat hien san pham loi, khong de san pham loi roi khoi tram!",
        "dup":         "Phat hien ma trung lap, khong de ma trung roi khoi tram!",
        "pass":        "Qua mat kiem tra",
        "startup":     "He thong binh thuong, vui long quet ma",
        "heartbeat":   "Vui long quet ma",
        "lang_switch": "Đã chuyển sang tiếng Việt",
        "pass_pack": "Đạt, đóng thùng",
        "remaining":  "Còn {count} cái",
        "full":       "Thùng đã đầy, niêm phong",
        "seal":       "Niêm phong xong, tiếp tục thùng tiếp theo",
        "wo_selected": "Đã chọn lệnh:{billno}",
        "cap_selected": "Dung tích thùng:{cap} cái",
    },
    "en": {
        "voice_id":    "en-US-JennyNeural",
        "ng":          "Defective product detected, do not let defective products leave the station!",
        "dup":         "Duplicate code detected, do not let duplicate products leave the station!",
        "pass":        "Scan passed",
        "startup":     "System normal, please scan the code",
        "heartbeat":   "Please scan the code",
        "lang_switch": "Switched to English",
        "pass_pack": "Pass, ready to pack",
        "remaining":  "{count} more",
        "full":       "Box full, please seal",
        "seal":       "Box sealed, continue to next box",
        "wo_selected": "Work order selected:{billno}",
        "cap_selected": "Box capacity:{cap}",
    },
}

def _voice_tts_path(lang, name):
    """Return cached MP3 path for a given language and prompt name."""
    return os.path.join(SIREN_DIR, f"{lang}_{name}.mp3")

def _make_siren_wav(path):
    """生成警笛WAV（高低音交替）"""
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        for _ in range(2):
            for freq in (880, 660, 880):
                n = int(44100 * 150 / 1000)
                for i in range(n):
                    env = min(1.0, i / max(1, int(n * 0.02)))
                    val = int(0.8 * env * 32767 * math.sin(2 * math.pi * freq * i / 44100))
                    val = max(-32768, min(32767, val))
                    w.writeframes(struct.pack('<h', val))

def _generate_tts(text, voice_id, mp3_path):
    if not edge_tts:
        log(f"[voice] edge_tts not available, skip: {text}")
        return
    try:
        import asyncio
        async def _gen():
            communicate = edge_tts.Communicate(text, voice_id, volume="+200%")
            await communicate.save(mp3_path)
        asyncio.run(_gen())
        log(f"[voice] TTS: {os.path.basename(mp3_path)}")
    except Exception as e:
        log(f"[voice] TTS error: {e}")

def _play_wav_siren():
    """播放警笛WAV（异步）"""
    if not os.path.exists(SIREN_FILE): return
    alias = f"wav{_voice_counter}"; _voice_counter += 1
    try:
        ctypes.windll.winmm.mciSendStringW(f'open "{SIREN_FILE}" type waveaudio alias {alias}', None, 0, None)
        ctypes.windll.winmm.mciSendStringW(f'setaudio {alias} volume to 1000', None, 0, None)
        ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, None)
        ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
    except: pass

def _play_voice_mci(mp3_path):
    """播放MP3语音 - 和 play_all.py 完全一致
    Uses _voice_lock + unique alias (shared with play_alert) to prevent dual-voice."""
    global _voice_counter
    if not mp3_path or not os.path.exists(mp3_path):
        log(f"[voice] MP3 not found: {mp3_path}")
        return
    with _voice_lock:
        _voice_counter += 1
        alias = f"voice_{_voice_counter % 100}"
        try:
            log(f"[voice] MCI opening: {mp3_path} alias={alias}")
            ctypes.windll.winmm.mciSendStringW(f'open "{mp3_path}" type mpegvideo alias {alias}', None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f'setaudio {alias} volume to 1000', None, 0, None)
            r = ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
            log(f"[voice] played: {os.path.basename(mp3_path)} r={r}")
        except Exception as e:
            log(f"[voice] MCI error: {e}")
            try:
                import winsound
                winsound.MessageBeep()
            except: pass
        finally:
            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)

def _copy_bundled_voices():
    """Copy bundled voice files from PyInstaller MEIPASS/_internal/ate_sirens to SIREN_DIR"""
    if not getattr(sys, 'frozen', False):
        return
    try:
        base = _bundle_data_dir()  # PyInstaller 6.x: _MEIPASS/_internal/
        bundled_dir = os.path.join(base, 'ate_sirens')
        if not os.path.isdir(bundled_dir):
            return
        for f_name in os.listdir(bundled_dir):
            src = os.path.join(bundled_dir, f_name)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(SIREN_DIR, f_name)
            if os.path.exists(dst):
                continue
            try:
                import shutil
                shutil.copy2(src, dst)
            except:
                log(f"[voice] copy failed: {f_name}")
        log(f"[voice] bundled voices extracted to {SIREN_DIR}")
    except Exception as e:
        log(f"[voice] bundled copy error: {e}")

def _ensure_voices():
    """Generate TTS voice files for ALL supported languages (zh/vi/en)."""
    _copy_bundled_voices()
    if not os.path.exists(SIREN_FILE):
        _make_siren_wav(SIREN_FILE)
    for lang, cfg in VOICE_MSGS.items():
        voice_id = cfg["voice_id"]
        for name, text in cfg.items():
            if name == "voice_id":
                continue
            dst = _voice_tts_path(lang, name)
            if os.path.exists(dst):
                continue
            log(f"[voice] generating: {lang}_{name}.mp3")
            _generate_tts(text, voice_id, dst)

def _current_lang():
    """Read the live _CURRENT_LANG (fallback to 'zh' if unset)."""
    return globals().get('_CURRENT_LANG', 'zh') or 'zh'

# Serialize voice playback + unique MCI alias to prevent dual-voice when called
# from multiple threads (e.g., NG detected simultaneously with language change).
_voice_lock = threading.Lock()
_voice_counter = 0

def play_alert(kind="ng"):
    """Play NG/Duplicate warning voice in the currently selected language.
    Serialized via _voice_lock; uses a unique MCI alias per call to prevent
    alias conflicts when multiple threads call simultaneously."""
    global _voice_counter
    lang = _current_lang()
    cfg = VOICE_MSGS.get(lang, VOICE_MSGS["zh"])
    name = "ng" if kind == "ng" else "dup"
    mp3_path = _voice_tts_path(lang, name)
    log(f"[voice] play_alert kind={kind} lang={lang} mp3={mp3_path} exists={os.path.exists(mp3_path)}")
    if not os.path.exists(mp3_path):
        return
    with _voice_lock:
        _voice_counter += 1
        alias = f"voice_{_voice_counter % 100}"
        try:
            log(f"[voice] MCI opening: {mp3_path} alias={alias}")
            r1 = ctypes.windll.winmm.mciSendStringW(f'open "{mp3_path}" type mpegvideo alias {alias}', None, 0, None)
            log(f"[voice] MCI open result: {r1}")
            r2 = ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
            log(f"[voice] MCI play result: {r2}")
        except Exception as e:
            log(f"[voice] MCI error: {e}")
        finally:
            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)

def play_lang_switch(lang):
    """Play a short confirmation voice when the user switches language."""
    cfg = VOICE_MSGS.get(lang, VOICE_MSGS["zh"])
    mp3_path = _voice_tts_path(lang, "lang_switch")
    if os.path.exists(mp3_path):
        threading.Thread(target=_play_voice_mci, args=(mp3_path,), daemon=True).start()

def play_pass():
    """Play 'scan passed' voice in the currently selected language.
    Called after an SN passes all 6 duplicate-check layers and is registered."""
    lang = _current_lang()
    mp3_path = _voice_tts_path(lang, "pass")
    log(f"[voice] play_pass lang={lang} mp3={mp3_path} exists={os.path.exists(mp3_path)}")
    if os.path.exists(mp3_path):
        threading.Thread(target=_play_voice_mci, args=(mp3_path,), daemon=True).start()

def play_sn(sn):
    """Announce the accepted serial number before the PASS prompt."""
    text = "S N " + " ".join(str(sn).strip())
    def _run():
        try:
            safe = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                 "Add-Type -AssemblyName System.Speech; "
                 "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                 "$v.Volume=100; $v.Rate=0; $v.Speak('" + safe + "')"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=15,
            )
        except Exception as exc:
            log(f"[voice] SN announcement failed: {exc}")
    threading.Thread(target=_run, daemon=True).start()

def play_pack_voice(key, **fmt):
    """Play a packaging voice in the current language, with optional format args.
    Keys: pass_pack, remaining, full, seal"""
    lang = _current_lang()
    cfg = VOICE_MSGS.get(lang, VOICE_MSGS["zh"])
    text = cfg.get(key, key)
    if fmt:
        text = text.format(**fmt)
    log(f"[voice] pack_voice key={key} text={text}")
    try:
        import hashlib
        safe_name = f"pack_{key}_{hashlib.md5(text.encode()).hexdigest()[:8]}"
        mp3_path = _voice_tts_path(lang, safe_name)
        if not os.path.exists(mp3_path):
            _generate_tts(text, cfg["voice_id"], mp3_path)
        threading.Thread(target=_play_voice_mci, args=(mp3_path,), daemon=True).start()
    except Exception as e:
        log(f"[voice] pack_voice error: {e}")


# ===== Pallet Binding (栈板绑码) 功能 =====
# — Code Generation, Label Preview/Print, Binding DB —

def _get_day_code():
    """Get 2-letter day code for today (AA=Jan1, AB=Jan2...)"""
    _day_map = {}
    from datetime import timedelta
    for _d in range(366):
        try:
            _dt = datetime(2023, 1, 1) + timedelta(days=_d)
            _c1 = chr(ord('A') + (_d // 26) % 26)
            _c2 = chr(ord('A') + _d % 26)
            _day_map[(_dt.month, _dt.day)] = _c1 + _c2
        except:
            break
    now = datetime.now()
    return _day_map.get((now.month, now.day), "AA")


def _generate_binding_code():
    """Generate a unique binding code: BT{YYMMDD}{SEQ:06d}{CHECK}
    CHECK = sum of digits mod 10, formatted as 2 digits (0-padded).
    """
    now = datetime.now()
    prefix = BINDING_CODE_PREFIX  # "BT"
    yymmdd = now.strftime("%y%m%d")
    # Get next sequence from binding DB
    try:
        conn = sqlite3.connect(BINDING_DB)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS binding_seq (id INTEGER PRIMARY KEY, seq INTEGER)")
        row = cur.execute("SELECT seq FROM binding_seq WHERE id=1").fetchone()
        if row:
            seq = row[0] + 1
            cur.execute("UPDATE binding_seq SET seq=? WHERE id=1", (seq,))
        else:
            seq = 1
            cur.execute("INSERT INTO binding_seq(id,seq) VALUES(1,?)", (seq,))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"[binding] seq error: {e}")
        # Fallback: use timestamp-based sequence
        seq = int(time.time() * 1000) % 1000000

    seq_str = f"{seq:06d}"
    raw = prefix + yymmdd + seq_str
    # Calculate 2-digit checksum
    total = sum(ord(c) for c in raw)
    check = f"{total % 100:02d}"
    return raw + check


def _validate_binding_code(code):
    """Validate a binding code by recalculating its checksum."""
    if not code or len(code) != BINDING_CODE_LENGTH:
        return False
    if not code.startswith(BINDING_CODE_PREFIX):
        return False
    raw = code[:-2]  # Remove last 2 check digits
    total = sum(ord(c) for c in raw)
    expected = f"{total % 100:02d}"
    return code[-2:] == expected


def init_binding_db():
    """Create binding_records table if not exists."""
    try:
        conn = sqlite3.connect(BINDING_DB)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS binding_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                binding_code TEXT UNIQUE NOT NULL,
                pallet_id TEXT,
                carton_count INTEGER DEFAULT 0,
                sn_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                bound_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        log(f"[binding] DB ready: {BINDING_DB}")
    except Exception as e:
        log(f"[binding] DB init error: {e}")


# ===== Label Generation (PIL-based) =====
def _generate_box_qr(carton_series):
    """Generate QR code image for carton series"""
    try:
        import qrcode
        img = qrcode.make(carton_series)
        temp_dir = os.path.join(tempfile.gettempdir(), "ate_labels")
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, f"qr_{carton_series}.png")
        img.save(path)
        return path
    except Exception as e:
        log(f"[label] QR error: {e}")
        return None


def _generate_label_image(carton_series, date_code, sn_count, sn_list,
                          model="48V3"):
    """Generate a carton label image (100×150mm @ 203 DPI ≈ 800×1200px)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 800, 1200
        img = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(img)

        try:
            ft_title = ImageFont.truetype("arial.ttf", 36)
            ft_hdr = ImageFont.truetype("arial.ttf", 22)
            ft_sn = ImageFont.truetype("arial.ttf", 16)
            ft_small = ImageFont.truetype("arial.ttf", 14)
        except:
            ft_title = ft_hdr = ft_sn = ft_small = ImageFont.load_default()

        # Header
        draw.text((20, 10), "NetBit Electronics Ltd.", font=ft_title, fill="black")
        draw.text((20, 55), f"Model: EPS48R1-36", font=ft_hdr, fill="black")

        # QR top-right
        try:
            import qrcode
            qr = qrcode.make(carton_series)
            qr = qr.resize((200, 200))
            img.paste(qr, (W - 220, 10))
        except:
            pass

        # Fields
        y = 120
        for lbl, val in [("QUANTITY:", str(sn_count)), ("Date of Mfg:", date_code)]:
            draw.text((20, y), lbl, font=ft_hdr, fill="black")
            draw.text((200, y), val, font=ft_hdr, fill="black")
            y += 30

        # Carton series
        y += 10
        draw.rectangle([(20, y), (W - 20, y + 2)], fill="black")
        y += 10
        draw.text((20, y), "CARTON SERIES:", font=ft_hdr, fill="black")
        draw.text((250, y), carton_series, font=ft_hdr, fill="black")
        y += 35

        # Code-39 barcode
        try:
            import barcode
            from barcode.writer import ImageWriter
            code39 = barcode.get('code39', carton_series, writer=ImageWriter())
            temp_dir = os.path.join(tempfile.gettempdir(), "ate_labels")
            os.makedirs(temp_dir, exist_ok=True)
            bc_path = os.path.join(temp_dir, f"bc_{carton_series}")
            bc_full = code39.save(bc_path)
            bc_img = Image.open(bc_full).convert("RGBA")
            bc_w, bc_h = bc_img.size
            target_w = W - 40
            ratio = target_w / bc_w
            bc_img = bc_img.resize((target_w, int(bc_h * ratio)))
            bc_bg = Image.new("RGBA", bc_img.size, (255, 255, 255, 255))
            bc_bg.paste(bc_img, mask=bc_img)
            img.paste(bc_bg, (20, y))
            y += bc_img.height + 5
        except Exception as be:
            log(f"[label] barcode error: {be}")

        # SN list (2-column)
        y += 5
        draw.text((20, y), "S/N:", font=ft_hdr, fill="black")
        y += 28
        col_x = [20, W // 2 + 20]
        sn_per_col = max(1, (len(sn_list) + 1) // 2)
        for idx, sn in enumerate(sn_list[:30]):
            col = 0 if idx < sn_per_col else 1
            row = idx if col == 0 else idx - sn_per_col
            draw.text((col_x[col], y + row * 22), sn, font=ft_sn, fill="black")

        # Footer
        draw.line([(20, H - 50), (W - 20, H - 50)], fill="black", width=1)
        draw.text((20, H - 45), carton_series, font=ft_hdr, fill="black")

        temp_dir = os.path.join(tempfile.gettempdir(), "ate_labels")
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, f"label_{carton_series}.png")
        img.save(path)
        log(f"[label] generated: {path} ({sn_count} SNs)")
        return path
    except Exception as e:
        log(f"[label] error: {e}")
        return None


def _print_label_image(image_path, printer_name=None):
    """Send label image to Windows printer."""
    try:
        if not image_path or not os.path.exists(image_path):
            return False
        from PIL import Image
        import win32print, win32ui
        from PIL import ImageWin

        if not printer_name:
            printer_name = win32print.GetDefaultPrinter()

        img = Image.open(image_path)
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc(image_path)
        hdc.StartPage()

        dib = ImageWin.Dib(img)
        dib.draw(hdc.GetHandleOutput(), (0, 0, 800, 800))

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
        log(f"[print] sent to {printer_name}: {image_path}")
        return True
    except Exception as e:
        log(f"[print] error: {e}")
        return False


# ===== Tooltip 系统 =====
def _add_tooltip(widget, key, delay_ms=500):
    """Bind a trilingual tooltip to a widget. Uses _T(key) so it follows language changes.

    Note: After language change the entire UI is destroyed and rebuilt, so bindings
    are re-created automatically. We do NOT track and cancel old tooltip Toplevels
    on language change — the old widget tree is gone.
    """
    tip_window = [None]
    tip_after_id = [None]

    def _on_enter(_event=None):
        def _show():
            if tip_window[0] is not None:
                return
            try:
                text = _T(key)
            except Exception:
                return
            if not text:
                return
            try:
                x = widget.winfo_rootx() + 20
                y = widget.winfo_rooty() + widget.winfo_height() + 4
            except Exception:
                return
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(
                tip, text=text, justify=tk.LEFT,
                background="#ffffe0", foreground="#000000",
                relief="solid", borderwidth=1,
                font=("Microsoft JhengHei", 9),
                wraplength=320, padx=6, pady=3,
            )
            lbl.pack()
            tip_window[0] = tip
        tip_after_id[0] = widget.after(delay_ms, _show)

    def _on_leave(_event=None):
        if tip_after_id[0] is not None:
            try:
                widget.after_cancel(tip_after_id[0])
            except Exception:
                pass
            tip_after_id[0] = None
        if tip_window[0] is not None:
            try:
                tip_window[0].destroy()
            except Exception:
                pass
            tip_window[0] = None

    widget.bind("<Enter>", _on_enter, add="+")
    widget.bind("<Leave>", _on_leave, add="+")


# ===== 扫码枪捕获系统（老化站风格） =====
_kb_buf = ""
_kb_listener = None
_kb_lock = threading.Lock()
_tcp_server_running = False
_tcp_server_socket = None
TCP_PORT = 1013  # Pallet scanner TCP; unique during all-station local testing

def _start_keyboard_hook():
    global _kb_listener
    try:
        from pynput import keyboard
        def on_press(key):
            global _kb_buf
            try:
                if hasattr(key, 'char') and key.char:
                    ch = key.char.upper()
                    if ch.isalnum():
                        with _kb_lock:
                            _kb_buf += ch
                elif key == keyboard.Key.enter:
                    with _kb_lock:
                        raw = _kb_buf.strip(); _kb_buf = ""
                    if not raw: return
                    station = root_ref[0]
                    if not station: return
                    station.root.after(0, lambda r=raw: station._process_scan_input(r))
            except: pass
        _kb_listener = keyboard.Listener(on_press=on_press)
        _kb_listener.start()
        log("键盘Hook已启动（扫码枪支持）")
    except Exception as e:
        log(f"键盘Hook失败: {e} (缺少pynput)")

def _start_tcp_server():
    global _tcp_server_running, _tcp_server_socket
    if _tcp_server_running: return
    try:
        import socket
        _tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _tcp_server_socket.bind(("0.0.0.0", TCP_PORT))
        _tcp_server_socket.listen(5)
        _tcp_server_running = True
        log(f"TCP Hook启动: port {TCP_PORT}")
    except Exception as e:
        log(f"TCP服务器错误: {e}"); return

    def accept_loop():
        global _tcp_server_running, _tcp_server_socket
        while _tcp_server_running:
            try:
                _tcp_server_socket.settimeout(1.0)
                client, addr = _tcp_server_socket.accept()
                threading.Thread(target=lambda c=client: _handle_tcp_client(c), daemon=True).start()
            except socket.timeout: continue
            except: break
    _tcp_server_thread = threading.Thread(target=accept_loop, daemon=True)
    _tcp_server_thread.start()

def _handle_tcp_client(client):
    try:
        client.settimeout(5.0)
        data = b""
        while True:
            chunk = client.recv(1024)
            if not chunk: break
            data += chunk
            lines = data.decode('utf-8', errors='replace').split('\n')
            for line in lines[:-1]:
                line = line.strip()
                if line:
                    log(f"[tcp] >> {line}")
                    station = root_ref[0]
                    if station:
                        # 手工设置工单命令: WO:billno,qty  例如 WO:WO20240601,500
                        if line.startswith("WO:"):
                            parts = line[3:].split(",")
                            billno = parts[0].strip()
                            qty = int(parts[1].strip()) if len(parts) > 1 else 99999
                            station._select_workorder({"code": billno, "quantity": qty, "completed": 0})
                            log(f"[tcp] WO set: {billno} qty={qty}")
                        else:
                            station._scan_queue.append(line)
            data = lines[-1].encode('utf-8') if lines[-1] else b""
        client.close()
    except: pass

# ===== SQLite =====
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sn_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sn TEXT UNIQUE NOT NULL,
            channel TEXT,
            result TEXT,
            error_code TEXT,
            scan_time TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ng_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sn TEXT UNIQUE NOT NULL,
            channel TEXT,
            error_code TEXT,
            scan_time TEXT,
            locked INTEGER DEFAULT 0,
            station_ip TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ng_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sn TEXT,
            channel TEXT,
            result TEXT,
            error_code TEXT,
            time TEXT,
            date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS packaging_containers (
            container_id TEXT PRIMARY KEY,
            box_number INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            current_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'packing',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sealed_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS packaging_container_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT NOT NULL,
            sn TEXT NOT NULL UNIQUE,
            packed_at TEXT NOT NULL,
            FOREIGN KEY(container_id) REFERENCES packaging_containers(container_id)
        )
    """)
    c.execute("""CREATE TABLE IF NOT EXISTS packaging_workorder_bindings(
        container_id TEXT PRIMARY KEY,work_order_code TEXT NOT NULL,station_code TEXT NOT NULL,
        bound_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'packing')""")
    conn.commit(); conn.close()
    log("数据库初始化完成")

# ===== Layer 1: 内存池 =====
def save_packaging_container(container_id, box_number, capacity, items, status):
    """Persist a box and its SN contents for offline and reconnect recovery."""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO packaging_containers
                (container_id, box_number, capacity, current_count, status,
                 created_at, updated_at, sealed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(container_id) DO UPDATE SET
                capacity=excluded.capacity,
                current_count=excluded.current_count,
                status=excluded.status,
                updated_at=excluded.updated_at,
                sealed_at=excluded.sealed_at
        """, (container_id, box_number, capacity, len(items), status, now, now,
              now if status in ("full", "sealed") else None))
        for sn in items:
            cur.execute("""
                INSERT OR IGNORE INTO packaging_container_items
                    (container_id, sn, packed_at) VALUES (?, ?, ?)
            """, (container_id, sn, now))
        conn.commit()
        conn.close()
    except Exception as exc:
        log(f"[packaging-db] save failed: {exc}")


def check_pool(sn):
    """检查SN是否在内存池中（只检查，不添加）"""
    return sn in _sn_pool

# ===== Layer 2: SQLite sn_records =====
def check_sqlite(sn):
    """查询本地SQLite sn_records表"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sn_records WHERE sn=?", (sn,))
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False

# ===== Layer 3: MES product表查重 =====
def check_mes(sn):
    """查询MES后端product表，检查SN是否已存在"""
    try:
        url = f"{MES_API}/aging/check?sn={sn}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("code") == 1 and data.get("exist") == True
    except:
        return False

# ===== Layer 3.5: MES NG注册表查询（仅警告） =====
def check_mes_ng(sn):
    """查询MES后端ng_registry表，检查SN是否有NG历史"""
    try:
        url = f"{MES_API}/aging/ng_registry/check?sn={sn}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:  # C6 fix: was 0.05 (50ms) — always timed out, layer non-functional
            data = json.loads(resp.read().decode())
            return data.get("code") == 1 and data.get("found") == True
    except:
        return False

# ===== Layer 4: 本地SQLite ng_records查重（仅警告） =====
def check_ngdb(sn):
    """查询本地SQLite ng_pool表（仅警告，不阻断）"""
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ng_pool WHERE sn=?", (sn,))
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False

# ===== 添加记录（全部通过后才调用） =====
def pool_add(sn):
    """添加SN到内存池"""
    global _sn_pool
    _sn_pool.add(sn)

def sqlite_add(sn, channel="", result="", errorcode=""):
    """写入全部SN到sn_records"""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO sn_records (sn, channel, result, error_code, scan_time) VALUES (?, ?, ?, ?, ?)",
                  (sn, channel, result, errorcode, now))
        conn.commit(); conn.close()
    except:
        pass

def ng_add(sn, channel="", result="", errorcode=""):
    """写入NG到ng_records + ng_history"""
    global _ng_pool
    _ng_pool.add(sn)
    save_ng_to_sqlite(sn, result, channel, errorcode, "ng_add", 0, "", "ng_add")
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO ng_records (sn, channel, error_code, scan_time, locked, station_ip) VALUES (?, ?, ?, ?, 1, ?)",
                  (sn, channel, errorcode, now, _STATION_IP))
        c.execute("INSERT INTO ng_history (sn, channel, result, error_code, time, date) VALUES (?, ?, ?, ?, ?, ?)",
                  (sn, channel, result, errorcode, now[:19], datetime.now().strftime("%Y-%m-%d")))
        conn.commit(); conn.close()
        log(f"NG: {sn} | {channel} | {errorcode}")
    except:
        pass

    state["ng_history"].insert(0, {"sn": sn, "channel": channel, "result": result, "error_code": errorcode, "time": datetime.now().strftime("%H:%M:%S")})
    state["ng_history"] = state["ng_history"][:100]

def sn_ng_add(sn, result="", channel="", errorcode="", file="", row=0, time_val="", source=""):
    """Add NG SN to memory pool + ate_ng_pool.db (5-year NG registry)"""
    global _ng_pool
    _ng_pool.add(sn)
    try:
        conn = sqlite3.connect(NG_SQLITE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO ng_pool (sn, result, channel, errorCode, file, row, time, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sn, result, channel, errorcode, file, row, time_val, source))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"sn_ng_add error: {e}")

# ===== 最近检测的SN列表（用于Tab1 实时监控） =====
recent_sns = []  # {sn, result, time, ch, err, checks:{'sp':0/1, 'sl':0/1, 'sm':0/1, 'np':0/1, 'nl':0/1, 'nm':0/1}}
MAX_RECENT = 100

def add_recent_sn(sn, result, channel, errorcode, is_dup=False, checks=None):
    """添加SN到实时监控列表"""
    entry = {"sn": sn, "result": result, "channel": channel, "errorcode": errorcode,
             "time": datetime.now().strftime("%H:%M:%S"), "is_dup": is_dup,
             "checks": checks or {"sp": 0, "sl": 0, "sm": 0, "np": 0, "nl": 0, "nm": 0}}
    recent_sns.insert(0, entry)
    if len(recent_sns) > MAX_RECENT:
        recent_sns.pop()

# ===== MES product表查询（获取6站状态） =====
STATION_LABELS = ["激光刻码", "超声波焊接", "老化柜", "ATE测试", "包装", "MES上传"]
STATION_KEYS  = ["print_status", "ultrasonic_status", "aging_status", "ate_status", "pack_status", "mes_status"]

def query_product_status(sn):
    """查询MES product表获取产品信息"""
    try:
        url = f"{MES_API}/mes/product?qr_code={sn}"
        import urllib.parse
        url = f"{MES_API}/mes/product?qr_code={urllib.parse.quote(sn)}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == 1 and data.get("product"):
                return data["product"]
        return None
    except:
        return None
def process_one_sn(sn, channel="", result="", errorcode="", source="ATE工位"):
    """
    处理一个SN（Excel一行）- NG检查 + 五重报警 + 更新三层NG存储
    source: 来源工站，如 "ATE工位"、"老化工位1"、"老化工位2" ...
    _silent_mode=True时=静默加载（不报警、不锁、不更新UI、不写pending_queue）
    返回: is_ng
    """
    is_ng_flag = (result.strip().upper() in ["NG", "FAIL"])

    if is_ng_flag:
        already_ng = sn in _ng_pool  # 先检查是否已有
        ng_add(sn, channel, result, errorcode)
        save_ng_to_sqlite(sn, result, channel, errorcode, source, 0, "", source)
        pool_add(sn)  # NG也加入SN池
        sqlite_add(sn, channel, result, errorcode)  # NG也写入ate_center.db
        mes_bridge_event(sn, "FAIL", "defect", errorcode, channel)  # 推送 NG 事件到新 MES

        if _silent_mode:
            log(f"[silent] ⚠ NG {sn} | {channel} | {errorcode} | {source}")
            return True
        # ★ 五重报警：USB禁用 + ATE锁定 + 弹窗 + 声音 + 记录
        log(f"⚠ 检测到NG: {sn} | {channel} | {errorcode} | 来源={source} | 已报警={not already_ng}")
        if not already_ng:
            # 1) 禁用USB扫描枪（后台线程，不阻塞）
            threading.Thread(target=lambda: _usb_guard.disable(), daemon=True).start()
            # 2) 锁定ATE (C8 fix: 3s grace so operator sees alarm before lock fires)
            state["lock_pending"] = True  # coordinate with process_queue: skip its lock during grace
            def _delayed_lock():
                if not state.get("lock_pending"):
                    return  # unlock happened during grace; cancel
                state["lock_pending"] = False
                state["mode"] = "locked"
                state["locked"] = True
                lock_ate()
            if root_ref[0]:
                root_ref[0].root.after(3000, _delayed_lock)
            else:
                _delayed_lock()
            # 3) 弹窗+声音 - alarm window FIRST, voice in background thread
            # (play_alert blocks 5-10s on the Vietnamese phrase via MCI 'play wait')
            # Previously also scheduled _trigger_dup_alarm -> 2nd popup. Removed: the
            # Excel-specific window already has more info (channel, errorcode, source).
            if root_ref[0]:
                root_ref[0].root.after(0, lambda s=sn, c=channel, e=errorcode: root_ref[0]._show_ng_alarm_window(s, c, e))
            threading.Thread(target=play_alert, args=("ng",), daemon=True).start()
            # 4) 记录到UI
            checks = {"sp": 1, "sl": 1, "sm": 1, "np": 1, "nl": 0, "nm": 0}
            add_recent_sn(sn, result, channel, errorcode, False, checks)
            state["stats"]["total"] += 1
            state["stats"]["fail"] += 1
            # 5) pending_queue → MES通知
            pending_queue.append({"sn": sn, "channel": channel, "errorcode": errorcode})
            if root_ref[0]:
                root_ref[0].root.after(0, lambda: root_ref[0].refresh_ui())
        return True
    # PASS — 添加到pool、SQLite，静默模式不更新UI
    pool_add(sn)
    sqlite_add(sn, channel, result, errorcode)
    mes_bridge_event(sn, "PASS", "station_scan", None, channel)  # 推送 PASS 事件到新 MES
    log(f"[excel] ✅ {sn} | {result} | {channel} | {errorcode}")
    if not _silent_mode:
        checks = {"sp": 1, "sl": 1, "sm": 1, "np": 0, "nl": 0, "nm": 0}
        add_recent_sn(sn, result, channel, errorcode, False, checks)
        state["stats"]["total"] += 1
        state["stats"]["pass"] += 1
        if root_ref[0]:
            root_ref[0].root.after(0, lambda: root_ref[0].refresh_ui())
    return False

# ===== 持久化 =====
def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({
                "last_rows": state["last_rows"],
                "data_start_rows": state["data_start_rows"],
                "sn_pool": list(_sn_pool),
                "ng_pool": list(_ng_pool),
                "dup_pool": list(_dup_pool),
                "ng_history": state["ng_history"][-100:],
                "stats": state["stats"],
                "date": state["date"],
            }, f)
    except:
        pass

def load_state():
    global _sn_pool, _ng_pool, _dup_pool
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                d = json.load(f)
                state["last_rows"] = d.get("last_rows", {})
                state["data_start_rows"] = d.get("data_start_rows", {})
                _sn_pool = set(d.get("sn_pool", []))
                _ng_pool = set(d.get("ng_pool", []))
                _dup_pool = set(d.get("dup_pool", []))
                state["ng_history"] = d.get("ng_history", [])
                state["stats"] = d.get("stats", {"total": 0, "pass": 0, "fail": 0})
                state["date"] = d.get("date", "")
                log(f"已加载: SN池={len(_sn_pool)}, NG池={len(_ng_pool)}, 重码池={len(_dup_pool)}")
    except:
        pass

def reset_pools_if_new_day():
    today = datetime.now().strftime("%Y-%m-%d")
    if state["date"] != today:
        global _sn_pool, _ng_pool, _dup_pool
        _sn_pool = set()
        _ng_pool = set()
        _dup_pool = set()
        state["date"] = today
        log(f"新日期 {today}，全部池已重置")

# ===== ATE锁定/解锁 =====
def lock_ate():
    try:
        if os.path.exists(PSSUSPEND_EXE):
            r = subprocess.run([PSSUSPEND_EXE, "-accepteula", ATE_PROCESS],
                             capture_output=True, text=True, timeout=10)
            log(f"锁定ATE: rc={r.returncode}")
            state["locked"] = True
            return r.returncode == 0
        else:
            log("pssuspend.exe不存在")
            return True
    except Exception as e:
        log(f"lock_ate错误: {e}")
        return False

def unlock_ate():
    global pending_queue  # C10 fix: drain pending_queue so process_queue doesn't re-lock
    pending_queue = []
    state["lock_pending"] = False  # C8: cancel any pending grace-period lock
    try:
        if os.path.exists(PSSUSPEND_EXE):
            r = subprocess.run([PSSUSPEND_EXE, "-accepteula", "-r", ATE_PROCESS],
                             capture_output=True, text=True, timeout=10)
            log(f"解锁ATE: rc={r.returncode}")
            state["locked"] = False
            state["mode"] = "standby"
            return r.returncode == 0
        else:
            return True
    except Exception as e:
        log(f"unlock_ate错误: {e}")
        return False

# ===== Excel解析 =====
def _scan_excel_files(root):
    """Recursively scan `root` (and all subfolders) for .xlsx files.
    Returns list of (mtime, fname, fpath) tuples sorted by mtime ASC.
    Skips Excel temp/lock files (start with `~$`).
    """
    if not root or not os.path.exists(root):
        return []
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.startswith("~$") or not fn.endswith(".xlsx"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                mt = os.path.getmtime(fp)
            except OSError:
                continue
            # fname shown to user = relative path under root (so per-product dirs are visible)
            rel = os.path.relpath(fp, root)
            found.append((mt, rel, fp))
    found.sort(key=lambda x: x[0])
    return found

def _detect_data_start_row(ws, max_scan=50):
    """自动检测Excel数据起始行
    查找表头行（包含 Result/Channel/BarCode 等关键字），然后找其后第一个有数字序号的行
    返回行号(1-based)，未找到则返回25
    """
    header_keywords = ["result", "channel", "barcode", "bar code", "no."]
    data_keywords = ["result", "barcode", "bar code"]
    header_row = None
    for row in range(1, min(max_scan, (ws.max_row or 0) + 1)):
        try:
            vals = []
            for c in range(1, 7):
                v = str(ws.cell(row, c).value or "").strip().lower()
                vals.append(v)
            match_count = sum(1 for kw in header_keywords if any(kw in v for v in vals))
            has_data_kw = any(any(dk in v for v in vals) for dk in data_keywords)
            if match_count >= 2 and has_data_kw:
                header_row = row
                log(f"[excel] 检测到表头行 row {row} ({' | '.join(vals[:6])})")
                break
        except:
            continue

    if header_row:
        for row in range(header_row + 1, min(max_scan + header_row, (ws.max_row or 0) + 1)):
            try:
                col1 = str(ws.cell(row, 1).value or "").strip()
                col4 = str(ws.cell(row, 4).value or "").strip()
                if col1.isdigit() and len(col4) >= 3:
                    log(f"[excel] 数据起始行: row {row} (col1={col1}, col4={col4})")
                    return row
            except:
                continue
        log(f"[excel] 未找到数字行，使用表头下一行 row {header_row + 1}")
        return header_row + 1

    log(f"[excel] 未检测到表头行，使用默认值25")
    return 25

def poll_excel():
    if state["mode"] not in ["running", "locked", "standby"]:
        return

    files = _scan_excel_files(DATA_FOLDER)
    if not files:
        return

    mtime, fname, fpath = files[-1]   # latest by mtime
    reset_pools_if_new_day()
    log(f"[excel] monitoring: {fname} (modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))})")

    try:
        wb = load_workbook(fpath, read_only=True, data_only=True)
        ws = wb.active
        if fname not in state["data_start_rows"]:
            state["data_start_rows"][fname] = _detect_data_start_row(ws)
        data_start = state["data_start_rows"][fname]
        last_row = state["last_rows"].get(fname, data_start - 1)
        max_row = ws.max_row

        any_new = False
        for row in range(last_row + 1, max_row + 1):
            try:
                no = str(ws.cell(row, 1).value or "").strip()
                result = str(ws.cell(row, 2).value or "").strip()
                channel = str(ws.cell(row, 3).value or "").strip()
                barcode = str(ws.cell(row, 4).value or "").strip()
                errorcode = str(ws.cell(row, 6).value or "").strip()

                if no and is_valid_sn(barcode) and no.isdigit():
                    any_new = True
                    process_one_sn(barcode, channel, result, errorcode)
                    state["last_rows"][fname] = row
            except:
                pass
        wb.close()
        if any_new:
            new_rows = max_row - last_row
            log(f"[excel] 📊 {fname}: {new_rows} 条新记录已处理")
            save_state()
    except Exception as e:
        log(f"Excel解析错误: {e}")

def process_queue():
    global pending_queue
    if state["mode"] == "locked":
        return
    if state.get("lock_pending"):  # C8: skip lock during 3s grace period
        return
    if pending_queue:
        item = pending_queue.pop(0)
        state["mode"] = "locked"
        state["locked"] = True
        lock_ate()
        if root_ref[0]:
            root_ref[0].root.after(0, lambda: root_ref[0].update_lock_display(item["sn"]))
        log(f"已锁定，SN: {item['sn']}")

# ===== 本地API =====
class LocalAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.path == "/api/ate/unlock":
            log(f"收到MES解锁命令")
            unlock_ate()
            state["mode"] = "running"
            state["locked"] = False
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"code": 1, "msg": "已解锁"}).encode())
            if root_ref[0]:
                root_ref[0].root.after(0, lambda: root_ref[0].update_unlock_display())
        elif self.path == "/api/ate/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {"mode": state["mode"], "locked": state["locked"], "stats": state["stats"],
                    "sn_pool": len(_sn_pool), "ng_pool": len(_ng_pool), "dup_pool": len(_dup_pool),
                    "ng_history": state["ng_history"][-20:]}
            self.wfile.write(json.dumps(resp).encode())
        elif self.path == "/api/ate/sim-ng":
            try:
                if root_ref[0]:
                    root_ref[0]._sim_scan_ng()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(json.dumps({"code": 1, "msg": "sim-ng triggered"}).encode())
                else:
                    self.send_response(503); self.end_headers()
            except Exception as e:
                log(f"[api] sim-ng error: {e}"); self.send_response(500); self.end_headers()
        elif self.path == "/api/ate/sim-pass":
            try:
                if root_ref[0]:
                    root_ref[0]._sim_scan_pass()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(json.dumps({"code": 1, "msg": "sim-pass triggered"}).encode())
                else:
                    self.send_response(503); self.end_headers()
            except Exception as e:
                log(f"[api] sim-pass error: {e}"); self.send_response(500); self.end_headers()
        elif self.path == "/api/ate/sim-dup":
            try:
                if root_ref[0]:
                    root_ref[0]._sim_scan_dup()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                    self.wfile.write(json.dumps({"code": 1, "msg": "sim-dup triggered"}).encode())
                else:
                    self.send_response(503); self.end_headers()
            except Exception as e:
                log(f"[api] sim-dup error: {e}"); self.send_response(500); self.end_headers()
        elif self.path == "/api/ate/upload":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = json.loads(body.decode("utf-8"))
                barcode = data.get("barcode", "").strip()
                result = data.get("result", "PASS").strip()
                channel = data.get("channel", "").strip()
                errorCode = data.get("errorCode", "").strip()
                log(f"[api] upload barcode={barcode} result={result} channel={channel}")
                process_one_sn(barcode, channel, result, errorCode)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"code": 1, "msg": "ok"}).encode())
            except Exception as e:
                log(f"[api] upload error: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
        elif self.path == "/api/ate/status":
            resp = {"mode": state["mode"], "locked": state["locked"], "stats": state["stats"],
                    "sn_pool": len(_sn_pool), "ng_pool": len(_ng_pool), "dup_pool": len(_dup_pool),
                    "ng_history": state["ng_history"][-20:]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        elif self.path == "/api/ate/mes-bridge":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(mes_bridge_status()).encode())
        elif self.path == "/api/heartbeat":
            cfg = get_station_config()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "station": cfg.get("station", "UNKNOWN"), "ip": _STATION_IP}, ensure_ascii=False).encode())
        elif self.path == "/start":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                data = json.loads(body) if body else {}
                exe_name = data.get("exe") if isinstance(data, dict) else None
                result = start_station_exe(exe_name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"started": False, "error": str(e)}).encode())
        elif self.path == "/stop":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                data = json.loads(body) if body else {}
                exe_name = data.get("exe") if isinstance(data, dict) else None
                result = stop_station_exe(exe_name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"stopped": False, "error": str(e)}).encode())
        elif self.path == "/status":
            try:
                result = get_station_status()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/stats":
            try:
                import sqlite3 as _sq
                from datetime import datetime as _dt
                today = _dt.now().strftime("%Y-%m-%d")
                conn = _sq.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM sn_records")
                total = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM sn_records WHERE LOWER(result)='pass'")
                passed = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM sn_records WHERE LOWER(result)='fail'")
                failed = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM (SELECT sn FROM sn_records GROUP BY sn HAVING COUNT(*)>1)")
                dup = cur.fetchone()[0] or 0
                conn.close()
                result = {"total": total, "pass": passed, "fail": failed, "dup": dup, "date": today}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404); self.end_headers()

def _open_firewall_ports():
    """Open ports LOCAL_PORT and WS_PORT in Windows Firewall on startup."""
    import subprocess
    ports = [str(LOCAL_PORT), str(WS_PORT)]
    for port in ports:
        try:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name=StationHelper_Port{port}",
                 "dir=in", "action=allow",
                 f"localport={port}", "protocol=tcp", "enable=yes"],
                capture_output=True, timeout=10
            )
            log(f"[firewall] port {port} opened")
        except Exception as e:
            log(f"[firewall] port {port} failed: {e}")

def start_api():
    _open_firewall_ports()
    server = HTTPServer(("0.0.0.0", LOCAL_PORT), LocalAPIHandler)
    log(f"本地API启动: http://0.0.0.0:{LOCAL_PORT}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    start_sync_server()   # 启动8089数据同步端口（MES/3D看板访问）
    start_mes_bridge()  # 启动新MES桥接后台线程

# ===== Tkinter UI =====
class ATEQualityCenter:
    def __init__(self, root):
        self.root = root
        root_ref[0] = self
        self._current_lang = 'zh'
        root.title(_T("title"))
        root.geometry("1000x750")
        root.configure(bg="#1a1a2e")
        self.dup_alarm_window = 0  # 窗口计数，每个NG独立窗口
        self._scanner_locked = False
        self._ng_pending_recheck = set()  # pending复测的SN，绕过dup警告
        self._scan_queue = []  # TCP/键盘扫码缓冲队列
        # ---- Work Order ----
        self._current_workorder = None  # {"billno": str, "qty": int, "completed": int}
        # ---- 装箱 ----
        self._pack_count = 0        # 当前箱已装数量
        self._box_count = 0         # 已封箱计数
        self._current_box_sns = []  # 当前箱全部SN，用于本机和3D容器显示
        self._current_box_code = None  # real scanned carton code; one code maps to one SN list
        self._auto_pack = True      # 自动装箱（通过后累加）
        # 初始化UI（在dup_alarm_window>0时由 _show_dup_alarm_window 构建）
        self.notebook = None
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        # 先构建主界面，再启动定时刷新
        self.setup_ui()
        self.root.after(500, self.refresh_ui)
        # 生成语音文件
        self.root.after(100, _ensure_voices)
        # 系统启动播报一次（跟随 _CURRENT_LANG）
        self.root.after(2000, lambda: threading.Thread(target=lambda: _play_voice_mci(_voice_tts_path(_current_lang(), "startup")), daemon=True).start())
        _start_keyboard_hook()
        threading.Thread(target=_start_tcp_server, daemon=True).start()
        # 队列轮询
        self.root.after(100, self._check_scan_queue)
        # 自动开始监控（静默）
        state["mode"] = "running"

    def setup_ui(self):
        """初始化主界面UI"""
        # 标题
        title_frame = tk.Frame(self.root, bg="#1a1a2e")
        title_frame.pack(pady=8, fill=tk.X)
        tk.Label(title_frame, text=f"栈板绑码工位 / PALLET BINDING STATION", font=("Microsoft JhengHei", 22, "bold"),
                bg="#1a1a2e", fg="#00d4ff").pack(side=tk.LEFT, expand=True)
        tk.Label(title_frame,text="数据源: 扫码枪 + 装箱/栈板绑定记录 + MES",bg="#1a1a2e",fg="#a7f3d0",font=("Microsoft JhengHei",9)).pack(side=tk.LEFT,padx=8)
        tk.Button(title_frame,text="申请报废",command=lambda: request_direct_scrap(self.root,"manu_pallet_binding",MES_API,
                  recent_sns[0]["sn"] if recent_sns else ""),bg="#b91c1c",fg="white",font=("Microsoft JhengHei",10,"bold")).pack(side=tk.RIGHT,padx=8)
        self.ng_sync_worker=start_sync_worker("manu_pallet_binding", MES_API)
        # 语言选择
        self.lang_combo = ttk.Combobox(title_frame, values=["中文", "Ti\u1ebfng Vi\u1ec7t", "English"],
                                        state="readonly", width=14, font=("Microsoft JhengHei", 10))
        self.lang_combo.current(0)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)
        self.lang_combo.pack(side=tk.RIGHT, padx=(0, 10))
        _add_tooltip(self.lang_combo, "tt_lang_combo")

        # 监控路径显示
        path_frame = tk.Frame(self.root, bg="#0f3460")
        path_frame.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.m_folder_label = tk.Label(path_frame,
            text=f"📁 {_T('file_label')}: {DATA_FOLDER}",
            font=("Microsoft JhengHei", 9), bg="#0f3460", fg="#94a3b8", anchor="w")
        self.m_folder_label.pack(side=tk.LEFT, padx=10, pady=2)

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(2,0))

        # ============ Tab1: 实时监控 ============
        tab_monitor = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_monitor, text=_T("monitor_tab"))
        self._build_monitor_tab(tab_monitor)

        # ============ Tab2: 资源查看 ============
        tab_res = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_res, text=_T("resources_tab"))
        self._build_resources_tab(tab_res)

        # ============ Tab3: 操作说明 ============
        tab_inst = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_inst, text=_T("instructions_tab"))
        self._build_instructions_tab(tab_inst)

        # ============ Tab4: 开机流程 ============
        tab_startup = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_startup, text=_T("startup_tab"))
        self._build_startup_tab(tab_startup)

        tab_pallet=tk.Frame(self.notebook,bg="#1a1a2e")
        self.notebook.add(tab_pallet,text="栈板绑定 / PALLET")
        self._build_real_pallet_tab(tab_pallet)

        tab_handover = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_handover, text="工程交接单 / HANDOVER")
        self.handover_tree = ttk.Treeview(tab_handover, columns=("batch","source","destination","count","status","sent","received"), show="headings")
        for key,label in (("batch","编号"),("source","来源"),("destination","目标"),("count","数量"),("status","状态"),("sent","送出"),("received","接收")): self.handover_tree.heading(key,text=label)
        self.handover_tree.pack(fill="both",expand=True,padx=8,pady=8)

        tab_residence = tk.Frame(self.notebook, bg="#1a1a2e")
        self.notebook.add(tab_residence, text="工位滞留监控 / RESIDENCE")
        self.residence_tree = ttk.Treeview(tab_residence, columns=("sn","batch","state","ng","entered","duration","alarm"), show="headings")
        for key,label in (("sn","SN"),("batch","整盘"),("state","状态"),("ng","NG"),("entered","入站"),("duration","滞留"),("alarm","报警")): self.residence_tree.heading(key,text=label)
        self.residence_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.root.after(500, self._refresh_mes_monitor_pages)

        log("[ui] setup complete")
        self._start_heartbeat()

    def _refresh_mes_monitor_pages(self):
        try:
            base=PDA_EVENT_URL.replace("/api/pda/events","")
            with urllib.request.urlopen(base+f"/api/station/handovers?stationCode={MES_NEW_STATION}",timeout=5) as response: rows=json.loads(response.read().decode()).get("items",[])
            self.handover_tree.delete(*self.handover_tree.get_children())
            for r in rows: self.handover_tree.insert("","end",values=(r.get("batchId"),r.get("sourceStation"),r.get("destinationStation"),r.get("memberCount"),r.get("status"),r.get("sentAt"),r.get("receivedAt")))
            with urllib.request.urlopen(base+f"/api/station/residence-stats?stationCode={MES_NEW_STATION}",timeout=5) as response: data=json.loads(response.read().decode())
            threshold=int(data.get("thresholdMinutes",30))*60; self.residence_tree.delete(*self.residence_tree.get_children())
            for r in data.get("current",[]):
                seconds=int(r.get("seconds",0)); self.residence_tree.insert("","end",values=(r.get("sn"),r.get("batchId"),r.get("productState"),"是" if r.get("isNg") else "否",r.get("enteredAt"),f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}","超时" if seconds>=threshold else "正常"))
        except Exception: pass
        self.root.after(5000,self._refresh_mes_monitor_pages)

    def _start_heartbeat(self):
        """心跳指示灯闪烁"""
        if not hasattr(self, 'm_heartbeat') or not self.m_heartbeat.winfo_exists():
            return
        fg = "#38bdf8" if self._heartbeat_on else "#1a1a2e"
        try:
            self.m_heartbeat.config(fg=fg)
        except:
            return
        self._heartbeat_on = not self._heartbeat_on
        self._heartbeat_job = self.root.after(600, self._start_heartbeat)

    def _toggle_mes_check(self):
        """切换MES检查开关"""
        state["skip_mes_check"] = not state["skip_mes_check"]
        if state["skip_mes_check"]:
            self.mes_toggle_btn.config(text=_T("mes_off"), bg="#dc2626")
            log("MES检查已关闭（只使用内存池）")
        else:
            self.mes_toggle_btn.config(text=_T("mes_on"), bg="#16a34a")
            log("MES检查已开启")

    def _on_lang_change(self, event):
        idx = self.lang_combo.current()
        lang = ['zh', 'vi', 'en'][idx]
        _set_lang(lang)
        self._current_lang = lang
        # 触发对应语言的语音提示（异步，不阻塞UI重建）
        try:
            play_lang_switch(lang)
        except Exception as e:
            log(f"[voice] play_lang_switch error: {e}")
        # Rebuild UI - destroy ALL root children (title_frame + notebook)
        for item in list(self.root.winfo_children()):
            item.destroy()
        self.setup_ui()
        self.refresh_ui()

    def _trigger_dup_alarm(self, sn, layer):
        """重码报警：弹窗 + 声光报警"""
        log(f"[dup_alarm] triggered sn={sn} layer={layer}")
        kind = "ng" if layer == "NG" else "dup"
        self.root.after(0, lambda s=sn, l=layer: self._show_dup_alarm_window(s, l))
        threading.Thread(target=lambda k=kind: play_alert(k), daemon=True).start()
        threading.Thread(target=lambda: _usb_guard.disable(), daemon=True).start()
        if not state.get("lock_pending"):  # C8: respect grace period set by process_one_sn
            lock_ate()  # 锁定ATE设备
        self._scanner_locked = True
        self.append_log(f"重码报警: {sn} [{layer}]")
        if self._heartbeat_job:
            self.root.after_cancel(self._heartbeat_job)
            self._heartbeat_job = None
        self.root.after(1000, lambda: setattr(self, '_scanner_locked', False))

    def _show_dup_alarm_window(self, sn, layer):
        win = tk.Toplevel(self.root)
        win.title(_T("dup_alarm_title"))
        win.attributes("-topmost", True)
        cw, ch = 1200, 720
        sc_w, sc_h = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{cw}x{ch}+{sc_w//2 - cw//2}+{sc_h//2 - ch//2}")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.dup_alarm_window += 1

        bg = tk.Frame(win, bg="#ef4444")
        bg.pack(fill="both", expand=True)

        if layer == "NG":
            tk.Label(bg, text=_T("found_ng"), font=("Arial", 56, "bold"),
                     fg="#ffffff", bg="#ef4444").pack(pady=(40, 20))
            tk.Label(bg, text=f"SN: {sn}", font=("Arial", 32), fg="#ffcccc", bg="#ef4444").pack(pady=8)
            tk.Label(bg, text=_T("source_ng_pool"), font=("Arial", 28), fg="#ffcccc", bg="#ef4444").pack(pady=8)
            tk.Label(bg, text=_T("ban_ng"), font=("Arial", 28), fg="#ffaaaa", bg="#ef4444").pack(pady=16)
        else:
            tk.Label(bg, text=_T("found_dup"), font=("Arial", 56, "bold"),
                     fg="#ffffff", bg="#ef4444").pack(pady=(40, 20))
            tk.Label(bg, text=f"SN: {sn}", font=("Arial", 32), fg="#ffcccc", bg="#ef4444").pack(pady=8)
            tk.Label(bg, text=_T("source_layer").format(layer=layer), font=("Arial", 28), fg="#ffcccc", bg="#ef4444").pack(pady=8)
            tk.Label(bg, text=_T("ban_dup"), font=("Arial", 28), fg="#ffaaaa", bg="#ef4444").pack(pady=16)

        auth_frame = tk.Frame(bg, bg="#ef4444")
        auth_frame.pack(pady=12)
        user_var, pw_var = tk.StringVar(value=""), tk.StringVar(value="")
        tk.Label(auth_frame, text=_T("admin_label"), font=("Arial", 24), fg="#ffffff", bg="#ef4444").grid(row=0, column=0, padx=12, sticky="e")
        dup_user_entry = tk.Entry(auth_frame, textvariable=user_var, font=("Arial", 24), width=16)
        dup_user_entry.grid(row=0, column=1, padx=12)
        _add_tooltip(dup_user_entry, "tt_admin_user")
        tk.Label(auth_frame, text=_T("password_label"), font=("Arial", 24), fg="#ffffff", bg="#ef4444").grid(row=1, column=0, padx=12, pady=8, sticky="e")
        dup_pw_entry = tk.Entry(auth_frame, textvariable=pw_var, font=("Arial", 24), width=16, show="*")
        dup_pw_entry.grid(row=1, column=1, padx=12, pady=8)
        _add_tooltip(dup_pw_entry, "tt_admin_pass")

        def _do_confirm():
            if user_var.get() == "admin" and pw_var.get() == "123456":
                win.destroy()
                self.dup_alarm_window -= 1
                unlock_ate()  # 解锁ATE设备
                threading.Thread(target=lambda: _usb_guard.enable(), daemon=True).start()
                self.append_log(f"重码告警已关闭")
            else:
                log(f"[dup_auth] 认证失败")

        bypass_frame = tk.Frame(auth_frame, bg="#ef4444")
        bypass_frame.grid(row=2, column=0, columnspan=2, pady=(12,0))
        dup_confirm_btn = tk.Button(bypass_frame, text=_T("confirm_btn"), font=("Arial", 32, "bold"),
                  bg="#16a34a", fg="#ffffff", command=_do_confirm,
                  width=10, height=1, bd=0)
        dup_confirm_btn.pack(side=tk.LEFT, padx=(0,12))
        _add_tooltip(dup_confirm_btn, "tt_confirm_btn")
        def _quick_bypass():
            win.destroy()
            self.dup_alarm_window -= 1
            unlock_ate()
            threading.Thread(target=lambda: _usb_guard.enable(), daemon=True).start()
            self.append_log(f"重码告警已绕过")
        dup_bypass_btn = tk.Button(bypass_frame, text=_T("bypass_btn"), font=("Arial", 20, "bold"),
                  bg="#dc2626", fg="#ffffff", command=_quick_bypass,
                  width=8, height=1, bd=0)
        dup_bypass_btn.pack(side=tk.LEFT)
        _add_tooltip(dup_bypass_btn, "tt_bypass_btn")

    def _show_ng_alarm_window(self, sn, channel, errorcode):
        """Excel NG检测到时弹出全屏警告窗口（需要认证才能关闭）"""
        win = tk.Toplevel(self.root)
        win.title(_T("ng_alarm_title"))
        win.attributes("-topmost", True)
        cw, ch = 1200, 720
        sc_w, sc_h = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{cw}x{ch}+{sc_w//2 - cw//2}+{sc_h//2 - ch//2}")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.dup_alarm_window += 1

        bg = tk.Frame(win, bg="#ef4444")
        bg.pack(fill="both", expand=True)

        tk.Label(bg, text=_T("found_ng"), font=("Arial", 56, "bold"),
                 fg="#ffffff", bg="#ef4444").pack(pady=(40, 20))
        tk.Label(bg, text=f"SN: {sn}", font=("Arial", 32), fg="#ffcccc", bg="#ef4444").pack(pady=8)
        tk.Label(bg, text=_T("channel_full").format(channel=channel), font=("Arial", 28), fg="#ffcccc", bg="#ef4444").pack(pady=8)
        tk.Label(bg, text=_T("errorcode_full").format(errorcode=errorcode), font=("Arial", 28), fg="#ffcccc", bg="#ef4444").pack(pady=8)
        tk.Label(bg, text=_T("source_excel"), font=("Arial", 28), fg="#ffaaaa", bg="#ef4444").pack(pady=8)
        tk.Label(bg, text=_T("ban_ng"), font=("Arial", 28), fg="#ffaaaa", bg="#ef4444").pack(pady=16)

        auth_frame = tk.Frame(bg, bg="#ef4444")
        auth_frame.pack(pady=12)
        user_var, pw_var = tk.StringVar(value=""), tk.StringVar(value="")
        tk.Label(auth_frame, text=_T("admin_label"), font=("Arial", 24), fg="#ffffff", bg="#ef4444").grid(row=0, column=0, padx=12, sticky="e")
        ng_user_entry = tk.Entry(auth_frame, textvariable=user_var, font=("Arial", 24), width=16)
        ng_user_entry.grid(row=0, column=1, padx=12)
        _add_tooltip(ng_user_entry, "tt_admin_user")
        tk.Label(auth_frame, text=_T("password_label"), font=("Arial", 24), fg="#ffffff", bg="#ef4444").grid(row=1, column=0, padx=12, pady=8, sticky="e")
        ng_pw_entry = tk.Entry(auth_frame, textvariable=pw_var, font=("Arial", 24), width=16, show="*")
        ng_pw_entry.grid(row=1, column=1, padx=12, pady=8)
        _add_tooltip(ng_pw_entry, "tt_admin_pass")

        result_label = tk.Label(bg, text="", font=("Arial", 18), fg="#ffff00", bg="#ef4444")
        result_label.pack(pady=4)

        def _do_confirm():
            if user_var.get() == "admin" and pw_var.get() == "123456":
                log(f"[ng_auth] 认证成功，sn={sn}")
                self._record_ng_handling(sn, channel, errorcode, "closed")
                win.destroy()
                self.dup_alarm_window -= 1
                unlock_ate()
                threading.Thread(target=lambda: _usb_guard.enable(), daemon=True).start()
                self.append_log(f"NG告警已关闭: {sn}")
                self._heartbeat_job = None
            else:
                result_label.config(text=_T("auth_failed"))
                log(f"[ng_auth] 认证失败")

        btn_frame2 = tk.Frame(bg, bg="#ef4444")
        btn_frame2.pack(pady=12)
        ng_confirm_btn = tk.Button(btn_frame2, text=_T("confirm_btn"), font=("Arial", 32, "bold"),
                  bg="#16a34a", fg="#ffffff", command=_do_confirm,
                  width=10, height=1, bd=0)
        ng_confirm_btn.pack(side=tk.LEFT, padx=(0,12))
        _add_tooltip(ng_confirm_btn, "tt_confirm_btn")
        def _quick_bypass_ng():
            win.destroy()
            self.dup_alarm_window -= 1
            unlock_ate()
            threading.Thread(target=lambda: _usb_guard.enable(), daemon=True).start()
            self.append_log(f"NG告警已绕过: {sn}")
        ng_bypass_btn = tk.Button(btn_frame2, text=_T("bypass_btn"), font=("Arial", 20, "bold"),
                  bg="#dc2626", fg="#ffffff", command=_quick_bypass_ng,
                  width=8, height=1, bd=0)
        ng_bypass_btn.pack(side=tk.LEFT)
        _add_tooltip(ng_bypass_btn, "tt_bypass_btn")

    def _build_monitor_tab(self, parent):
        """Tab1: 实时监控"""
        def cf(s=10, b=False): return ("Microsoft JhengHei", str(s), "bold" if b else "normal")
        # 状态卡片
        card = tk.Frame(parent, bg="#1a1a2e")
        card.pack(pady=8)
        self.m_status = tk.Label(card, text=_T("status_label") + ": " + _T("stopped"), font=cf(14, True),
                                 bg="#1a1a2e", fg="#ffcc00", width=18, height=2, relief="groove", bd=3)
        self.m_status.pack(side=tk.LEFT, padx=8)
        self.m_lock = tk.Label(card, text=_T("device_label") + ": " + _T("unlocked"), font=cf(14, True),
                               bg="#1a1a2e", fg="#00ff00", width=18, height=2, relief="groove", bd=3)
        self.m_lock.pack(side=tk.LEFT, padx=8)
        # 心跳指示器
        self.m_heartbeat = tk.Label(card, text="●", font=("Arial", 24),
                                    bg="#1a1a2e", fg="#38bdf8", width=3, relief="groove", bd=3)
        self.m_heartbeat.pack(side=tk.LEFT, padx=8)
        self._heartbeat_on = True
        self._heartbeat_job = None
        # 统计行
        sf = tk.Frame(parent, bg="#1a1a2e")
        sf.pack(pady=5)
        self.m_total = tk.Label(sf, text=_T("total_label") + ": 0", font=cf(12), bg="#16213e", fg="#ffffff", width=10)
        self.m_total.pack(side=tk.LEFT, padx=3)
        self.m_pass = tk.Label(sf, text=_T("pass_label") + ": 0", font=cf(12), bg="#16213e", fg="#00ff00", width=12)
        self.m_pass.pack(side=tk.LEFT, padx=3)
        self.m_fail = tk.Label(sf, text=_T("fail_label") + ": 0", font=cf(12), bg="#16213e", fg="#ff4444", width=12)
        self.m_fail.pack(side=tk.LEFT, padx=3)
        self.m_dup = tk.Label(sf, text=_T("dup_label") + ": 0", font=cf(12), bg="#16213e", fg="#ffaa00", width=10)
        self.m_dup.pack(side=tk.LEFT, padx=3)
        # 池状态
        self.m_pool = tk.Label(parent, text=_T("pool_status").format(total=0, ng=0, dup=0),
                               font=cf(10), bg="#16213e", fg="#aaaaaa", height=2)
        self.m_pool.pack(fill=tk.X, padx=20, pady=3)
        # 正在测试的SN
        self.m_current = tk.Label(parent, text=_T("waiting"), font=cf(13, True),
                                  bg="#1a1a2e", fg="#38bdf8", height=2)
        self.m_current.pack(pady=3)
        # 文件
        self.m_file = tk.Label(parent, text=_T("file_label") + ": --", font=cf(9),
                               bg="#1a1a2e", fg="#888888")
        self.m_file.pack()
        # ===== 工单信息 =====
        wo_row = tk.Frame(parent, bg="#0f3460")
        wo_row.pack(fill=tk.X, padx=20, pady=(4,0))
        self._wo_lbl = tk.Label(wo_row, text=_T("workorder") + ": " + _T("no_workorder"),
                                font=("Microsoft JhengHei", 10), bg="#0f3460", fg="#00d4ff")
        self._wo_lbl.pack(side=tk.LEFT, padx=10, pady=3)
        tk.Button(wo_row, text=_T("btn_select_wo"), font=("Microsoft JhengHei", 9),
                  bg="#0f766e", fg="#ffffff", command=self._load_workorder_selection).pack(side=tk.RIGHT, padx=5, pady=2)
        tk.Button(wo_row, text=_T("btn_manual_wo"), font=("Microsoft JhengHei", 9),
                  bg="#374151", fg="#ffffff", command=self._manual_workorder_input).pack(side=tk.RIGHT, padx=2, pady=2)
        # SN状态表格
        sn_frame = tk.Frame(parent, bg="#1a1a2e")
        sn_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=3)
        tk.Label(sn_frame, text=_T("check_title"), font=cf(10, True),
                 bg="#1a1a2e", fg="#38bdf8").pack(anchor="w")
        cols = (_T("col_sn"), _T("col_result"), _T("col_sp"), _T("col_sl"), _T("col_sm"), _T("col_np"), _T("col_nl"), _T("col_nm"), _T("col_time"))
        self.sn_tree = ttk.Treeview(sn_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.sn_tree.heading(c, text=c)
            w = 120 if c == "SN" else 70
            self.sn_tree.column(c, width=w)
        sb_sn = ttk.Scrollbar(sn_frame, orient=tk.VERTICAL, command=self.sn_tree.yview)
        self.sn_tree.configure(yscrollcommand=sb_sn.set)
        sb_sn.pack(side=tk.RIGHT, fill=tk.Y)
        self.sn_tree.pack(fill=tk.BOTH, expand=True)
        # ===== 装箱 =====
        box_frame = tk.LabelFrame(parent, text="装箱", font=("Microsoft JhengHei", 10, "bold"),
                                  fg="#00d4ff", bg="#1a1a2e", padx=5, pady=5)
        box_frame.pack(fill=tk.X, padx=20, pady=(3, 0))
        cap_row = tk.Frame(box_frame, bg="#1a1a2e")
        cap_row.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(cap_row,text="装箱码:",font=("Microsoft JhengHei",10),fg="#fbbf24",bg="#1a1a2e").pack(side=tk.LEFT)
        self._box_code_var=tk.StringVar()
        box_entry=tk.Entry(cap_row,textvariable=self._box_code_var,width=22,font=("Consolas",11))
        box_entry.pack(side=tk.LEFT,padx=5)
        box_entry.bind("<Return>",lambda _event:self._activate_box_code())
        tk.Button(cap_row,text="确认箱码",command=self._activate_box_code,bg="#2563eb",fg="white").pack(side=tk.LEFT,padx=3)
        tk.Label(cap_row, text="箱容量:", font=("Microsoft JhengHei", 10),
                 fg="#94a3b8", bg="#1a1a2e").pack(side=tk.LEFT)
        self._box_capacity = tk.StringVar(value="100")
        cap_combo = ttk.Combobox(cap_row, textvariable=self._box_capacity,
                                 values=["100", "96", "50", "46", "40"],
                                 state="normal", width=8, font=("Microsoft JhengHei", 10))
        cap_combo.pack(side=tk.LEFT, padx=5)
        self._box_capacity.trace_add("write", lambda *a: (
            self._update_pack_display(),
            play_pack_voice("cap_selected", cap=self._box_capacity.get())
        ))
        self._pack_info_lbl = tk.Label(cap_row, text="已装: 0/100  箱号: 1",
                                       font=("Microsoft JhengHei", 10, "bold"),
                                       fg="#00d4ff", bg="#1a1a2e")
        self._pack_info_lbl.pack(side=tk.LEFT, padx=10)
        tk.Button(cap_row, text="封箱", font=("Microsoft JhengHei", 9),
                  bg="#dc2626", fg="#ffffff", command=self._seal_box).pack(side=tk.RIGHT, padx=2)

        # 扫描日志
        log_frame = tk.Frame(parent, bg="#1a1a2e")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=3)
        tk.Label(log_frame, text=_T("scan_log"), font=cf(10, True),
                 bg="#1a1a2e", fg="#94a3b8").pack(anchor="w")
        self.m_log = tk.Text(log_frame, font=("Consolas", 10), bg="#0f172a", fg="#e2e8f0",
                             height=12, bd=0, relief="flat")
        sb_log = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.m_log.yview)
        self.m_log.configure(yscrollcommand=sb_log.set)
        sb_log.pack(side=tk.RIGHT, fill=tk.Y)
        self.m_log.pack(fill=tk.BOTH, expand=True)
        log_frame.pack_forget()

        # ===== SN扫码测试按钮 =====
        sim_frame = tk.Frame(parent, bg="#1e293b", bd=1, relief="groove")
        sim_frame.pack(fill=tk.X, padx=10, pady=(0,8))

        tk.Label(sim_frame, text="🔍 SN测试:", font=("Microsoft JhengHei", 11, "bold"),
                 fg="#38bdf8", bg="#1e293b").pack(side=tk.LEFT, padx=(10,6), pady=6)
        self._sim_entry_var = tk.StringVar()
        sim_entry = tk.Entry(sim_frame, textvariable=self._sim_entry_var, font=("Consolas", 14),
                             bg="#0f172a", fg="#e2e8f0", insertbackground="#38bdf8",
                             relief="sunken", bd=2, width=28)
        sim_entry.pack(side=tk.LEFT, padx=(0,6), pady=6)
        sim_entry.bind("<Return>", lambda e: self._sim_scan())
        _add_tooltip(sim_entry, "tt_sim_entry")
        btn_scan = tk.Button(sim_frame, text="📥 扫码", command=self._sim_scan,
                  font=("Microsoft JhengHei", 11, "bold"), fg="#ffffff", bg="#16a34a",
                  padx=16, pady=3)
        btn_scan.pack(side=tk.LEFT, padx=(0,6), pady=6)
        _add_tooltip(btn_scan, "tt_sim_scan")

        btn_row = tk.Frame(parent, bg="#0f172a")
        btn_row.pack(fill=tk.X, padx=10, pady=(0,8))
        btn_pass = tk.Button(btn_row, text="模拟扫码", command=self._sim_scan_pass,
                  font=("Microsoft JhengHei", 11), fg="#ffffff", bg="#475569", padx=12, pady=3)
        btn_pass.pack(side=tk.LEFT, padx=(0,6))
        _add_tooltip(btn_pass, "tt_sim_pass")
        btn_ng = tk.Button(btn_row, text="模拟NG", command=self._sim_scan_ng,
                  font=("Microsoft JhengHei", 11), fg="#ffffff", bg="#dc2626", padx=12, pady=3)
        btn_ng.pack(side=tk.LEFT, padx=(0,6))
        _add_tooltip(btn_ng, "tt_sim_ng")
        btn_dup = tk.Button(btn_row, text="模拟重码", command=self._sim_scan_dup,
                  font=("Microsoft JhengHei", 11), fg="#ffffff", bg="#d97706", padx=12, pady=3)
        btn_dup.pack(side=tk.LEFT, padx=(0,6))
        _add_tooltip(btn_dup, "tt_sim_dup")
        btn_clr = tk.Button(btn_row, text="清空", command=self._sim_clear,
                  font=("Microsoft JhengHei", 11), fg="#ffffff", bg="#475569", padx=12, pady=3)
        btn_clr.pack(side=tk.RIGHT)
        _add_tooltip(btn_clr, "tt_sim_clear")

    # ===== Work Order (工单) =====
    def _fetch_workorders(self):
        """Fetch work orders from MES API"""
        try:
            import urllib.request, json
            url = f"{MES_API}/k3/orders"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return data.get("data", []) if isinstance(data, dict) else []
        except Exception as e:
            log(f"[wo] fetch error: {e}")
            return []

    def _select_workorder(self, wo):
        """Select a work order and update UI"""
        self._current_workorder = {
            "billno": wo.get("code", wo.get("billno", "")),
            "qty": int(wo.get("quantity", wo.get("qty", 0))),
            "completed": int(wo.get("completed", 0))
        }
        self._pack_count = 0
        self._refresh_workorder_display()
        billno = self._current_workorder['billno']
        log(f"[wo] selected: {billno}")
        play_pack_voice("wo_selected", billno=billno)

    def _refresh_workorder_display(self):
        """Update the work order label"""
        if self._current_workorder:
            wo = self._current_workorder
            remaining = wo["qty"] - wo["completed"]
            self._wo_lbl.config(
                text=f"{_T('workorder')}: {wo['billno']}  \u76ee\u6807:{wo['qty']}  \u5b8c\u6210:{wo['completed']}  \u5269\u4f59:{remaining}")
        else:
            self._wo_lbl.config(text=_T("workorder") + ": " + _T("no_workorder"))

    def _load_workorder_selection(self):
        """Open work order selection dialog"""
        win = tk.Toplevel(self.root)
        win.title(_T("btn_select_wo"))
        win.geometry("500x400")
        win.transient(self.root)
        win.configure(bg="#1a1a2e")
        tk.Label(win, text=_T("btn_select_wo"), font=("Microsoft JhengHei", 12, "bold"),
                 bg="#1a1a2e", fg="#00d4ff").pack(pady=10)

        frame = tk.Frame(win, bg="#1a1a2e")
        frame.pack(fill="both", expand=True, padx=10)
        cols = ("\u5de5\u5355\u53f7", "\u7269\u6599", "\u6570\u91cf", "\u72b6\u6001")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor="center")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        workorders = self._fetch_workorders()
        for wo in workorders:
            status_map = {"in_progress": "\u8fdb\u884c\u4e2d", "completed": "\u5b8c\u6210",
                          "approved": "\u5df2\u4e0b\u8fbe", "pending": "\u5f85\u5904\u7406"}
            tree.insert("", "end", values=(
                wo.get("code", wo.get("billno", "")),
                wo.get("product_model", ""),
                wo.get("quantity", wo.get("qty", "")),
                status_map.get(wo.get("status", ""), "\u672a\u77e5")
            ))

        def on_select():
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0])["values"]
                wo = next((w for w in workorders if w.get("code", w.get("billno", "")) == vals[0]), None)
                if wo:
                    self._select_workorder(wo)
                    win.destroy()

        btn_frame = tk.Frame(win, bg="#1a1a2e")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="\u786e\u5b9a", font=("Microsoft JhengHei", 11),
                  bg="#16a34a", fg="#ffffff", command=on_select).pack()

    def _manual_workorder_input(self):
        """Dialog for manually entering work order (no MES API needed)"""
        win = tk.Toplevel(self.root)
        win.title(_T("btn_manual_wo"))
        win.geometry("400x200")
        win.transient(self.root)
        win.configure(bg="#1a1a2e")

        tk.Label(win, text=_T("workorder") + ":", font=("Microsoft JhengHei", 11),
                 bg="#1a1a2e", fg="#00d4ff").pack(pady=(20, 5))

        entry_var = tk.StringVar()
        entry = tk.Entry(win, textvariable=entry_var, font=("Microsoft JhengHei", 14),
                         width=30, justify="center")
        entry.pack(pady=5)
        entry.focus()

        tk.Label(win, text=_T("no_workorder") + " → " + _T("btn_manual_wo"),
                 font=("Microsoft JhengHei", 9), bg="#1a1a2e", fg="#888888").pack()

        def on_confirm():
            code = entry_var.get().strip()
            if code:
                self._select_workorder({"code": code, "quantity": 99999, "completed": 0})
                win.destroy()

        btn_frame = tk.Frame(win, bg="#1a1a2e")
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text=_T("confirm_btn"), font=("Microsoft JhengHei", 11),
                  bg="#16a34a", fg="#ffffff", command=on_confirm).pack()

        win.bind("<Return>", lambda e: on_confirm())

    # ===== 装箱 =====
    def _activate_box_code(self):
        code=self._box_code_var.get().strip().upper()
        workorder=(self._current_workorder or {}).get("code") or (self._current_workorder or {}).get("billno")
        if not workorder:
            messagebox.showwarning("需要工单","请先选择工单，再扫描装箱码");return
        if len(code)<6 or not all(ch.isalnum() or ch in "-_" for ch in code):
            messagebox.showwarning("装箱码","无效装箱码，请重新扫描");return
        with sqlite3.connect(DB_FILE) as conn:
            row=conn.execute("SELECT status FROM packaging_containers WHERE container_id=?",(code,)).fetchone()
            binding=conn.execute("SELECT work_order_code FROM packaging_workorder_bindings WHERE container_id=?",(code,)).fetchone()
            if row and row[0] in ("full","sealed"):
                self._trigger_dup_alarm(code,"BOX_CODE_DUPLICATE");messagebox.showerror("重复箱码",f"箱码 {code} 已封箱");return
            if binding and binding[0]!=workorder:
                messagebox.showerror("工单冲突",f"箱码已绑定工单 {binding[0]}");return
            conn.execute("INSERT OR REPLACE INTO packaging_workorder_bindings(container_id,work_order_code,station_code,bound_at,status) VALUES(?,?,?,?,?)",
                         (code,workorder,MES_NEW_STATION,time.strftime("%Y-%m-%d %H:%M:%S"),"packing"))
        if self._current_box_code and self._current_box_code!=code and self._pack_count>0:
            messagebox.showwarning("当前箱未完成",f"当前箱 {self._current_box_code} 尚未封箱");return
        self._current_box_code=code
        save_packaging_container(code,self._box_count+1,int(self._box_capacity.get()),self._current_box_sns,"packing")
        packaging_3d_container({"containerId":code,"workOrderCode":workorder,"boxNumber":self._box_count+1,
            "items":list(self._current_box_sns),"currentCount":self._pack_count,"capacity":int(self._box_capacity.get()),
            "remaining":max(0,int(self._box_capacity.get())-self._pack_count),"status":"packing","updatedAt":int(time.time()*1000)})
        self._update_pack_display()

    def _pack_sn_pass(self, sn=None):
        """Auto-pack: increment box count, check capacity, play voice"""
        if not self._auto_pack:
            return
        if not self._current_box_code:
            messagebox.showwarning("请先扫箱码","箱码未绑定工单，产品SN不能入箱");return
        cap = int(self._box_capacity.get())
        if sn:
            self._current_box_sns.append(sn)
        self._pack_count += 1
        remaining = cap - self._pack_count
        box_id = self._current_box_code
        status = "full" if self._pack_count >= cap else "packing"
        container_payload = {
            "containerId": box_id, "boxNumber": self._box_count + 1,
            "workOrderCode": (self._current_workorder or {}).get("code") or (self._current_workorder or {}).get("billno"),
            "items": list(self._current_box_sns), "currentCount": self._pack_count,
            "capacity": cap, "remaining": max(0, remaining),
            "status": status,
            "updatedAt": int(time.time() * 1000),
        }
        save_packaging_container(box_id, self._box_count + 1, cap,
                                 self._current_box_sns, status)
        packaging_3d_container(container_payload)
        if self._pack_count >= cap:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("UPDATE packaging_workorder_bindings SET status='sealed' WHERE container_id=?",(box_id,))
            self._box_count += 1
            play_pack_voice("full")
            self._pack_count = 0  # 自动重置，继续下一箱
            self._current_box_sns = []
            self._current_box_code = None
            self._box_code_var.set("")
            self.root.after(1500, lambda: play_pack_voice("remaining", count=cap))
        else:
            play_pack_voice("remaining", count=remaining)
        self._update_pack_display()

    def _seal_box(self):
        """Seal current box, reset counter, play voice"""
        if self._pack_count == 0:
            return
        save_packaging_container(self._current_box_code,self._box_count+1,int(self._box_capacity.get()),self._current_box_sns,"sealed")
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE packaging_workorder_bindings SET status='sealed' WHERE container_id=?",(self._current_box_code,))
        self._box_count += 1
        self._pack_count = 0
        self._current_box_sns = []
        self._current_box_code = None
        self._box_code_var.set("")
        play_pack_voice("seal")
        self._update_pack_display()

    def _update_pack_display(self):
        """Update the 装箱 UI labels"""
        cap = int(self._box_capacity.get())
        text = f"装箱码: {self._current_box_code or '未扫描'}  已装: {self._pack_count}/{cap}"
        if hasattr(self, '_pack_info_lbl'):
            self._pack_info_lbl.config(text=text)

    def _build_real_pallet_tab(self,parent):
        row=tk.Frame(parent,bg="#1a1a2e");row.pack(fill="x",padx=20,pady=15)
        self._pallet_code_var=tk.StringVar();self._pallet_target_var=tk.StringVar(value="20");self._pallet_carton_var=tk.StringVar();self._pallet_status_var=tk.StringVar(value="请先选择工单并扫描栈板码")
        for label,var,width in (("栈板码",self._pallet_code_var,20),("目标箱数",self._pallet_target_var,8),("箱码",self._pallet_carton_var,20)):
            tk.Label(row,text=label,bg="#1a1a2e",fg="white").pack(side="left",padx=(8,2));tk.Entry(row,textvariable=var,width=width).pack(side="left",padx=3)
        def api(path,body):
            req=urllib.request.Request(MES_API+path,json.dumps(body,ensure_ascii=False).encode("utf-8"),{"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=5) as response:return json.loads(response.read().decode("utf-8"))
        def create():
            wo=(self._current_workorder or {}).get("code") or (self._current_workorder or {}).get("billno")
            if not wo: messagebox.showwarning("工单","请先选择工单");return
            try: api("/station/pallets",{"palletCode":self._pallet_code_var.get().strip().upper(),"workOrderCode":wo,"targetCartons":int(self._pallet_target_var.get()),"stationCode":MES_NEW_STATION,"createdBy":"OPERATOR"});self._pallet_status_var.set("栈板建立成功，请扫描箱码")
            except Exception as exc: messagebox.showerror("栈板建立失败",str(exc))
        def add():
            try:
                d=api(f"/station/pallets/{self._pallet_code_var.get().strip().upper()}/cartons",{"containerId":self._pallet_carton_var.get().strip().upper(),"addedBy":"OPERATOR"});self._pallet_status_var.set(f"箱码加入成功，还差{d.get('remaining')}箱");self._pallet_carton_var.set("")
            except Exception as exc: messagebox.showerror("箱码加入失败",str(exc))
        def seal():
            try: api(f"/station/pallets/{self._pallet_code_var.get().strip().upper()}/seal",{});self._pallet_status_var.set("满栈完成，栈板已锁定")
            except Exception as exc: messagebox.showerror("满栈失败",str(exc))
        tk.Button(row,text="建立栈板",command=create,bg="#2563eb",fg="white").pack(side="left",padx=4);tk.Button(row,text="加入箱码",command=add,bg="#059669",fg="white").pack(side="left",padx=4);tk.Button(row,text="确认满栈",command=seal,bg="#b91c1c",fg="white").pack(side="left",padx=4)
        tk.Label(parent,textvariable=self._pallet_status_var,bg="#0f172a",fg="#fbbf24",font=("Microsoft JhengHei",14,"bold"),pady=15).pack(fill="x",padx=20)

    # Clean production implementation. This later definition intentionally
    # replaces the legacy pallet-tab implementation above.
    def _build_real_pallet_tab(self, parent):
        row = tk.Frame(parent, bg="#1a1a2e")
        row.pack(fill="x", padx=20, pady=15)
        self._pallet_code_var = tk.StringVar()
        self._pallet_target_var = tk.StringVar(value="20")
        self._pallet_carton_var = tk.StringVar()
        self._pallet_printer_var = tk.StringVar(value=os.environ.get("PALLET_LABEL_PRINTER", ""))
        self._pallet_status_var = tk.StringVar(value="请先选择工单并扫描栈板码")

        entries = {}
        for key, label, variable, width in (
            ("pallet", "栈板码", self._pallet_code_var, 20),
            ("target", "目标箱数", self._pallet_target_var, 8),
            ("carton", "箱码", self._pallet_carton_var, 20),
        ):
            tk.Label(row, text=label, bg="#1a1a2e", fg="white").pack(side="left", padx=(8, 2))
            entry = tk.Entry(row, textvariable=variable, width=width)
            entry.pack(side="left", padx=3)
            entries[key] = entry

        tk.Label(row, text="标签打印机", bg="#1a1a2e", fg="white").pack(side="left", padx=(8, 2))
        printer_entry = tk.Entry(row, textvariable=self._pallet_printer_var, width=20)
        printer_entry.pack(side="left", padx=3)

        def api(path, body):
            request = urllib.request.Request(
                MES_API + path,
                json.dumps(body, ensure_ascii=False).encode("utf-8"),
                {"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        def create():
            work_order = (self._current_workorder or {}).get("code") or (self._current_workorder or {}).get("billno")
            pallet_code = self._pallet_code_var.get().strip().upper()
            if not work_order:
                messagebox.showwarning("工单", "请先选择工单")
                return
            if not pallet_code:
                messagebox.showwarning("栈板码", "请扫描栈板码")
                return
            try:
                api("/station/pallets", {
                    "palletCode": pallet_code,
                    "workOrderCode": work_order,
                    "targetCartons": int(self._pallet_target_var.get()),
                    "stationCode": MES_NEW_STATION,
                    "createdBy": "OPERATOR",
                })
                self._pallet_status_var.set("栈板建立成功，请扫描箱码")
                entries["carton"].focus_set()
            except Exception as exc:
                messagebox.showerror("栈板建立失败", str(exc))

        def add():
            pallet_code = self._pallet_code_var.get().strip().upper()
            carton_code = self._pallet_carton_var.get().strip().upper()
            if not pallet_code or not carton_code:
                messagebox.showwarning("扫码", "请扫描栈板码和箱码")
                return
            try:
                result = api(f"/station/pallets/{pallet_code}/cartons", {
                    "containerId": carton_code,
                    "addedBy": "OPERATOR",
                })
                self._pallet_status_var.set(f"箱码加入成功，还差 {result.get('remaining')} 箱")
                self._pallet_carton_var.set("")
                entries["carton"].focus_set()
            except Exception as exc:
                messagebox.showerror("箱码加入失败", str(exc))

        def print_label(pallet_code, carton_count, unit_count):
            printer = self._pallet_printer_var.get().strip()
            if not printer:
                raise RuntimeError("请先填写 Windows 打印机名称")
            work_order = (self._current_workorder or {}).get("code") or (self._current_workorder or {}).get("billno") or ""
            label_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "labels")
            os.makedirs(label_dir, exist_ok=True)
            label_path = os.path.join(label_dir, f"PALLET_{pallet_code}_{datetime.now():%Y%m%d%H%M%S}.txt")
            label = (f"栈板码 / PALLET: {pallet_code}\n"
                     f"工单 / WORK ORDER: {work_order}\n"
                     f"箱数 / CARTONS: {carton_count}\n"
                     f"产品数 / UNITS: {unit_count}\n"
                     f"完成时间 / TIME: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            with open(label_path, "w", encoding="utf-8-sig") as label_file:
                label_file.write(label)
            subprocess.Popen(["notepad.exe", "/pt", label_path, printer], creationflags=0x08000000)
            return label_path

        def seal():
            pallet_code = self._pallet_code_var.get().strip().upper()
            if not pallet_code:
                messagebox.showwarning("栈板码", "请扫描栈板码")
                return
            try:
                result = api(f"/station/pallets/{pallet_code}/seal", {"actor": "OPERATOR"})
            except Exception as exc:
                messagebox.showerror("满栈失败", str(exc))
                return
            try:
                print_label(pallet_code, result.get("cartonCount", 0), result.get("unitCount", 0))
                self._pallet_status_var.set("满栈完成，栈板已锁定，标签已发送打印")
            except Exception as exc:
                self._pallet_status_var.set("满栈完成并已锁定，但标签打印失败，请补打")
                messagebox.showwarning("打印失败", f"栈板已经锁定。请配置打印机后补打标签。\n{exc}")

        def reprint():
            pallet_code = self._pallet_code_var.get().strip().upper()
            if not pallet_code:
                messagebox.showwarning("栈板码", "请扫描栈板码")
                return
            try:
                print_label(pallet_code, "请核对", "请核对")
                self._pallet_status_var.set("补打标签已发送到打印机")
            except Exception as exc:
                messagebox.showerror("打印失败", str(exc))

        tk.Button(row, text="建立栈板", command=create, bg="#2563eb", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="加入箱码", command=add, bg="#059669", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="确认满栈", command=seal, bg="#b91c1c", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="补打标签", command=reprint, bg="#7c3aed", fg="white").pack(side="left", padx=4)
        entries["pallet"].bind("<Return>", lambda _event: create())
        entries["carton"].bind("<Return>", lambda _event: add())
        tk.Label(parent, textvariable=self._pallet_status_var, bg="#0f172a", fg="#fbbf24",
                 font=("Microsoft JhengHei", 14, "bold"), pady=15).pack(fill="x", padx=20)

    def _build_ng_tab(self, parent):
        """Tab2: NG记录列表"""
        columns = (_T("col_sn"), _T("col_result"), _T("col_channel"), _T("col_errorcode"), _T("col_time"), _T("col_station_ip"))
        self.ng_tree = ttk.Treeview(parent, columns=columns, show="headings", height=20)
        for col in columns:
            self.ng_tree.heading(col, text=col)
            self.ng_tree.column(col, width=180)
        sb_ng = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.ng_tree.yview)
        self.ng_tree.configure(yscrollcommand=sb_ng.set)
        sb_ng.pack(side=tk.RIGHT, fill=tk.Y)
        self.ng_tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def _build_resources_tab(self, parent):
        """Tab3: 资源查看 - 多列阵布局"""
        # 顶部按钮行
        bf = tk.Frame(parent, bg="#1a1a2e")
        bf.pack(fill=tk.X, padx=10, pady=(8,4))
        btn_del_sn = tk.Button(bf, text=_T("btn_delete_sn"), font=("Microsoft JhengHei", 9), bg="#dc2626", fg="#ffffff",
                 relief="raised", command=lambda: clear_sn_pool())
        btn_del_sn.pack(side=tk.LEFT, padx=3)
        _add_tooltip(btn_del_sn, "tt_btn_delete_sn")
        btn_del_ng = tk.Button(bf, text=_T("btn_delete_ng"), font=("Microsoft JhengHei", 9), bg="#dc2626", fg="#ffffff",
                 relief="raised", command=lambda: clear_ng_pool())
        btn_del_ng.pack(side=tk.LEFT, padx=3)
        _add_tooltip(btn_del_ng, "tt_btn_delete_ng")
        btn_clr_sn = tk.Button(bf, text=_T("btn_clear_sn"), font=("Microsoft JhengHei", 9), bg="#b45309", fg="#ffffff",
                 relief="raised", command=lambda: clear_sn_sqlite())
        btn_clr_sn.pack(side=tk.LEFT, padx=3)
        _add_tooltip(btn_clr_sn, "tt_btn_clear_sn")
        btn_clr_ng = tk.Button(bf, text=_T("btn_clear_ng"), font=("Microsoft JhengHei", 9), bg="#b45309", fg="#ffffff",
                 relief="raised", command=lambda: clear_ng_sqlite())
        btn_clr_ng.pack(side=tk.LEFT, padx=3)
        _add_tooltip(btn_clr_ng, "tt_btn_clear_ng")
        self.mes_toggle_btn = tk.Button(bf, text=_T("mes_on"), font=("Microsoft JhengHei", 9),
                                       bg="#16a34a", fg="#ffffff", relief="raised",
                                       command=self._toggle_mes_check)
        self.mes_toggle_btn.pack(side=tk.LEFT, padx=3)
        _add_tooltip(self.mes_toggle_btn, "tt_mes_toggle")

        # 四列表格
        cols = (_T("pool_sn"), _T("pool_ng"), _T("registry_sn"), _T("registry_ng"))
        self.r_all_tree = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols:
            self.r_all_tree.heading(c, text=c)
            self.r_all_tree.column(c, width=130)
        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.r_all_tree.yview)
        self.r_all_tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,10))
        self.r_all_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,5))

    def _build_instructions_tab(self, parent):
        """Tab3: 操作说明 / 启动流程 - trilingual content from LANG dict"""
        canvas = tk.Canvas(parent, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas, bg="#1a1a2e")
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        def _mw(e): canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _mw)

        fg_t = "#00d4ff"; fg_s = "#e0e0e0"; fg_h = "#facc15"; fg_w = "#ef4444"
        ft_t = ("Microsoft JhengHei",14,"bold")
        ft_h = ("Microsoft JhengHei",12,"bold")
        ft_b = ("Microsoft JhengHei",10)

        def add_lbl(text,font=ft_b,fg=fg_s,pady=6):
            tk.Label(sf,text=text,font=font,fg=fg,bg="#1a1a2e",
                     justify=tk.LEFT,wraplength=700).pack(anchor="w",padx=20,pady=(pady,2))

        # Get current language data
        ld = LANG.get(self._current_lang, LANG['zh'])

        add_lbl(_T("instructions_tab").strip(), ft_t, fg_t, 12)

        # Section 1~7: iterate over section arrays
        sections = [
            ('inst_sec1_title', 'inst_sec1_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec2_title', 'inst_sec2_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec3_title', 'inst_sec3_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec4_title', 'inst_sec4_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec5_title', 'inst_sec5_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec6_title', 'inst_sec6_content', fg_h, ft_h, ft_b, fg_s),
            ('inst_sec7_title', 'inst_sec7_content', fg_h, ft_h, ft_b, fg_w),
        ]
        for tkey, ckey, cfg_title, ft_hdr, ft_body, cfg_body in sections:
            add_lbl(ld.get(tkey, tkey), ft_hdr, cfg_title, 10)
            for line in ld.get(ckey, []):
                add_lbl(line, ft_body, cfg_body)

        # Section 8: current config (dynamic, always in-line)
        add_lbl(ld.get('inst_sec8_title', '8. Current Config'), ft_h, fg_h, 10)
        config_prefixes = {
            'zh': ['数据文件夹', 'MES API', '本地端口', '轮询间隔', '工位IP'],
            'vi': ['Thư mục dữ liệu', 'MES API', 'Cổng địa phương', 'Chu kỳ', 'IP Trạm'],
            'en': ['Data Folder', 'MES API', 'Local Port', 'Poll Interval', 'Station IP'],
        }
        cp = config_prefixes.get(self._current_lang, config_prefixes['zh'])
        config_vals = [DATA_FOLDER, MES_API, str(LOCAL_PORT), f"{POLL_INTERVAL}s", _STATION_IP]
        for p, v in zip(cp, config_vals):
            add_lbl(f"• {p}: {v}", ft_b, fg_s)

    def _build_startup_tab(self, parent):
        """Tab4: 开机流程 / Startup / Quy trình khởi động - trilingual"""
        self._startup_step = 0
        canvas = tk.Canvas(parent, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas, bg="#1a1a2e")
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        def _mw(e): canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _mw)

        fg_t = "#00d4ff"; fg_s = "#e0e0e0"; fg_n = "#facc15"
        fg_d = "#22c55e"; fg_w = "#ef4444"
        ft_t = ("Microsoft JhengHei",14,"bold")
        ft_h = ("Microsoft JhengHei",12,"bold")
        ft_b = ("Microsoft JhengHei",10)
        ft_c = ("Microsoft JhengHei",11,"bold")

        def add_lbl(text,font=ft_b,fg=fg_s,pady=4,padx=25):
            tk.Label(sf,text=text,font=font,fg=fg,bg="#1a1a2e",
                     justify=tk.LEFT,wraplength=700).pack(anchor="w",padx=padx,pady=(pady,0))

        ld = LANG.get(self._current_lang, LANG['zh'])
        add_lbl(_T("startup_tab").strip(), ft_t, fg_t, 14, 20)

        # Steps 1-6: iterate from LANG keys
        for i in range(1, 7):
            add_lbl("", pady=2)
            title_key = f'start_step{i}_title'
            content_key = f'start_step{i}_content'
            done_key = 'start_done_text'

            add_lbl(ld.get(title_key, title_key), ft_h, fg_n, 8)
            for line in ld.get(content_key, []):
                add_lbl(line, ft_b, fg_s)
            add_lbl("", pady=2)
            done_text = ld.get(done_key, '☐ Step {step} done').format(step=i)
            tk.Label(sf, text=done_text, font=ft_c, fg=fg_d, bg="#1a1a2e",
                     cursor="hand2").pack(anchor="w", padx=25, pady=2)

        # Final message
        add_lbl("", 8)
        add_lbl("═══════════════════════════════", ft_b, fg_t)
        add_lbl("", 2)
        add_lbl(ld.get('start_final_msg', '✅ All steps completed'), ft_h, fg_d)
        add_lbl("", 2)
        add_lbl(ld.get('start_note1', '📌 Notify admin if abnormal'), ft_b, fg_w)
        add_lbl(ld.get('start_note2', '📌 Record checklist daily'), ft_b, fg_s)
        add_lbl("", 4)
        add_lbl("═══════════════════════════════", ft_b, fg_t)

    def _generate_test_sn(self):
        """生成一个有效的测试SN: 05K41G + MMDD + 5位序号"""
        now = datetime.now()
        mmdd = now.strftime("%m%d")
        # 用当前时间戳后5位作序号，避免重复
        serial = f"{int(time.time()) % 100000:05d}"
        return f"05K41G{mmdd}{serial}"

    def _sim_scan(self):
        """从输入框取SN进行扫码"""
        sn = self._sim_entry_var.get().strip()
        if not sn:
            sn = self._generate_test_sn()
            self._sim_entry_var.set(sn)
        self._process_scan_input(sn)

    def _sim_scan_pass(self):
        """生成一个合格SN走完整通过流程"""
        sn = self._generate_test_sn()
        self._sim_entry_var.set(sn)
        self._process_scan_input(sn)

    def _sim_scan_ng(self):
        """生成NG SN（注入NG池后扫码）"""
        sn = self._generate_test_sn()
        self._sim_entry_var.set(sn)
        log(f"[sim] NG注入: {sn}")
        # C11 fix: route through process_one_sn for proper SQLite persistence (ng_pool 5-year retention)
        process_one_sn(sn, channel="R1", result="NG", errorcode="E001", source="sim-ng")

    def _sim_scan_dup(self):
        """生成重码SN（注入SN池后扫码）"""
        sn = self._generate_test_sn()
        self._sim_entry_var.set(sn)
        global _sn_pool
        _sn_pool.add(sn)
        log(f"[sim] 重码注入: {sn}")
        self._process_scan_input(sn)

    def _sim_clear(self):
        """清空所有内存池和SQLite"""
        clear_all_pools()
        state["stats"] = {"total": 0, "pass": 0, "fail": 0}
        self._sim_entry_var.set("")
        self.append_log("🧹 已清空所有池")
        self.refresh_ui()

    def _check_scan_queue(self):
        try:
            s = root_ref[0]
            if s:
                while self._scan_queue:
                    raw = self._scan_queue.pop(0)
                    self._process_scan_input(raw)
        except: pass
        self.root.after(100, self._check_scan_queue)

    def _process_scan_input(self, raw):
        """处理扫码枪输入（KB hook或TCP传入）- 快速路径，不阻塞"""
        sn = raw.strip()
        if not sn or not is_valid_sn(sn):
            return
        log(f"[scan] SN={sn}")

        local_ng=self.ng_sync_worker.ng_guard.get(sn) if hasattr(self,"ng_sync_worker") else None
        if local_ng:
            source=local_ng.get("sourceStationCode") or local_ng.get("stationCode") or "UNKNOWN"
            log(f"[LOCAL NG SQLITE] SN={sn} source={source}")
            self._scanner_locked=True
            threading.Thread(target=play_alert,args=("ng",),daemon=True).start()
            messagebox.showerror("ACTIVE NG / 不良品拦截",f"SN: {sn}\n来源工位: {source}\n必须确认取出后才能继续")
            self.root.after(1000,lambda:setattr(self,"_scanner_locked",False))
            return

        # Mandatory synchronous MES decision. Never write SQLite, update a
        # container/pallet, or announce PASS before MES approves this SN.
        allowed, decision = mes_scan_gate(
            PDA_EVENT_URL, MES_NEW_STATION, sn,
            event_type="pallet_binding_scanner", timeout=6,
            operation="PALLET_OR_CASE_BINDING",
        )
        if not allowed:
            code = str(decision.get("code") or decision.get("error", {}).get("code") or "MES_BLOCKED")
            log(f"[MES BLOCK] SN={sn} code={code} detail={decision}")
            self._scanner_locked = True
            threading.Thread(target=play_alert, args=("ng",), daemon=True).start()
            messagebox.showerror("MES BLOCK / MES拦截", f"SN: {sn}\nMES: {code}\n禁止入箱/入栈板")
            self.root.after(1000, lambda: setattr(self, "_scanner_locked", False))
            return

        # Pending recheck SN → 跳过NG池告警，从pending移除
        if sn in self._ng_pending_recheck:
            self._ng_pending_recheck.discard(sn)
            log(f"[ng_recheck] passing recheck: sn={sn}")
            # 继续走正常流程，不阻断

        # 直接检查NG pool（memory pool for latest Excel NG）
        if sn in _ng_pool and sn not in self._ng_pending_recheck:
            log(f"⚠ 扫描到NG池SN: {sn}")
            state["stats"]["total"] += 1
            state["stats"]["fail"] += 1
            add_recent_sn(sn, "NG", "", "", False, {"sp":1,"sl":1,"sm":1,"np":0,"nl":1,"nm":0})
            pending_queue.append({"sn": sn, "channel": "", "errorcode": ""})
            # Schedule alarm window FIRST, then start voice in background thread
            # (was: play_alert direct call blocked main thread 5-10s, delaying popup)
            if root_ref[0]:
                root_ref[0].root.after(0, lambda s=sn: root_ref[0]._trigger_dup_alarm(s, "NG"))
            threading.Thread(target=play_alert, args=("ng",), daemon=True).start()
            self.root.after(50, self.refresh_ui)
            return

        # 三重查重（仅内存池检查，不阻塞）
        is_dup = False
        if sn in _sn_pool or sn in _dup_pool:
            log(f"❌ 重码:Pool → {sn}")
            state["stats"]["total"] += 1
            state["stats"]["pass"] += 1
            add_recent_sn(sn, "PASS", "", "", True, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":0})
            if root_ref[0]:
                root_ref[0].root.after(0, lambda s=sn: root_ref[0]._trigger_dup_alarm(s, "Pool"))
            self.root.after(50, self.refresh_ui)
            return

        # 池测试通过 → 立即放行（不等 MES）
        # SN已通过 in-memory 池检查，接受本次扫描。
        # 不再等待 MES/SQLite 慢查 — 扫描响应从 ~6s 降到 ~10ms。
        pool_add(sn)
        sqlite_add(sn, "", "PASS", "")
        state["stats"]["total"] += 1
        state["stats"]["pass"] += 1
        add_recent_sn(sn, "PASS", "", "", False, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":0})
        log(f"[scan] ✅ SN passed (pool clean): {sn}")
        # 语音反馈：通过 (在后台线程，不阻塞扫描)
        play_sn(sn)
        play_pass()
        # 自动装箱
        if root_ref[0]:
            root_ref[0].root.after(0, lambda s=sn: root_ref[0]._pack_sn_pass(s))
        self.root.after(50, self.refresh_ui)

        # 慢速后台检查 — 用于"later detection"（不阻塞、不弹窗）
        # 异步查询 MES + SQLite；若发现 NG/dup，把 SN 标记到对应内存池，
        # 后续重扫该 SN 时会被池命中并触发告警。
        # 关键约定：NG 检测 → _ng_pool；dup 检测 → _dup_pool，绝不混淆。
        def late_check():
            try:
                from concurrent.futures import ThreadPoolExecutor, wait
                with ThreadPoolExecutor(max_workers=3) as ex:
                    f_mes_ng = ex.submit(check_mes_ng, sn)
                    f_sqlite = ex.submit(check_sqlite, sn)
                    f_mes = ex.submit(check_mes, sn)
                    wait([f_mes_ng, f_sqlite, f_mes], timeout=3.5)
                    mes_ng = f_mes_ng.result(timeout=0) if f_mes_ng.done() else False
                    local_dup = f_sqlite.result(timeout=0) if f_sqlite.done() else False
                    mes_dup = f_mes.result(timeout=0) if f_mes.done() else False
                if mes_ng:
                    _ng_pool.add(sn)
                    log(f"[late-detect] flagged NG {sn}: mes_ng=True (added to _ng_pool)")
                elif local_dup or mes_dup:
                    _dup_pool.add(sn)
                    log(f"[late-detect] flagged DUP {sn}: local_dup={local_dup} mes_dup={mes_dup} (added to _dup_pool)")
            except Exception as e:
                log(f"[late-detect] error for {sn}: {e}")

        threading.Thread(target=late_check, daemon=True).start()
        # 不阻塞，立即返回，让队列继续处理下一个SN

        threading.Thread(target=slow_check, daemon=True).start()
        # 不阻塞，立即返回，让队列继续处理下一个SN

    def _handle_slow_check_result(self, sn, mes_ng, local_dup, mes_dup):
        """慢速检查结果在Tk主线程处理"""
        if state.get("skip_mes_check"):
            mes_ng, local_dup, mes_dup = False, False, False
        if mes_ng:
            log(f"⚠ MES NG历史: {sn}")
            state["stats"]["total"] += 1
            state["stats"]["fail"] += 1
            add_recent_sn(sn, "NG", "", "", False, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":1})
            pending_queue.append({"sn": sn, "channel": "", "errorcode": ""})
            # Voice in background thread (was: direct call blocked main thread 5-10s)
            mes_bridge_event(sn, "FAIL", "ng_history", None, "")  # 推送 NG历史 事件到新 MES
            threading.Thread(target=play_alert, args=("ng",), daemon=True).start()
            threading.Thread(target=lambda: _usb_guard.disable(), daemon=True).start()
            lock_ate()
            self._scanner_locked = True
            self._show_dup_alarm_window(sn, "NG")
            self.refresh_ui()
            return

        is_dup = False
        if local_dup:
            log(f"❌ 重码:Local → {sn}")
            state["stats"]["total"] += 1
            state["stats"]["pass"] += 1
            add_recent_sn(sn, "PASS", "", "", True, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":0})
            mes_bridge_event(sn, "FAIL", "dup", None, "")  # 推送 重码 事件到新 MES
            if root_ref[0]:
                root_ref[0].root.after(0, lambda s=sn: root_ref[0]._trigger_dup_alarm(s, "Local"))
            is_dup = True
        elif mes_dup:
            log(f"❌ 重码:MES → {sn}")
            state["stats"]["total"] += 1
            state["stats"]["pass"] += 1
            add_recent_sn(sn, "PASS", "", "", True, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":0})
            mes_bridge_event(sn, "FAIL", "dup", None, "")  # 推送 重码 事件到新 MES
            if root_ref[0]:
                root_ref[0].root.after(0, lambda s=sn: root_ref[0]._trigger_dup_alarm(s, "MES"))
            is_dup = True

        if not is_dup:
            pool_add(sn)
            sqlite_add(sn, "", "PASS", "")
            state["stats"]["total"] += 1
            state["stats"]["pass"] += 1
            add_recent_sn(sn, "PASS", "", "", False, {"sp":1,"sl":1,"sm":1,"np":0,"nl":0,"nm":0})
            log(f"✅ SN通过: {sn}")
            mes_bridge_event(sn, "PASS", "station_scan", None, "")  # 推送 PASS 事件到新 MES
            play_sn(sn)
            play_pass()  # 播报"SN + 扫码通过" - 跟随 _CURRENT_LANG
            self._pack_sn_pass()  # 自动装箱

            # 复测SN通过 → 从NG池移除所有记录
            if sn in self._ng_pending_recheck:
                self._ng_remove_from_pools(sn)
                self._ng_pending_recheck.discard(sn)

        self.refresh_ui()

    def _poll_loop(self):
        while True:
            if state["mode"] in ["running", "locked", "standby"]:
                poll_excel()
                process_queue()
            time.sleep(0.5)

    def append_log(self, msg):
        """追加消息到实时日志Text控件"""
        try:
            if hasattr(self, 'm_log') and self.m_log.winfo_exists():
                self.m_log.configure(state="normal")
                self.m_log.insert("end", msg + "\n")
                self.m_log.configure(state="disabled")
                self.m_log.see("end")
        except: pass

    def _record_ng_handling(self, sn, channel, errorcode, method):
        """记录NG处理方式和结果到SQLite"""
        try:
            conn = sqlite3.connect(NG_SQLITE)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ng_handling (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sn TEXT, channel TEXT, errorcode TEXT, method TEXT, time TEXT
                )
            """)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("INSERT INTO ng_handling(sn,channel,errorcode,method,time) VALUES(?,?,?,?,?)",
                        (sn, channel, errorcode, method, now))
            conn.commit(); conn.close()
            log(f"[ng_handle] recorded: sn={sn} method={method}")
        except: pass

    def _ng_remove_from_pools(self, sn):
        """从ng_pool移除SN（复测时用）"""
        global _ng_pool
        if sn in _ng_pool:
            _ng_pool.discard(sn)
            log(f"[ng_recheck] removed from ng_pool: {sn}")
        try:
            conn = sqlite3.connect(NG_SQLITE)
            cur = conn.cursor()
            cur.execute("DELETE FROM ng_pool WHERE sn=?", (sn,))
            conn.commit(); conn.close()
            log(f"[ng_recheck] removed from ng_pool table: {sn}")
        except: pass
        # 通知MES删除NG记录
        threading.Thread(target=self._delete_ng_from_mes, args=(sn,), daemon=True).start()

    def _delete_ng_from_mes(self, sn):
        """从MES NG注册表删除SN"""
        try:
            import urllib.parse
            url = f"{MES_API}/aging/ng_registry/delete?sn={urllib.parse.quote(sn)}"
            req = urllib.request.Request(url, method="DELETE")
            with urllib.request.urlopen(req, timeout=3) as resp:
                log(f"[ng_recheck] deleted from MES: {sn}")
        except Exception as e:
            log(f"[ng_recheck] MES delete error: {e}")

    def refresh_ui(self):
        if self.notebook is None:
            self.root.after(500, self.refresh_ui)
            return
        # S12 fix: removed per-refresh log() calls that produced 4 log lines/sec
        # (~14k/hour). The UI labels (m_pass, m_fail, m_pool, etc.) already show
        # the same state to the operator.
        self.m_pass.config(text=_T("pass_label") + ": " + str(state['stats']['pass']))
        self.m_fail.config(text=_T("fail_label") + ": " + str(state['stats']['fail']))
        self.m_dup.config(text=_T("dup_label") + ": " + str(len(_dup_pool)))
        self.m_pool.config(text=_T("pool_status").format(total=len(_sn_pool), ng=len(_ng_pool), dup=len(_dup_pool)))
        if state["locked"]:
            self.m_status.config(text=_T("status_label") + ": " + _T("locked"), fg="#ff4444")
        elif state["mode"] == "running":
            self.m_status.config(text=_T("status_label") + ": " + _T("running"), fg="#00ff00")
        else:
            self.m_status.config(text=_T("status_label") + ": " + _T("stopped"), fg="#ffcc00")
        for item in self.sn_tree.get_children():
            self.sn_tree.delete(item)
        count = 0
        for rec in recent_sns[:30]:
            c = rec.get("checks") or {}
            def icon(v): return "✅" if v == 1 else ("⏳" if v == 0 else "❌")
            tag = "ng" if rec["result"] in ["NG", "FAIL"] else "pass"
            self.sn_tree.insert("", 0, values=(rec["sn"][:16], rec["result"], icon(c.get("sp",0)), icon(c.get("sl",0)), icon(c.get("sm",0)), icon(c.get("np",0)), icon(c.get("nl",0)), icon(c.get("nm",0)), rec["time"]), tags=(tag,))
            count += 1
        # S12 fix: removed ui_refresh log (was called 2×/sec, ~7k lines/hour)
        self.sn_tree.tag_configure("ng", foreground="#ff0000", font=("Microsoft JhengHei", 9, "bold"))
        self.sn_tree.tag_configure("pass", foreground="#006600", font=("Microsoft JhengHei", 9))
        if recent_sns:
            self.m_current.config(text=_T("current_sn") + ": " + recent_sns[0]["sn"] + " \u2192 " + recent_sns[0]["result"], fg="#38bdf8")
        # 刷新四列资源表
        for item in self.r_all_tree.get_children():
            self.r_all_tree.delete(item)
        sn_pool_list = sorted(_sn_pool, reverse=True)[:50]
        ng_pool_list = sorted(_ng_pool, reverse=True)[:50]
        sn_reg_list = []
        ng_reg_list = []
        try:
            conn = sqlite3.connect(DB_FILE)
            for r in conn.execute("SELECT sn FROM sn_records ORDER BY id DESC LIMIT 50").fetchall():
                sn_reg_list.append(r[0])
            conn.close()
        except: pass
        try:
            conn = sqlite3.connect(NG_SQLITE)
            for r in conn.execute("SELECT sn FROM ng_pool ORDER BY id DESC LIMIT 50").fetchall():
                ng_reg_list.append(r[0])
            conn.close()
        except: pass
        max_len = max(len(sn_pool_list), len(ng_pool_list), len(sn_reg_list), len(ng_reg_list))
        for i in range(max_len):
            row = (
                sn_pool_list[i] if i < len(sn_pool_list) else "",
                ng_pool_list[i] if i < len(ng_pool_list) else "",
                sn_reg_list[i] if i < len(sn_reg_list) else "",
                ng_reg_list[i] if i < len(ng_reg_list) else "",
            )
            self.r_all_tree.insert("", 0, values=row)
        if root_ref[0]:
            self.root.after(500, self.refresh_ui)

if __name__ == "__main__":
    _instance_mutex = acquire_single_instance("MANU_PALLET_BINDING_AGENT")
    if _instance_mutex is None: raise SystemExit("Pallet Binding Agent is already running")
    log(f"ATE质量中心启动")
    log(f"Tkinter version: {tk.TkVersion}")
    init_db()
    log("db init done")
    load_state()
    log("load_state done")
    init_ng_sqlite()
    log("ng sqlite init done")
    init_station_config()
    log("station_config init done")
    # 首次运行检测：检查sn_records是否已有数据
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sn_records")
        sn_count = c.fetchone()[0]
        conn.close()
        is_first_run = (sn_count == 0)
    except:
        is_first_run = True

    if is_first_run:
        log("[excel] 首次运行，开始加载历史数据...")
        load_all_ng_from_excel()  # 加载所有Excel到pool + SQLite
        _load_latest_excel_ng()  # 加载最新文件到内存池
        log(f"ng pool loaded: {len(_ng_pool)} NGs in memory (latest file)")
    else:
        log(f"[excel] 已跳过加载（sn_records已有 {sn_count} 条记录）")
    _silent_mode = False  # 加载完成后开启报警和认证
    _ng_pool.update(load_ng_from_sqlite())  # 启动时从5-10年库加载NG到内存池
    start_api()
    log("api started")
    start_ws_server()
    log("ws server started")
    threading.Thread(target=packaging_heartbeat_worker, daemon=True, name="packaging-heartbeat").start()
    log("3D heartbeat started")
    register_ip_to_mes()   # 向MES注册本工位IP
    log("ip registered")
    # Do not open a browser from the production station agent.
    ensure_single_instance()
    log("creating Tk root...")
    root = tk.Tk()
    log("root created")
    log("about to create ATEQualityCenter...")
    root.update()
    app = ATEQualityCenter(root)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from station_retest import install_station_retest_panel
    install_station_retest_panel(root, MES_NEW_STATION, MES_NEW_API, test_station=False)
    log("app created")
    # 显示Excel读取结果 (UI + console)
    if _excel_load_result:
        banner = "=" * 60
        log(banner)
        log("📊 EXCEL READING RESULTS:")
        for fname, total, ng in _excel_load_result:
            log(f"   {fname}: {total} rows / {ng} NG")
        log(f"   Latest file: {_excel_latest_result}")
        log(banner)
        app.append_log(banner)
        app.append_log("📊 Excel读取完成:")
        for fname, total, ng in _excel_load_result:
            app.append_log(f"   {fname}: {total} 条 / {ng} NG")
        app.append_log(f"   最新文件已加载 {_excel_latest_result}")
        app.append_log(banner)
    log("entering mainloop")
    root.mainloop()
    log("mainloop exited")
