const t=[{id:"spec",title:"SPEC Verdict Rules (dedicated chapter)",sections:[{id:"spec-prereq",title:"Prerequisite: the table needs these three columns",body:`
<p>The system detects <strong>which column holds the standard, which holds the measured value and which holds the verdict</strong> from the <strong>header text</strong>. All three are matched by keyword, regardless of column order.</p>
<table>
<thead><tr><th>Column</th><th>The header must contain one of these</th></tr></thead>
<tbody>
<tr><td>Standard column (SPEC)</td><td><code>spec</code>, 规格, 标准, 判定标准, 技术要求, 公差, 要求</td></tr>
<tr><td>Measured value column</td><td>实测, 测量, 实测值, 测量值, 数值, 读数, 检验值</td></tr>
<tr><td>Verdict column</td><td>判定, 结论, 结果, 合格, 是否</td></tr>
</tbody>
</table>
<blockquote><strong>The single most important rule:</strong> the table <strong>must have a verdict column</strong>; without one the whole table is <strong>skipped and not processed at all</strong> (this prevents the system from touching unrelated layout tables inside a template).</blockquote>
<p>Header rows are skipped automatically (two-row merged headers are supported, for example an Excel sheet where "measured value" spans two columns and "day shift / night shift" sits on the second row).</p>
<p>After importing Excel, merged cells become ordinary colspan/rowspan cells and do not affect detection.</p>
`},{id:"spec-syntax",title:"Seven ways to write a SPEC (with examples)",body:`
<p>The value in the standard column is tried against the following <strong>fixed order</strong>; the first match wins. Any one of them is enough.</p>

<h4>① One-sided words</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>不小于5</code>, <code>不低于5</code></td><td>≥ 5 (5 included)</td></tr>
<tr><td><code>不大于10</code>, <code>不高于10</code></td><td>≤ 10 (10 included)</td></tr>
<tr><td><code>大于等于5</code>, <code>大等于5</code></td><td>≥ 5 (5 included)</td></tr>
<tr><td><code>小于等于10</code>, <code>小等于10</code></td><td>≤ 10 (10 included)</td></tr>
<tr><td><code>大于5</code>, <code>高于5</code></td><td>&gt; 5 (5 excluded)</td></tr>
<tr><td><code>小于10</code>, <code>低于10</code></td><td>&lt; 10 (10 excluded)</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> one-sided words take <strong>only the first number they meet</strong>. Written as "不小于5且不大于10" the system takes 5 as the lower bound and <strong>ignores the upper bound</strong>. Use the range form for two-sided limits (see ②).</blockquote>

<h4>② Range</h4>
<p>Six connectors are supported: <code>-</code>, <code>~</code>, <code>～</code>, <code>到</code>, <code>—</code>, <code>–</code>, plus the <strong>full-width comma</strong> <code>，</code>.</p>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>5-10</code>, <code>5~10</code>, <code>5到10</code>, <code>5，10</code></td><td>5 ≤ value ≤ 10</td></tr>
<tr><td><code>10mm-20mm</code></td><td>10 ≤ value ≤ 20 (units may sit on either side of the connector)</td></tr>
<tr><td><code>10-5</code></td><td>Corrected automatically to 5 ~ 10</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> Do not put <code>min</code> or <code>max</code> next to the connector, or it is read as a maximum/minimum instead (see ④).</blockquote>

<h4>③ Inequality signs</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>≥5</code>, <code>&gt;=5</code></td><td>≥ 5 (5 included)</td></tr>
<tr><td><code>≤10</code>, <code>&lt;=10</code></td><td>≤ 10 (10 included)</td></tr>
<tr><td><code>&gt;5</code></td><td>&gt; 5 (5 excluded)</td></tr>
<tr><td><code>&lt;10</code></td><td>&lt; 10 (10 excluded)</td></tr>
</tbody>
</table>
<blockquote><strong>Note (the easiest trap):</strong> the inequality sign <strong>must come first</strong>. <code>≥5</code> works; "直径≥5" or "L≥5" with <strong>text in front fails to parse</strong>. Put diameter / width / length into another column or into the item name.</blockquote>

<h4>④ Max / Min</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>10max</code>, <code>max 10</code>, <code>max. 10</code></td><td>≤ 10</td></tr>
<tr><td><code>2min</code>, <code>min 2</code>, <code>min. 2</code></td><td>≥ 2</td></tr>
</tbody>
</table>
<p>Case does not matter, and the word may come before or after the number.</p>

<h4>⑤ ± tolerance</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>1.2±0.1</code></td><td>1.1 ~ 1.3</td></tr>
<tr><td><code>1.2±0.1mm</code></td><td>1.1 ~ 1.3 (a unit after ± is accepted)</td></tr>
<tr><td><code>100±5%</code></td><td>95 ~ 105 (the percentage is applied to the base value)</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> the value before <code>±</code> must be a <strong>plain number</strong>. "1mm±0.1" <strong>fails to parse</strong> because a unit sits in between.</blockquote>

<h4>⑥ Upper and lower deviation (engineering drawing style)</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>10(+0.5/0.2)</code></td><td>10.2 ~ 10.5</td></tr>
<tr><td><code>10(+0.5,-0.2)</code></td><td>9.8 ~ 10.5</td></tr>
<tr><td><code>10(+0.5，0.2)</code></td><td>10.2 ~ 10.5 (Chinese brackets and a full-width comma are fine)</td></tr>
</tbody>
</table>
<p>Inside the brackets the first number is the upper deviation and the second the lower one, separated by <code>/</code> or <code>,</code>. If the lower deviation <strong>omits its sign it is treated as positive</strong>.</p>
<blockquote><strong>Note:</strong> the deviations <strong>must be in brackets</strong>. <code>100+0.5/-0.2</code> without brackets fails to parse.</blockquote>

<h4>⑦ Powers (scientific notation)</h4>
<table>
<thead><tr><th>Written as</th><th>Means</th></tr></thead>
<tbody>
<tr><td><code>1^3</code></td><td>1000</td></tr>
<tr><td><code>2^10</code></td><td>1024</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> only <code>^</code> is understood; <strong><code>1e3</code> is not supported</strong>.</blockquote>
`},{id:"spec-tolerance",title:"Tolerance rules (sloppy input still parses)",body:`
<p>The system corrects the following irregular inputs before parsing:</p>
<table>
<thead><tr><th>Input</th><th>Handling</th><th>Example</th></tr></thead>
<tbody>
<tr><td>A half-width comma followed by <strong>3 digits</strong></td><td>Treated as a thousands separator and removed</td><td><code>1,000</code> → 1000</td></tr>
<tr><td>A half-width comma followed by <strong>1–2 digits</strong></td><td>Treated as a European decimal point</td><td><code>1,5</code> → 1.5</td></tr>
<tr><td>Full-width <code>&gt;=</code> / <code>&lt;=</code></td><td>Normalised to <code>&gt;=</code> and <code>&lt;=</code></td><td>Boundary-inclusive meaning kept</td></tr>
<tr><td>Full-width percent sign</td><td>Normalised to <code>%</code></td><td>Avoids being read as an absolute tolerance</td></tr>
<tr><td>Spaces, units or text around the number</td><td>Parsed by skipping to the number</td><td><code>厚度 5 mm</code> → 5</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> the two comma rules do <strong>not</strong> apply inside brackets, where a comma separates the deviations — <code>10(+0.5,0.2)</code> is left untouched.</blockquote>
`},{id:"spec-unsupported",title:"Explicitly unsupported inputs",body:`
<p>The system <strong>does not guess</strong> in the following cases; they are handed to a person instead (never misjudged as NG):</p>
<table>
<thead><tr><th>Input / case</th><th>Result</th></tr></thead>
<tbody>
<tr><td>Full-width digits (for example <code>５</code>, <code>１２３</code>)</td><td>Parse failure (only half-width digits are read)</td></tr>
<tr><td>Scientific notation such as <code>1e3</code></td><td>Parse failure (use <code>1^3</code>)</td></tr>
<tr><td>An inequality sign in the middle, such as "直径≥5"</td><td>Parse failure (the sign must come first)</td></tr>
<tr><td><code>1mm±0.1</code> (a unit before ±)</td><td>Parse failure</td></tr>
<tr><td><code>100+0.5/-0.2</code> (deviations without brackets)</td><td>Parse failure</td></tr>
<tr><td>Plain text without a verdict meaning, such as "直径5"</td><td>Parse failure</td></tr>
<tr><td>Only <strong>one number</strong>, such as <code>5</code></td><td><strong>No automatic verdict</strong> (cannot tell whether it is a floor or a ceiling) → "please specify a tolerance or limits"</td></tr>
</tbody>
</table>
`},{id:"spec-when",title:"When the automatic verdict runs",body:`
<p>The system <strong>does not judge while you type</strong>; it runs in batch at these moments:</p>
<ol>
<li><strong>When you click Save Draft</strong> — it judges once before saving</li>
<li><strong>When you click Submit</strong> — the final pass before submission</li>
<li><strong>When you click Re-judge in the toolbar</strong> — a manual re-run at any time</li>
<li><strong>When an existing draft is reopened</strong> — it recalculates once automatically</li>
</ol>
<blockquote><strong>Note:</strong> a <strong>submitted</strong> record is read-only; reopening it only recalculates the statistics and <strong>never changes the body content</strong>.</blockquote>
<p>The verdict is written into the <strong>verdict column</strong>:</p>
<ul>
<li>Pass → <code>OK</code></li>
<li>Fail → <code>NG</code>, and the cell is <strong>highlighted in red</strong></li>
<li>Parse failure with no manual choice → "人工" (manual)</li>
<li>A standard with an empty measured value → "—"</li>
</ul>
<p>Colours are not stored in the data; the interface applies them from the verdict, so they also appear correctly on the details page, when printing and in Word exports.</p>
`},{id:"spec-stats",title:"How the three-level statistics are counted",body:`
<p>A statistics bar appears below the fill page with four numbers:</p>
<table>
<thead><tr><th>Metric</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td>Judge by Row</td><td>Rows judged / total rows</td></tr>
<tr><td>Defect Count</td><td>Rows judged NG</td></tr>
<tr><td>To Manual</td><td>Rows the system could not judge and a person must confirm</td></tr>
<tr><td>Overall Conclusion</td><td>Accept / Reject / Pending</td></tr>
</tbody>
</table>
<p><strong>How the overall conclusion is computed:</strong> by default Ac = 0 and Re = 1, which means</p>
<ul>
<li>Defect count <strong>= 0</strong> → <strong>Accept</strong></li>
<li>Defect count <strong>≥ 1</strong> → <strong>Reject</strong></li>
<li>No valid verdict at all → <strong>Pending</strong></li>
</ul>
<blockquote><strong>Note on the denominator:</strong> only <strong>valid verdicts</strong> count — those produced automatically plus those you picked by hand. Rows with an empty measured value, and rows that failed to parse and were not picked by hand, <strong>are excluded from the denominator and are not counted as defects</strong>.</blockquote>

<h4>Period-based tables: a partial fill still passes</h4>
<p>Some tables are laid out by period — for example one check <strong>every 2 hours, four cells across an 8-hour day</strong>. If only the first three cells are filled and the fourth is left empty:</p>
<ul>
<li>The three filled cells are judged one by one as usual</li>
<li>The fourth cell stays empty → its verdict cell shows "—" and it is <strong>neither a defect nor a missed check</strong></li>
<li>As long as none of the three filled cells is NG, the overall conclusion is <strong>OK (Accept)</strong></li>
</ul>
<blockquote><strong>Note:</strong> if <strong>not a single value is filled in</strong>, the system <strong>draws no conclusion</strong> (Pending) instead of reporting OK.</blockquote>
`},{id:"spec-safeguard",title:"Three safeguards against a wrong verdict",body:`
<p>These three rules are deliberate: they ensure the system <strong>never treats "I do not know" as "failed"</strong>.</p>
<ol>
<li><strong>Empty measured value</strong> → skipped: not counted in the denominator, not counted as a defect</li>
<li><strong>A single number in the standard column</strong> (such as <code>5</code>) → <strong>no automatic verdict</strong>; handed to a person, because a lone number cannot tell a floor from a ceiling</li>
<li><strong>An irregular standard that cannot be parsed</strong> → <strong>no automatic verdict</strong>; handed to a person, never marked NG</li>
</ol>
<p>In addition, a measured value that is not a number ("正常", "OK") is also skipped — use the manual controls below instead.</p>
`},{id:"spec-control",title:"Manual verdict controls (OK/NG dropdown and checkbox)",body:`
<p>Qualitative items that <strong>have no numeric value and can only be checked by eye and hand</strong> (for example "no damage on the surface", "label is legible") use the verdict controls in the editor toolbar.</p>
<p>The <strong>Decision controls</strong> group on the toolbar has two buttons:</p>
<table>
<thead><tr><th>Button</th><th>Inserts</th><th>Use when</th></tr></thead>
<tbody>
<tr><td>Dropdown</td><td>An OK / NG dropdown</td><td>The item must be explicitly passed or failed</td></tr>
<tr><td>Checkbox</td><td>A checkbox</td><td>You only need to confirm "checked / done"</td></tr>
</tbody>
</table>
<p><strong>How to use it:</strong></p>
<ol>
<li>Put the cursor inside the target cell (usually the verdict column)</li>
<li>Click Dropdown or Checkbox in the toolbar</li>
<li>Open the dropdown in the cell and pick OK or NG</li>
</ol>
<blockquote><strong>Note:</strong> if a row already carries a manual OK/NG, the verdict <strong>does not overwrite your choice</strong> — it only colours the cell, the content is kept and can still be changed after reopening.</blockquote>
<p>Manual choices <strong>also count</strong> in the three-level statistics above, as valid verdicts.</p>
`},{id:"spec-scope",title:"Which pages have this verdict",body:`
<table>
<thead><tr><th>Page</th><th>Automatic verdict</th><th>Statistics bar</th><th>Manual controls</th></tr></thead>
<tbody>
<tr><td>IPQC line patrol fill page</td><td>Yes</td><td>Yes</td><td>Yes</td></tr>
<tr><td>FAI first article fill page</td><td>Yes</td><td>Yes</td><td>Yes</td></tr>
<tr><td>Equipment inspection fill page</td><td>Yes</td><td>Yes</td><td>Yes</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> line patrol, first article and inspection <strong>behave identically</strong> — a SPEC in the table triggers the automatic verdict. <strong>Inspection differs only in how anomalies are reported</strong>: an NG <strong>does not open a form by itself</strong>; someone must click Report Equipment Repair. (Patrol and first article raise a quality issue report instead.)</blockquote>
`},{id:"spec-limits",title:"Known limitations (must read)",body:`
<ol>
<li><strong>Vietnamese headers are not recognised.</strong> Column detection only knows <strong>Chinese keywords and the English word <code>spec</code></strong>. If an imported Excel header reads <code>Tiêu chuẩn</code> / <code>Giá trị đo</code> / <code>Kết luận</code>, no column is found, <strong>the whole table is skipped and the interface shows no error</strong> (it simply looks as if clicking the verdict button does nothing). Change the headers to Chinese first, or wait for a later version that supports Vietnamese headers.</li>
<li><strong>Vietnamese word-based standards are not recognised.</strong> Forms such as <code>không nhỏ hơn</code> or <code>tối đa</code> are not supported. <strong>Symbol forms are language-neutral</strong>, so <code>≥5</code>, <code>≤10</code>, <code>5-10</code>, <code>1.2±0.1</code> and <code>10max</code> all work in a Vietnamese table.</li>
<li><strong>Full-width digits are not recognised</strong> (<code>１２３</code> is invalid); use half-width <code>123</code>.</li>
<li><strong>Scientific notation only understands <code>^</code></strong>, not <code>1e3</code>.</li>
<li><strong>An inequality sign must come first</strong>; "直径≥5" fails.</li>
<li><strong>A verdict column is mandatory</strong>, otherwise the table takes no part in the verdict.</li>
</ol>
<blockquote><strong>Recommendation:</strong> write the standard column names in Chinese in Excel, and prefer <strong>symbol forms</strong> for the standard itself (<code>≥</code> <code>≤</code> <code>~</code> <code>±</code>) so the same file works in both Chinese and Vietnamese.</blockquote>
`}]}];export{t as default};
