# -*- coding: utf-8 -*-
"""AOI Streamlit UI - delegates data layer to aoi_core."""
import json
import sys
import time
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
AUTO = BASE.parent.parent / "002-自动线"
if AUTO.exists():
    sys.path.insert(0, str(AUTO))

from aoi_core import AoiCore, STATION_CODE
from station_retest import render_streamlit_retest
from station_repair_workflow import render_streamlit_repair_workflow
from station_arrival_ui import render_streamlit_product_gate
from station_ui_primitives import render_streamlit_station_tabs

core = AoiCore()
MES_API = core.mes_api

st.set_page_config(page_title="AOI KPI", page_icon="🔍", layout="wide")
render_streamlit_retest(st, STATION_CODE, MES_API, test_station=True)
render_streamlit_station_tabs(st, STATION_CODE)
render_streamlit_repair_workflow(st, STATION_CODE, MES_API, "AOI质量")

# Background sync (runs once per rerun)
mysql_ok, mysql_err, new_rows = True, None, 0
try:
    last_id, new_rows, mysql_err = core.process_mysql(500)
except Exception as exc:
    mysql_ok, mysql_err = False, str(exc)

heartbeat_ok = core.heartbeat()
core.sync_outbox(20)

snap = core.snapshot()
render_streamlit_product_gate(st, backend_gap=True)

st.title("🔍 AOI 质量工位 KPI")
st.caption("MySQL pcb_detection.detection_board · Heartbeat → MES/3D · 无复测")

cols = st.columns(6)
cols[0].metric("工位心跳", "ONLINE" if heartbeat_ok else "OFFLINE")
cols[1].metric("MySQL", "CONNECTED" if mysql_ok else "OFFLINE")
cols[2].metric("检测 SN", snap['total'])
cols[3].metric("PASS", snap['passed'])
cols[4].metric("确认不良", snap['confirmed'])
cols[5].metric("重复编码", snap['duplicates'])

if mysql_err:
    st.error(f"MySQL 读取失败，保持拦截：{mysql_err}")
else:
    st.success(f"MySQL 已连接 · 本轮新增 {new_rows} · Last ID {snap['mysql_last_id']}")

st.subheader("最近检测记录")
if snap['recent']:
    st.dataframe([
        {"SN": r['sn'], "判定": r['decision'],
         "时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r['detected_at'] / 1000))}
        for r in snap['recent'][:30]
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
