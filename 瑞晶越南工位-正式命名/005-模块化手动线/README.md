# 模块化手动线 / Modular Manual Line

这是与 `004-手动线` 隔离的新工站系列，不替换现有正式入口。

## 核心边界

- 正常产线主流程与 NG 维修路由分离。
- `stations.json` 定义 13 个工站、下一工序、专用适配器和 NG 策略。
- Agent 仅展示并执行 MES 的决策；MES 拥有产品状态、权限、策略版本、返回路线和审计真相。
- 默认启动为预览模式，所有生产写入按钮禁用。

## 预览

```powershell
python modular_manual_line.py --station mod_manu_assembly_ate
```

可用工站代码由 `python modular_manual_line.py --help` 列出。正式接入前必须完成设备适配器、MES Product Gate、身份鉴权、三语言和无生产写入烟雾测试。
