# -*- coding: utf-8 -*-
"""PDA Streamlit UI - delegates data layer to pda_core."""
import json, sys, time
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
AUTO = BASE.parent.parent / "002-自动线"
if AUTO.exists():
    sys.path.insert(0, str(AUTO))

from pda_core import PdaCore
from station_retest import render_streamlit_retest
from station_repair_workflow import render_streamlit_repair_workflow
from station_arrival_ui import render_streamlit_product_gate
from station_ui_primitives import render_streamlit_station_tabs

core = PdaCore()
MES_API = core.mes_api

st.set_page_config(page_title="PDA 扫码输入", page_icon="📱", layout="wide")
render_streamlit_retest(st, "manu_pda", MES_API, test_station=False)
render_streamlit_station_tabs(st, "manu_pda")
render_streamlit_repair_workflow(st, "manu_pda", MES_API, "PDA扫码上料")

# Background sync (runs once per rerun)
core.sync_ng_cache(500)
core.sync_outbox(20)
core.heartbeat()

st.title("📱 PDA 扫码输入设备")
st.subheader("进料二维码绑定工单 / Incoming QR → Work Order")

snap = core.snapshot()
render_streamlit_product_gate(st, backend_gap=True)
with st.form("pda_workorder_binding", clear_on_submit=True):
    wo = st.text_input("工单号 / Work Order")
    qr = st.text_input("扫描来料二维码 / Incoming QR")
    submitted = st.form_submit_button("绑定并放行 / BIND")

if submitted:
    try:
        result = core.bind_workorder(wo, qr)
        st.success(f"绑定成功：{result.get('qrCode', qr)} → {result.get('workOrderCode', wo)}")
    except Exception as exc:
        st.error(f"绑定失败：{exc}")

st.caption("PDA 是 MES 扫码入口：心跳、工单绑定和二维码路由均由 MES 监督；MES 不可用时禁止绑定放行。")

a, b, c, d = st.columns(4)
a.metric("MES ACTIVE NG", snap['active_ng_count'])
b.metric("绑定记录", len(snap['bindings']))
c.metric("实时扫描", len(snap['scans']))
d.metric("MES Outbox", len(snap['outbox']))

st.subheader("最近绑定 / Bindings")
if snap['bindings']:
    st.dataframe([
        {"时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(b['bound_at'] / 1000)),
         "工单": b['work_order_code'], "二维码": b['qr_code'], "操作员": b['bound_by']}
        for b in snap['bindings'][:20]
    ], use_container_width=True, hide_index=True)

st.subheader("实时扫码 / Live Scans")
if snap['scans']:
    st.dataframe([
        {"时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s['received_at'] / 1000)),
         "SN": s['sn'], "目标": s['destination_station'] or '-', "类型": s['scan_type']}
        for s in snap['scans'][:30]
    ], use_container_width=True, hide_index=True)

with st.expander("MES 通信 / Outbox"):
    st.dataframe([
        {"事件": o['event_id'][:16], "类型": json.loads(o['payload']).get('type', '?'),
         "创建": o['created_at'], "重试": o['attempts'], "错误": (o['last_error'] or '')[:50]}
        for o in snap['outbox'][:20]
    ], use_container_width=True, hide_index=True)

with st.expander("修改记录 / Software Change Log"):
    st.dataframe([
        {"编号": c['change_id'], "版本": c['version'], "组件": c['component'],
         "原因": c['reason'], "时间": c['changed_at']}
        for c in snap['changes']
    ], use_container_width=True, hide_index=True)

time.sleep(2)
st.rerun()
