# 瑞晶越南工厂 · 新工厂布局图 — 1m×1m 网格分区报告

## 1. 数据来源
- **DWG 源文件**：`dc\新工厂布局图 WMS.dwg`（AutoCAD 2018 / AC1032，10.1 MB）
- **转换**：LibreDWG v0.13.4 (WASM) → `dc\dwgwork\layout.dxf`（80 MB，117,407 个图元）
- 厂房主体：**62.02 m × 56.30 m**（西侧主厂房）+ 东侧辅房（约 9 m 宽，含 Intelligent SMT Reel Rack、Electronic Component Control System 等）
- 总图幅：74.02 m × 60.0 m（含右侧尺寸标注带与左侧图框）

## 2. 网格定义（1m × 1m）
| 参数 | 值 |
|---|---|
| 网格原点 | 厂房西南角 (191382.6, 84195.7) mm |
| 列 | X01 – X72（自西向东，72 列） |
| 行 | Y01 – Y57（自南向北，57 行） |
| 单元总数 | **4104 个**（每格 1 m × 1 m） |
| 单元编号 | `X##-Y##`（列-行），如 X05-Y12 |

## 3. 自动分区结果（按 DWG 内文字标注自动聚类）
| 区域 | 网格数 | 面积(m²) | 主要设备/标注 |
|---|---|---|---|
| 货架/仓储 | 0 | 0 m² | Storage Rack 1–9、样品柜、文件柜、冰箱、治具架 |
| 老化测试 | 604 | 604 m² | Burn-in、BI Pending/Finish Line、耐压、Hi-pot、Rattle |
| 组装装配 | 457 | 457 m² | Assembly Line、点胶、超声波焊接、Depaneling、线束 |
| DIP插件 | 275 | 275 m² | DIP、Wave soldering、Odd Form Insert |
| 通道物流 | 789 | 789 m² | 门、货梯、楼梯、ESD 门、风淋室、滚轮门 |
| SMT贴片 | 254 | 254 m² | NPM-D3A、SPI、GKG 印刷机、Reflow、上板机 |
| 包装 | 260 | 260 m² | Packing、Carton Seal、称重、贴标、PE 袋 |
| IQC检验 | 200 | 200 m² | 检验1/2、待检/合格/不合格区、LCR、高度规 |
| 成品仓储 | 153 | 153 m² | FG Temp Storage、Pallet 托盘阵 |
| 维修工具 | 99 | 99 m² | Repair ROOM、TOOL Storage、维修台、Power Box |
| AOI检测 | 96 | 96 m² | AOI、3D AOI、Visual Insp、缺陷标记 |
| 生活区 | 84 | 84 m² | Tea Room、男女更衣室 |

（其余未列区域为未标注的边角/辅助格）

## 4. 交付文件（`dc\dwgwork\`）
| 文件 | 用途 |
|---|---|
| `plant_grid_1m_map.png` | 布局图 + 1m 网格 + 分区着色（2160×1710 px，可打印） |
| `plant_grid_1m_map.svg` | 矢量版（可放大不失真，标注可选中） |
| `plant_grid_allocation.csv` | 4104 行分配表：cell_id / 坐标 / 自动分区 / 手动分配栏 / 格内设备 |
| `plant_grid_allocation.json` | 机器可读：网格元数据 + 30 个分区矩形 + 全部单元 |
| `plant_grid_allocator.html` | **交互式分配工具**：点击格子分配区域、图例选择、导出 CSV/JSON、可导入回填 |

## 5. 使用方法
1. 打开 `plant_grid_allocator.html`（浏览器直接打开，无需联网）。
2. 右侧选择区域（如"成品仓储区"），在地图上点击任意 1m 格子完成分配（再点一次取消）。
3. 完成后点「导出 CSV / 导出 JSON」保存分配结果；下次打开可导入继续编辑。

## 6. 坐标换算
- 任意网格单元 X##-Y## 对应厂房内绝对坐标（西南角为原点）：
  - X = 191382.6 + (col-1)*1000 mm
  - Y = 84195.7 + (row-1)*1000 mm
- 换算回 DWG 原坐标：加上上述原点即可，与 AutoCAD 中 `ID` 查询一致。
