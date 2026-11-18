# 分板机 3-NG 隔离闭环测试报告

> 测试数据全部使用 `TEST-*` 编号，未写入生产 MES。

## 批次

- 批次：`TEST-SHIP-003-NG`
- 回修箱 QR：`TEST-BOX-REPAIR-001`
- 数量：3
- 测试时间：2026-08-07

## SN 结果

| SN | 原来源 | 回修工单 | PDA 接收 | 返回工站 | 复测 | 最终状态 |
|---|---|---|---|---|---|---|
| `TEST-DEP-ICT-001` | ICT | `TEST-WO-001` | 组长已扫描确认 | ICT | PASS | CLOSED |
| `TEST-DEP-ICT-002` | ICT | `TEST-WO-002` | 组长已扫描确认 | ICT | PASS | CLOSED |
| `TEST-DEP-FCT-001` | FCT | `TEST-WO-003` | 组长已扫描确认 | FCT | PASS | CLOSED |

## 验证结果

- MES 发出维修交接：通过
- 回修站箱 QR/SN 扫描接收：通过
- 维修完成通知组长 PDA：通过
- PDA 扫描确认领取：通过
- ICT/FCT 原路线返回：通过
- ICT/FCT 复测 PASS：通过
- MES 恢复后 Outbox 补传：18/18
- 重复事件：0
- 冲突：0
- 共享组件测试：35/35 通过

## 结论

隔离测试闭环完成。该报告不代表真实工站或生产 MES 已执行写入测试。
