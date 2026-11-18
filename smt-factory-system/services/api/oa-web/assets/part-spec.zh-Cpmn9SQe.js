const t=[{id:"spec",title:"SPEC 判定规则（专章）",sections:[{id:"spec-prereq",title:"使用前提：表格要有这三列",body:`
<p>系统通过<strong>表头文字</strong>自动识别「哪一列是标准、哪一列是实测值、哪一列写判定结果」。三列都靠关键词匹配，与列的先后位置无关。</p>
<table>
<thead><tr><th>列</th><th>表头需要包含这些字</th></tr></thead>
<tbody>
<tr><td>标准列（SPEC）</td><td><code>spec</code>、规格、标准、判定标准、技术要求、公差、要求</td></tr>
<tr><td>实测值列</td><td>实测、测量、实测值、测量值、数值、读数、检验值</td></tr>
<tr><td>判定列</td><td>判定、结论、结果、合格、是否</td></tr>
</tbody>
</table>
<blockquote><strong>最关键的一条：</strong>表格里<strong>必须有「判定」列</strong>，否则整张表会被系统<strong>跳过、完全不处理</strong>（这是为了避免误改模板里那些无关的排版表格）。</blockquote>
<p>识别时会自动跳过表头行（支持<strong>双行合并表头</strong>，例如 Excel 里「实测值」跨两列、「白班 / 夜班」为第二行的情况）。</p>
<p>导入 Excel 后，合并单元格会转成正常的跨列跨行，不影响识别。</p>
`},{id:"spec-syntax",title:"七类 SPEC 写法（含示例）",body:`
<p>标准列里的写法按下面<strong>固定优先级</strong>依次尝试，命中即返回。写对任意一类即可。</p>

<h4>① 文字单边</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>不小于5</code>、<code>不低于5</code></td><td>≥ 5（含 5）</td></tr>
<tr><td><code>不大于10</code>、<code>不高于10</code></td><td>≤ 10（含 10）</td></tr>
<tr><td><code>大于等于5</code>、<code>大等于5</code></td><td>≥ 5（含 5）</td></tr>
<tr><td><code>小于等于10</code>、<code>小等于10</code></td><td>≤ 10（含 10）</td></tr>
<tr><td><code>大于5</code>、<code>高于5</code></td><td>&gt; 5（不含 5）</td></tr>
<tr><td><code>小于10</code>、<code>低于10</code></td><td>&lt; 10（不含 10）</td></tr>
</tbody>
</table>
<blockquote><strong>注意：</strong>文字单边<strong>只取它遇到的第一个数字</strong>。写成「不小于5且不大于10」，系统只取 5 作为下限，<strong>上限会被忽略</strong>。双边限请改用范围写法（见 ②）。</blockquote>

<h4>② 范围</h4>
<p>连接符支持六种：<code>-</code>、<code>~</code>、<code>～</code>、<code>到</code>、<code>—</code>、<code>–</code>，以及<strong>全角逗号</strong>「<code>，</code>」。</p>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>5-10</code>、<code>5~10</code>、<code>5到10</code>、<code>5，10</code></td><td>5 ≤ 值 ≤ 10</td></tr>
<tr><td><code>10mm-20mm</code></td><td>10 ≤ 值 ≤ 20（连接符两侧可带单位）</td></tr>
<tr><td><code>10-5</code></td><td>自动纠正为 5 ~ 10</td></tr>
</tbody>
</table>
<blockquote><strong>注意：</strong>连接符两侧不要出现 <code>min</code> / <code>max</code> 字样，否则会被当成最大最小值（见 ④）。</blockquote>

<h4>③ 不等号</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>≥5</code>、<code>&gt;=5</code></td><td>≥ 5（含 5）</td></tr>
<tr><td><code>≤10</code>、<code>&lt;=10</code></td><td>≤ 10（含 10）</td></tr>
<tr><td><code>&gt;5</code></td><td>&gt; 5（不含 5）</td></tr>
<tr><td><code>&lt;10</code></td><td>&lt; 10（不含 10）</td></tr>
</tbody>
</table>
<blockquote><strong>注意（最容易踩）：</strong>不等号<strong>必须写在最前面</strong>。<code>≥5</code> 可以，写成「直径≥5」「L≥5」这种<strong>前面带文字的会直接解析失败</strong>。高/宽/长等前缀请另起一列或写进项目名称里。</blockquote>

<h4>④ 最大值 / 最小值</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>10max</code>、<code>max 10</code>、<code>max. 10</code></td><td>≤ 10</td></tr>
<tr><td><code>2min</code>、<code>min 2</code>、<code>min. 2</code></td><td>≥ 2</td></tr>
</tbody>
</table>
<p>不分大小写，写在数字前或后都可以。</p>

<h4>⑤ ± 公差</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>1.2±0.1</code></td><td>1.1 ~ 1.3</td></tr>
<tr><td><code>1.2±0.1mm</code></td><td>1.1 ~ 1.3（± 后带单位可以）</td></tr>
<tr><td><code>100±5%</code></td><td>95 ~ 105（百分比按基准值折算）</td></tr>
</tbody>
</table>
<blockquote><strong>注意：</strong><code>±</code> 前面必须是<strong>纯数字</strong>。写成「1mm±0.1」会因为中间夹了单位而<strong>解析失败</strong>。</blockquote>

<h4>⑥ 上下偏差（工程图纸写法）</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>10(+0.5/0.2)</code></td><td>10.2 ~ 10.5</td></tr>
<tr><td><code>10(+0.5,-0.2)</code></td><td>9.8 ~ 10.5</td></tr>
<tr><td><code>10(+0.5，0.2)</code></td><td>10.2 ~ 10.5（中文括号、全角逗号都可以）</td></tr>
</tbody>
</table>
<p>括号内两个数分别代表上偏差、下偏差，用 <code>/</code> 或 <code>,</code> 分隔。下偏差<strong>漏写正负号时自动按正数处理</strong>。</p>
<blockquote><strong>注意：</strong>偏差<strong>必须带括号</strong>。写成 <code>100+0.5/-0.2</code>（无括号）会解析失败。</blockquote>

<h4>⑦ 乘方（科学计数）</h4>
<table>
<thead><tr><th>写法</th><th>含义</th></tr></thead>
<tbody>
<tr><td><code>1^3</code></td><td>1000</td></tr>
<tr><td><code>2^10</code></td><td>1024</td></tr>
</tbody>
</table>
<blockquote><strong>注意：</strong>只认 <code>^</code>，<strong>不认 <code>1e3</code></strong> 这种科学计数写法。</blockquote>
`},{id:"spec-tolerance",title:"容错规则（写歪了也能认）",body:`
<p>下面这些不规范写法，系统会自动纠正后再解析：</p>
<table>
<thead><tr><th>情况</th><th>处理</th><th>例子</th></tr></thead>
<tbody>
<tr><td>半角逗号后跟 <strong>3 位数字</strong></td><td>当作千分位，去掉逗号</td><td><code>1,000</code> → 1000</td></tr>
<tr><td>半角逗号后跟 <strong>1~2 位数字</strong></td><td>当作欧洲式小数点</td><td><code>1,5</code> → 1.5</td></tr>
<tr><td>全角「＞=」「＜=」</td><td>归一为 <code>&gt;=</code> <code>&lt;=</code></td><td>保留含边界语义</td></tr>
<tr><td>全角「％」</td><td>归一为 <code>%</code></td><td>避免被当成绝对公差</td></tr>
<tr><td>数字前后有空格、单位、文字</td><td>自动跳过取数字</td><td><code>厚度 5 mm</code> → 取到 5</td></tr>
</tbody>
</table>
<blockquote><strong>注意：</strong>括号内的半角逗号<strong>不适用</strong>上面两条规则（它是上下偏差的分隔符），例如 <code>10(+0.5,0.2)</code> 不会被误改。</blockquote>
`},{id:"spec-unsupported",title:"明确不支持的写法",body:`
<p>下面这些写法系统<strong>不会猜</strong>，一律转人工处理（不会误判成不合格）：</p>
<table>
<thead><tr><th>写法 / 情况</th><th>结果</th></tr></thead>
<tbody>
<tr><td>全角数字（如 <code>５</code>、<code>１２３</code>）</td><td>解析失败（只认半角数字）</td></tr>
<tr><td><code>1e3</code> 这类科学计数</td><td>解析失败（请改用 <code>1^3</code>）</td></tr>
<tr><td>不等号写在中间，如「直径≥5」</td><td>解析失败（不等号必须写在最前）</td></tr>
<tr><td><code>1mm±0.1</code>（± 前夹单位）</td><td>解析失败</td></tr>
<tr><td><code>100+0.5/-0.2</code>（偏差无括号）</td><td>解析失败</td></tr>
<tr><td><code>直径5</code> 这类纯文字无判定意义</td><td>解析失败</td></tr>
<tr><td>只写了<strong>一个数字</strong>，如 <code>5</code></td><td><strong>不自动判定</strong>（不知道是上限还是下限）→「请指定公差或上下限」</td></tr>
</tbody>
</table>
`},{id:"spec-when",title:"什么时候会自动判定",body:`
<p>系统<strong>不会一边打字一边判</strong>，而是在下面这些时点批量执行：</p>
<ol>
<li><strong>点「保存草稿」</strong>时 —— 先判一遍再存</li>
<li><strong>点「提交」</strong>时 —— 提交前的最后一遍判定</li>
<li><strong>点工具条上的「重新判定」</strong>按钮 —— 随时手动重跑</li>
<li><strong>重新打开已有草稿</strong>时 —— 自动重算一遍</li>
</ol>
<blockquote><strong>注意：</strong>已经<strong>提交</strong>的记录是只读的，重新打开只会重算统计、<strong>不会改动正文内容</strong>。</blockquote>
<p>判定结果会写到<strong>判定列</strong>的单元格里：</p>
<ul>
<li>合格 → 写 <code>OK</code></li>
<li>不合格 → 写 <code>NG</code>，并把该格<strong>标红</strong></li>
<li>解析失败且没有手选 → 写「人工」</li>
<li>有标准但实测值空 → 写「—」</li>
</ul>
<p>颜色不是写进数据的，而是按判定结果由界面自动着色；因此详情页、打印、导出 Word 里都能正确显示颜色。</p>
`},{id:"spec-stats",title:"三级统计口径",body:`
<p>填写页下方会出现一条统计条，四个数字的含义如下：</p>
<table>
<thead><tr><th>指标</th><th>含义</th></tr></thead>
<tbody>
<tr><td>逐行判定</td><td>已判定的行数 / 总行数</td></tr>
<tr><td>不良数</td><td>判为 NG 的行数</td></tr>
<tr><td>转人工</td><td>系统判不出来、需要人工确认的行数</td></tr>
<tr><td>整体结论</td><td>接收 / 拒收 / 待定</td></tr>
</tbody>
</table>
<p><strong>整体结论的计算规则：</strong>默认 Ac = 0、Re = 1，即</p>
<ul>
<li>不良数 <strong>= 0</strong> → <strong>接收</strong></li>
<li>不良数 <strong>≥ 1</strong> → <strong>拒收</strong></li>
<li>没有任何有效判定 → <strong>待定</strong></li>
</ul>
<blockquote><strong>注意分母口径：</strong>只有「有效判定」才计入分母 —— 也就是自动判出来的，加上你手工选的。实测值留空的行、以及解析失败且未手选的行，<strong>不计入分母，也不计为不良</strong>。</blockquote>

<h4>按周期排的表：没填满也照样判 OK</h4>
<p>有些表是按周期排的，例如某项<strong>每 2 小时一次、一天 8 小时共 4 格</strong>。记录时如果只填了前 3 格、第 4 格还是空的：</p>
<ul>
<li>已填的 3 格照常逐格判定</li>
<li>第 4 格留空 → 判定列写「—」，<strong>不算不良、也不算漏检</strong></li>
<li>只要已填的 3 格没有 NG → 整体结论 <strong>OK（接收）</strong></li>
</ul>
<blockquote><strong>注意：</strong>如果<strong>整张表一个数据都没填</strong>，系统<strong>不下结论</strong>（显示「待定」），不会误报成 OK。</blockquote>
`},{id:"spec-safeguard",title:"三种「不会误判」的保底",body:`
<p>这三条是刻意设计的，用来保证<strong>系统不会把「不知道」当成「不合格」</strong>：</p>
<ol>
<li><strong>实测值留空</strong> → 直接跳过：不计入分母，也不计不良</li>
<li><strong>标准列只写了一个数字</strong>（如 <code>5</code>）→ <strong>不自动判</strong>，转为人工（因为无法判断这是下限还是上限）</li>
<li><strong>标准写得不规范、解析不了</strong> → <strong>不自动判</strong>，转为人工，绝不当成 NG</li>
</ol>
<p>另外，实测值填了非数字（如「正常」「OK」）时，也会按跳过处理，请改用下面的手选控件。</p>
`},{id:"spec-control",title:"手工判定控件（OK/NG 下拉与勾选）",body:`
<p>对于<strong>没有具体数值、只能靠眼看手摸</strong>的定性项（例如「外观无破损」「标识清晰」），用编辑器工具条上的判定控件。</p>
<p>工具条上有「<strong>判定控件</strong>」一组，两个按钮：</p>
<table>
<thead><tr><th>按钮</th><th>插入内容</th><th>适用</th></tr></thead>
<tbody>
<tr><td>下拉</td><td>一个 OK / NG 下拉框</td><td>需要明确判合格/不合格的项</td></tr>
<tr><td>勾选</td><td>一个勾选框</td><td>只需确认「已检/已完成」的项</td></tr>
</tbody>
</table>
<p><strong>使用方法：</strong></p>
<ol>
<li>把光标点进目标表格的单元格里（通常是判定列）</li>
<li>点工具条上的「下拉」或「勾选」</li>
<li>在单元格里点开下拉选择 OK 或 NG</li>
</ol>
<blockquote><strong>注意：</strong>如果某一行已经有了手选的 OK/NG，判定<strong>不会覆盖你的选择</strong> —— 只会给它着色，内容保留，重新打开还能改。</blockquote>
<p>手选的结果<strong>同样计入</strong>上面的三级统计（算作有效判定）。</p>
`},{id:"spec-scope",title:"哪些页面有这套判定",body:`
<table>
<thead><tr><th>页面</th><th>自动判定</th><th>三级统计条</th><th>手选控件</th></tr></thead>
<tbody>
<tr><td>巡线 IPQC 填写页</td><td>有</td><td>有</td><td>有</td></tr>
<tr><td>首件 FAI 填写页</td><td>有</td><td>有</td><td>有</td></tr>
<tr><td>设备点检填写页</td><td>有</td><td>有</td><td>有</td></tr>
</tbody>
</table>
<blockquote><strong>说明：</strong>巡线、首件、点检<strong>三个填写页口径一致</strong>——表格里有 SPEC 即自动判定。<strong>点检的差别只在「异常上报」</strong>：判出 NG 后<strong>不会自动开单</strong>，需人工点「上报设备维修申请单」。（巡线/首件上报的是品质异常单。）</blockquote>
`},{id:"spec-limits",title:"已知限制（务必了解）",body:`
<ol>
<li><strong>越南文表头不被识别。</strong>列识别关键词目前只认<strong>中文和英文 <code>spec</code></strong>。如果导入的 Excel 表头是 <code>Tiêu chuẩn</code> / <code>Giá trị đo</code> / <code>Kết luận</code>，系统认不出列，<strong>整张表会被跳过，且界面不会报错</strong>（表现为点了判定没有反应）。请先把表头改成中文，或等后续版本支持越南文表头。</li>
<li><strong>越南文的文字标准写法不被识别。</strong><code>không nhỏ hơn</code>、<code>tối đa</code> 这类写法不支持。但<strong>符号类写法与语言无关</strong>，越南文表格里写 <code>≥5</code>、<code>≤10</code>、<code>5-10</code>、<code>1.2±0.1</code>、<code>10max</code> 都可以正常判定。</li>
<li><strong>全角数字不认</strong>（<code>１２３</code> 无效），请用半角 <code>123</code>。</li>
<li><strong>科学计数只认 <code>^</code></strong>，不认 <code>1e3</code>。</li>
<li><strong>不等号必须写在最前面</strong>，「直径≥5」这种写法会失败。</li>
<li><strong>必须有「判定」列</strong>，否则整张表不参与判定。</li>
</ol>
<blockquote><strong>建议做法：</strong>统一在 Excel 里写好标准的列名（中文），标准值优先用<strong>符号写法</strong>（<code>≥</code> <code>≤</code> <code>~</code> <code>±</code>），这样中越两边都能用。</blockquote>
`}]}];export{t as default};
