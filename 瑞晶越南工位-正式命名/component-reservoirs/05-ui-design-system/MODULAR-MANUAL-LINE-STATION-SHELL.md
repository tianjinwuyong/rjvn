# 模块化手动线 StationShell 方案

状态：设计建议，尚未接管任何正式工站入口。  
范围：手动线 01–13；Tk、Qt/PySide6、Streamlit 三种 UI 家族。  
原则：StationShell 只负责布局、呈现和交互编排，不拥有 MES 决策、NG、维修、权限、工艺路线或设备业务规则。

## 1. 盘点结论

当前已经具备可复用基础，但缺少统一的页面编排层：

- `station_ui_primitives.py` 已有颜色、1366×768、Treeview、扫码焦点、新事件提示等基础能力。
- `station_arrival_ui.py` 已有只读 Product Gate，以及 Tk/Streamlit 呈现适配器。
- `station_repair_workflow.py`、`station_retest.py` 已有维修和复测能力，但目前通常以独立窗口、分散按钮或页面块出现。
- `station_alarm.py`、`station_scan_alarm.py` 已实现“只提示新事件一次”，应继续作为告警行为权威。
- `station_i18n.py`、`station_language.py` 提供三语言机制，但字典存在乱码、重复和运行时漏译风险；外壳不能继续依赖遍历控件猜测原文作为长期方案。
- 01–02 是 Streamlit；03–13 以 Tk 为生产主界面，另有 Qt/3D 观察界面。多个正式入口仍分别设置 `geometry()`、颜色和工具栏。
- 03–06 的 Product Gate 后端证据尚缺，只能显示 `UNKNOWN / BACKEND GAP`，外壳不得把它们渲染成 ALLOW。

## 2. StationShell 的职责边界

StationShell 接收只读的 `StationViewModel` 和显式命令回调：

```text
Station runtime / MES / device adapters
        │ immutable snapshot + explicit command callbacks
        ▼
StationShell
 ├─ Header / identity
 ├─ Alarm banner
 ├─ Product context
 ├─ Production workspace slot
 ├─ Exception / repair drawer
 └─ Health strip
```

它不应：

- 自己推断 ALLOW、PASS、NG、下一工站或维修权限；
- 直接访问数据库、扫描器、MES 或设备；
- 因历史告警重新播放声音、闪烁或抢焦点；
- 在语言切换时修改业务状态值；
- 把 Qt/3D 观察界面变成第二套生产真相。

## 3. 统一桌面布局

目标尺寸：1366×768；最小 1024×700；页面本身不纵向滚动。

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ 68px Header: 工厂 / 线别 / 工站 / Agent版本 │ WO / 产品 │ 操作员 │ 中 EN VI │
├──────────────────────────────────────────────────────────────────────────┤
│ 48px Alarm Banner: 新告警一次提示；历史告警静态；无告警时仍保留高度         │
├────────────── 22% ──────────────┬──────────── 56% ────────────┬── 22% ──┤
│ Product Context                 │ Production Workspace         │ Context │
│ · Product Gate                  │ · 工站专属主流程              │ · Result│
│ · SN / Motherboard / Case       │ · 扫码输入                    │ · Next  │
│ · WO / route revision           │ · 设备/槽位/绑定可视化         │ · Policy│
│ · Reason / Next action          │ · 唯一主操作                  │ · Audit │
├─────────────────────────────────┴──────────────────────────────┴─────────┤
│ 54px Health: Scanner │ Equipment/Data source │ MES │ Outbox │ Clock │ IP │
└──────────────────────────────────────────────────────────────────────────┘
                                                ┌──────────────────────────┐
                                                │ Exception/Repair Drawer  │
                                                │ NG → receipt → repair →  │
                                                │ return → retest → close  │
                                                └──────────────────────────┘
```

### 视觉权重

1. 中央生产主流程永远占最大面积；操作员不需要在资源页、维修页和主流程之间来回找当前任务。
2. Product Gate 位于左侧、与扫码相邻，先回答“这个产品能不能在本站做”。
3. 右侧只显示当前结果、原因、下一步和必要策略，不显示完整历史表。
4. 异常/维修使用右侧抽屉，打开后不能遮住扫码输入和当前结果。
5. 健康条固定在底部，避免连接状态散落在标题、状态栏和弹窗中。

## 4. 可复用组件

### 4.1 `StationHeader`

字段：`plant`、`lineCode`、`stationCode`、本地 `hostIp`、MES 观察到的 `sourceIp`、Agent 版本、操作员、班次。  
操作：三语言切换、帮助、诊断、受控设置。语言按钮始终可见，不与标题重叠。

### 4.2 `AlarmBanner`

状态：`normal`、`attention`、`new-ng`、`historical-ng`、`offline`、`unauthorized`。  
仅消费 `station_alarm.py` / `station_scan_alarm.py` 已去重后的呈现事件。新事件短提示一次，随后成为静态状态。

### 4.3 `ProductContextPanel`

复用 Product Gate 契约：`ALLOW`、`HOLD`、`REJECT`、`REPAIR_ROUTE`、`COMPLETED`、`UNKNOWN`。  
固定信息顺序：产品身份 → Gate → 原因 → 下一步 → WO/route revision → Trace。  
颜色必须复用：ALLOW `#22D887`、HOLD `#F2B84B`、REJECT `#F05252`、REPAIR_ROUTE `#18C6D9`、COMPLETED `#4C8DFF`、UNKNOWN `#9EB0BC`。

### 4.4 `ProductionWorkspace`

这是唯一允许工站定制的主插槽。各站仅提供专用内容：

- 01 PDA：物料/工单扫描步骤；
- 02 AOI：质量结果与缺陷确认；
- 03 ICT、04 FCT：3×4 母板/子板结果；
- 05 分板：母板拆分和立即取出 NG；
- 06 外壳绑定：母板/子板/外壳关系；
- 07、10、11 ATE：8-SN 布局和最后周期结果；
- 08 超声：扫描、设备参数和 NG 标记；
- 09 老化：7 柜、柜号/槽位/SN/最后记录；
- 12 外箱绑定：48-SN 箱格；
- 13 栈板绑定：栈板/外箱位置。

### 4.5 `ResultActionPanel`

固定显示：当前状态、原因、下一动作、是否需要授权、关联事件/工单。  
只保留一个主操作；复测、豁免、报废、移除等例外动作进入受控菜单或抽屉。

### 4.6 `ExceptionRepairDrawer`

统一闭环：Confirmed NG → 确认送修 → 维修收单 → 维修动作 → 返回收单 → 复测授权 → Revival/关闭。  
抽屉显示 SLA、负责人、目的地、证据和审计引用；所有写操作仍由现有维修共享运行时执行。

### 4.7 `HealthStrip`

固定字段：Scanner、Equipment/Data Source、MES、Outbox、Clock、Agent、Host IP。  
每项同时显示文本和颜色，不允许仅用圆点表达。离线状态保持琥珀色，不应弹窗循环提示。

### 4.8 `DiagnosticsDrawer` 与 `AuthorizationDialog`

诊断抽屉只读并可复制结果；授权弹窗必须显示动作、产品、原因、所需角色、操作者和超时。关闭后恢复扫码焦点。

## 5. 三语言策略

建议从“遍历当前控件文本再替换”迁移到稳定 key：

```python
text("shell.header.operator", locale)
text("gate.reason", locale)
text("repair.send", locale)
```

要求：

- zh/en/vi 字典同时提交，缺 key 在预览/测试中直接报错；
- 动态状态使用结构化参数，不拼接中文句子；
- ATE 发音固定为 A-T-E，AOI 固定为 A-O-I；
- SN、WO、IP、时间戳使用等宽字体；
- 不把后端状态码翻译后再回传。

## 6. 建议新增文件

位置：`瑞晶越南工位-正式命名/004-手动线/`

| 文件 | 责任 |
|---|---|
| `station_shell_contract.py` | `StationViewModel`、健康状态、告警展示状态、显式命令回调协议；无 UI 工具包依赖 |
| `station_shell_tk.py` | Tk 版 StationShell、固定网格、抽屉、主插槽与焦点恢复 |
| `station_shell_qt.py` | Qt/PySide6 只读/3D 适配壳；复用同一 contract，不复制业务规则 |
| `station_shell_streamlit.py` | 01–02 的 Streamlit 布局适配器；保持 Product Gate/维修契约一致 |
| `station_shell_components.py` | Header、AlarmBanner、HealthStrip、ResultActionPanel 等 Tk 组合组件 |
| `station_shell_i18n.py` | StationShell 稳定 key 的 zh/en/vi 字典和缺 key 检查 |
| `station_shell_preview.py` | 写阻断的状态图库：idle、processing、PASS、new NG、historical NG、offline、repair、unauthorized |
| `tests/test_station_shell_contract.py` | contract、状态枚举、无业务推断测试 |
| `tests/test_station_shell_i18n.py` | 三语言完整性、ATE/AOI 发音、乱码检测 |
| `tests/test_station_shell_layout.py` | 1366×768 区域尺寸、抽屉不遮扫码/结果、最小控件高度 |

## 7. 建议修改的共享 UI 文件

这些修改应分阶段进行，并且不直接改变正式入口：

1. `station_ui_primitives.py`
   - 增加 spacing/type/motion token；保留现有函数签名。
   - 增加 toolkit-neutral 的 gate/state 色映射常量。
2. `station_arrival_ui.py`
   - 把 Product Gate 的只读数据到呈现映射抽成小组件供 Shell 复用。
   - 保持 `ProductGateComponent` 和 Streamlit 函数兼容。
3. `station_i18n.py`
   - 逐步转为稳定 key；先新增校验，不一次性删除旧字典。
4. `station_language.py`
   - 保留兼容层，但新 Shell 不再依赖控件遍历翻译。
5. `station_repair_workflow.py`
   - 增加可嵌入 drawer 的 presenter；现有独立窗口/Streamlit 函数继续可用。
6. `station_retest.py`
   - 提供只读状态卡与授权命令回调，避免各站重新布局按钮。

## 8. 正式工站入口的后续接入顺序

本方案当前不修改以下入口。建议未来采用“一个试点、验证、再扩展”：

1. 07 组装 ATE：共享组件最完整，作为首个 Tk 试点。
2. 10 高压 ATE、11 包装 ATE：与 07 同族，迁移成本最低。
3. 08 超声、09 老化、12 外箱、13 栈板：保留各自中央工作区。
4. 03 ICT、04 FCT、05 分板、06 外壳绑定：先补齐 Product Gate 后端证据，UI 仍显示 UNKNOWN 直到完成。
5. 01 PDA、02 AOI：最后用 Streamlit adapter 接入，验证小屏和页面刷新行为。

Qt/3D 视图仅在同一个 ViewModel 上做观察投影，不另建状态机。

## 9. 验收要求

- 每次只启动一个本地 GUI Agent；使用 `UI_PREVIEW=1`，禁止生产写入。
- 1366×768 下主流程、扫码、结果、Product Gate、健康条同时可见。
- 中文、英文、越南语分别截图，无乱码、截断和按钮重叠。
- 新 NG 只提示一次；历史 NG 静态且无声音。
- 抽屉打开时扫码和结果仍可见，关闭后恢复扫码焦点。
- MES 离线、无权限、后端 gap 均不可显示为成功或 ALLOW。
- 所有写动作由已有 runtime 回调执行，并保留 reason、operator、version/evidence/audit。

## 10. 视觉理由

- 使用稳定的 68/48/主区/54 水平骨架，状态变化时页面不跳动。
- 22/56/22 将视觉重量放在生产主流程，而不是平均分配给辅助卡片。
- Product Gate 靠近输入，结果/下一步靠近主流程，符合“扫描 → MES 判定 → 执行”的阅读方向。
- 异常和维修在抽屉中完成闭环，既不隐藏，也不长期挤占生产空间。
- 统一的冷中性色只承载结构，语义色仅用于状态；避免每个工站形成自己的颜色语言。
- 三种 UI 工具包共用 contract 和状态词，减少视觉相似但业务含义不同的风险。
