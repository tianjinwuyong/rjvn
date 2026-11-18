const t=[{id:"spec",title:"Quy tắc phán định SPEC (chuyên đề)",sections:[{id:"spec-prereq",title:"Điều kiện áp dụng: bảng phải có ba cột này",body:`
<p>Hệ thống nhận diện tự động «cột nào là tiêu chuẩn, cột nào là giá trị đo, cột nào ghi kết luận» thông qua <strong>chữ ở dòng tiêu đề</strong>. Cả ba cột đều dựa trên khớp từ khóa, không phụ thuộc vào thứ tự hay vị trí của cột.</p>
<table>
<thead><tr><th>Cột</th><th>Tiêu đề cần chứa các chữ này</th></tr></thead>
<tbody>
<tr><td>Cột tiêu chuẩn (SPEC)</td><td><code>spec</code>, 规格, 标准, 判定标准, 技术要求, 公差, 要求</td></tr>
<tr><td>Cột giá trị đo</td><td>实测, 测量, 实测值, 测量值, 数值, 读数, 检验值</td></tr>
<tr><td>Cột kết luận</td><td>判定, 结论, 结果, 合格, 是否</td></tr>
</tbody>
</table>
<blockquote><strong>Điều quan trọng nhất:</strong> bảng <strong>bắt buộc phải có cột «kết luận»</strong>, nếu không toàn bộ bảng sẽ bị hệ thống <strong>bỏ qua, không xử lý gì cả</strong> (nhằm tránh vô tình sửa các bảng trình bày không liên quan trong mẫu).</blockquote>
<p>Khi nhận diện, hệ thống tự động bỏ qua các dòng tiêu đề (hỗ trợ <strong>tiêu đề hai dòng gộp ô</strong>, ví dụ trong Excel «实测值» trải trên hai cột, còn «白班 / 夜班» nằm ở dòng thứ hai).</p>
<p>Sau khi nhập Excel, các ô gộp sẽ được chuyển thành gộp cột / gộp dòng bình thường, không ảnh hưởng đến việc nhận diện.</p>
`},{id:"spec-syntax",title:"Bảy cách viết SPEC (kèm ví dụ)",body:`
<p>Cách viết trong cột tiêu chuẩn được thử lần lượt theo <strong>thứ tự ưu tiên cố định</strong> dưới đây, trúng là dừng. Viết đúng bất kỳ cách nào là được.</p>

<h4>① Một phía bằng chữ</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>不小于5</code>, <code>不低于5</code></td><td>≥ 5 (bao gồm 5)</td></tr>
<tr><td><code>不大于10</code>, <code>不高于10</code></td><td>≤ 10 (bao gồm 10)</td></tr>
<tr><td><code>大于等于5</code>, <code>大等于5</code></td><td>≥ 5 (bao gồm 5)</td></tr>
<tr><td><code>小于等于10</code>, <code>小等于10</code></td><td>≤ 10 (bao gồm 10)</td></tr>
<tr><td><code>大于5</code>, <code>高于5</code></td><td>&gt; 5 (không bao gồm 5)</td></tr>
<tr><td><code>小于10</code>, <code>低于10</code></td><td>&lt; 10 (không bao gồm 10)</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong> cách viết một phía bằng chữ <strong>chỉ lấy con số đầu tiên gặp được</strong>. Nếu viết «不小于5且不大于10», hệ thống chỉ lấy 5 làm giới hạn dưới, <strong>giới hạn trên sẽ bị bỏ qua</strong>. Muốn giới hạn hai phía hãy dùng cách viết khoảng (xem ②).</blockquote>

<h4>② Khoảng giá trị</h4>
<p>Có sáu loại ký hiệu nối: <code>-</code>, <code>~</code>, <code>～</code>, <code>到</code>, <code>—</code>, <code>–</code>, và <strong>dấu phẩy toàn phần</strong> «<code>，</code>».</p>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>5-10</code>, <code>5~10</code>, <code>5到10</code>, <code>5，10</code></td><td>5 ≤ giá trị ≤ 10</td></tr>
<tr><td><code>10mm-20mm</code></td><td>10 ≤ giá trị ≤ 20 (hai bên ký hiệu nối có thể có đơn vị)</td></tr>
<tr><td><code>10-5</code></td><td>Tự động sửa thành 5 ~ 10</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong> hai bên ký hiệu nối không nên xuất hiện chữ <code>min</code> / <code>max</code>, nếu không sẽ bị hiểu là giá trị lớn nhất / nhỏ nhất (xem ④).</blockquote>

<h4>③ Dấu bất đẳng thức</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>≥5</code>, <code>&gt;=5</code></td><td>≥ 5 (bao gồm 5)</td></tr>
<tr><td><code>≤10</code>, <code>&lt;=10</code></td><td>≤ 10 (bao gồm 10)</td></tr>
<tr><td><code>&gt;5</code></td><td>&gt; 5 (không bao gồm 5)</td></tr>
<tr><td><code>&lt;10</code></td><td>&lt; 10 (không bao gồm 10)</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý (dễ sai nhất):</strong> dấu bất đẳng thức <strong>phải viết ở vị trí đầu tiên</strong>. <code>≥5</code> thì được, nhưng viết «直径≥5» hay «L≥5» (có chữ phía trước) sẽ <strong>phân tích thất bại ngay</strong>. Các tiền tố như cao / rộng / dài hãy để ở cột khác hoặc viết vào tên hạng mục.</blockquote>

<h4>④ Giá trị lớn nhất / nhỏ nhất</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>10max</code>, <code>max 10</code>, <code>max. 10</code></td><td>≤ 10</td></tr>
<tr><td><code>2min</code>, <code>min 2</code>, <code>min. 2</code></td><td>≥ 2</td></tr>
</tbody>
</table>
<p>Không phân biệt chữ hoa chữ thường, viết trước hay sau con số đều được.</p>

<h4>⑤ Dung sai ±</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>1.2±0.1</code></td><td>1.1 ~ 1.3</td></tr>
<tr><td><code>1.2±0.1mm</code></td><td>1.1 ~ 1.3 (sau dấu ± có đơn vị vẫn được)</td></tr>
<tr><td><code>100±5%</code></td><td>95 ~ 105 (phần trăm quy đổi theo giá trị cơ sở)</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong> trước dấu <code>±</code> bắt buộc phải là <strong>số thuần</strong>. Viết «1mm±0.1» vì chen đơn vị vào giữa nên sẽ <strong>phân tích thất bại</strong>.</blockquote>

<h4>⑥ Sai lệch trên / dưới (cách viết trên bản vẽ kỹ thuật)</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>10(+0.5/0.2)</code></td><td>10.2 ~ 10.5</td></tr>
<tr><td><code>10(+0.5,-0.2)</code></td><td>9.8 ~ 10.5</td></tr>
<tr><td><code>10(+0.5，0.2)</code></td><td>10.2 ~ 10.5 (ngoặc Trung văn, dấu phẩy toàn phần đều được)</td></tr>
</tbody>
</table>
<p>Hai số trong ngoặc lần lượt là sai lệch trên và sai lệch dưới, phân cách bằng <code>/</code> hoặc <code>,</code>. Nếu sai lệch dưới <strong>thiếu dấu dương thì tự động hiểu là số dương</strong>.</p>
<blockquote><strong>Lưu ý:</strong> sai lệch <strong>bắt buộc phải có ngoặc</strong>. Viết <code>100+0.5/-0.2</code> (không ngoặc) sẽ phân tích thất bại.</blockquote>

<h4>⑦ Lũy thừa (ký hiệu khoa học)</h4>
<table>
<thead><tr><th>Cách viết</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td><code>1^3</code></td><td>1000</td></tr>
<tr><td><code>2^10</code></td><td>1024</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong> chỉ nhận <code>^</code>, <strong>không nhận <code>1e3</code></strong>.</blockquote>
`},{id:"spec-tolerance",title:"Quy tắc chấp nhận sai lệch nhỏ (viết chưa chuẩn vẫn hiểu)",body:`
<p>Những cách viết chưa chuẩn dưới đây sẽ được hệ thống tự động sửa rồi mới phân tích:</p>
<table>
<thead><tr><th>Trường hợp</th><th>Xử lý</th><th>Ví dụ</th></tr></thead>
<tbody>
<tr><td>Dấu phẩy nửa phần theo sau là <strong>3 chữ số</strong></td><td>Coi là dấu phân cách nghìn, bỏ dấu phẩy</td><td><code>1,000</code> → 1000</td></tr>
<tr><td>Dấu phẩy nửa phần theo sau là <strong>1~2 chữ số</strong></td><td>Coi là dấu thập phân kiểu châu Âu</td><td><code>1,5</code> → 1.5</td></tr>
<tr><td>Dấu «＞=», «＜=» toàn phần</td><td>Chuẩn hóa thành <code>&gt;=</code> <code>&lt;=</code></td><td>Giữ đúng nghĩa bao gồm biên</td></tr>
<tr><td>Dấu «％» toàn phần</td><td>Chuẩn hóa thành <code>%</code></td><td>Tránh bị hiểu là dung sai tuyệt đối</td></tr>
<tr><td>Trước / sau số có khoảng trắng, đơn vị, chữ</td><td>Tự động bỏ qua để lấy số</td><td><code>厚度 5 mm</code> → lấy được 5</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong> dấu phẩy nửa phần <strong>nằm trong ngoặc không áp dụng</strong> hai quy tắc đầu (vì đó là dấu phân cách sai lệch trên / dưới), ví dụ <code>10(+0.5,0.2)</code> sẽ không bị sửa nhầm.</blockquote>
`},{id:"spec-unsupported",title:"Những cách viết không được hỗ trợ",body:`
<p>Các cách viết dưới đây hệ thống <strong>không đoán bừa</strong>, đều chuyển sang xử lý thủ công (không phán định nhầm thành không đạt):</p>
<table>
<thead><tr><th>Cách viết / Trường hợp</th><th>Kết quả</th></tr></thead>
<tbody>
<tr><td>Chữ số toàn phần (như <code>５</code>, <code>１２３</code>)</td><td>Phân tích thất bại (chỉ nhận chữ số nửa phần)</td></tr>
<tr><td>Ký hiệu khoa học kiểu <code>1e3</code></td><td>Phân tích thất bại (hãy dùng <code>1^3</code>)</td></tr>
<tr><td>Dấu bất đẳng thức viết ở giữa, như «直径≥5»</td><td>Phân tích thất bại (dấu phải ở đầu)</td></tr>
<tr><td><code>1mm±0.1</code> (chen đơn vị trước ±)</td><td>Phân tích thất bại</td></tr>
<tr><td><code>100+0.5/-0.2</code> (sai lệch không ngoặc)</td><td>Phân tích thất bại</td></tr>
<tr><td><code>直径5</code> loại chỉ có chữ, không có ý nghĩa phán định</td><td>Phân tích thất bại</td></tr>
<tr><td>Chỉ viết <strong>một con số</strong>, như <code>5</code></td><td><strong>Không phán định tự động</strong> (không biết là giới hạn trên hay dưới) → «Hãy ghi rõ dung sai hoặc giới hạn»</td></tr>
</tbody>
</table>
`},{id:"spec-when",title:"Khi nào hệ thống phán định tự động",body:`
<p>Hệ thống <strong>không phán định ngay khi đang gõ</strong>, mà chạy theo lô vào những thời điểm sau:</p>
<ol>
<li><strong>Khi bấm «Lưu nháp»</strong> — phán định một lượt rồi mới lưu</li>
<li><strong>Khi bấm «Gửi»</strong> — lượt phán định cuối trước khi gửi</li>
<li><strong>Khi bấm nút «Phán định lại»</strong> trên thanh công cụ — chạy lại bất cứ lúc nào</li>
<li><strong>Khi mở lại bản nháp đã có</strong> — tự động tính lại một lượt</li>
</ol>
<blockquote><strong>Lưu ý:</strong> bản ghi đã <strong>gửi</strong> là chỉ đọc, mở lại chỉ tính lại thống kê, <strong>không thay đổi nội dung chính</strong>.</blockquote>
<p>Kết quả phán định được ghi vào ô thuộc <strong>cột kết luận</strong>:</p>
<ul>
<li>Đạt → ghi <code>OK</code></li>
<li>Không đạt → ghi <code>NG</code>, đồng thời <strong>tô đỏ</strong> ô đó</li>
<li>Phân tích thất bại và không có lựa chọn thủ công → ghi «人工» (thủ công)</li>
<li>Có tiêu chuẩn nhưng giá trị đo trống → ghi «—»</li>
</ul>
<p>Màu không được ghi vào dữ liệu, mà do giao diện tự tô theo kết quả; vì vậy trang chi tiết, bản in và tệp Word xuất ra đều hiển thị đúng màu.</p>
`},{id:"spec-stats",title:"Ý nghĩa thống kê ba cấp",body:`
<p>Phía dưới trang điền sẽ hiện một dải thống kê, ý nghĩa bốn con số như sau:</p>
<table>
<thead><tr><th>Chỉ số</th><th>Ý nghĩa</th></tr></thead>
<tbody>
<tr><td>Phán định từng dòng</td><td>Số dòng đã phán định / tổng số dòng</td></tr>
<tr><td>Số bất thường</td><td>Số dòng bị phán định là NG</td></tr>
<tr><td>Chuyển thủ công</td><td>Số dòng hệ thống không phán định được, cần người xác nhận</td></tr>
<tr><td>Kết luận tổng thể</td><td>Nhận / Từ chối / Chờ xử lý</td></tr>
</tbody>
</table>
<p><strong>Cách tính kết luận tổng thể:</strong> mặc định Ac = 0, Re = 1, nghĩa là</p>
<ul>
<li>Số bất thường <strong>= 0</strong> → <strong>Nhận</strong></li>
<li>Số bất thường <strong>≥ 1</strong> → <strong>Từ chối</strong></li>
<li>Không có phán định hợp lệ nào → <strong>Chờ xử lý</strong></li>
</ul>
<blockquote><strong>Lưu ý về mẫu số:</strong> chỉ «phán định hợp lệ» mới được tính vào mẫu số — tức là các dòng do hệ thống phán định, cộng với các dòng bạn tự chọn. Dòng để trống giá trị đo, và dòng phân tích thất bại mà không chọn thủ công, <strong>không vào mẫu số và cũng không tính là bất thường</strong>.</blockquote>

<h4>Bảng xếp theo chu kỳ: chưa điền đủ vẫn phán định Đạt</h4>
<p>Có những bảng được xếp theo chu kỳ, ví dụ một hạng mục <strong>2 giờ một lần, một ngày 8 giờ là 4 ô</strong>. Khi ghi chép chỉ điền 3 ô đầu, ô thứ 4 còn trống:</p>
<ul>
<li>3 ô đã điền vẫn được phán định từng ô như bình thường</li>
<li>Ô thứ 4 để trống → cột kết luận ghi「—」, <strong>không tính là bất thường, cũng không tính là bỏ sót</strong></li>
<li>Chỉ cần 3 ô đã điền không có NG → kết luận tổng thể <strong>Đạt (Nhận)</strong></li>
</ul>
<blockquote><strong>Lưu ý:</strong> nếu <strong>cả bảng không điền một dữ liệu nào</strong>, hệ thống <strong>không đưa ra kết luận</strong> (hiển thị「Chờ xử lý」), không báo nhầm thành Đạt.</blockquote>
`},{id:"spec-safeguard",title:"Ba lớp bảo đảm «không phán định nhầm»",body:`
<p>Ba điều này được thiết kế có chủ đích, để bảo đảm <strong>hệ thống không biến «không biết» thành «không đạt»</strong>:</p>
<ol>
<li><strong>Giá trị đo để trống</strong> → bỏ qua ngay: không vào mẫu số, cũng không tính là bất thường</li>
<li><strong>Cột tiêu chuẩn chỉ ghi một con số</strong> (như <code>5</code>) → <strong>không phán định tự động</strong>, chuyển sang thủ công (vì không xác định được đây là giới hạn dưới hay trên)</li>
<li><strong>Tiêu chuẩn viết không chuẩn, không phân tích được</strong> → <strong>không phán định tự động</strong>, chuyển sang thủ công, tuyệt đối không coi là NG</li>
</ol>
<p>Ngoài ra, nếu giá trị đo điền chữ không phải số (như «bình thường», «OK») cũng được coi là bỏ qua, hãy dùng ô chọn thủ công bên dưới.</p>
`},{id:"spec-control",title:"Ô điều khiển phán định thủ công (chọn OK/NG và ô tick)",body:`
<p>Với các hạng mục <strong>không có số cụ thể, chỉ nhìn / sờ để đánh giá</strong> (như «ngoại quan không hư hỏng», «nhãn rõ ràng»), hãy dùng ô điều khiển trên thanh công cụ của trình soạn thảo.</p>
<p>Trên thanh công cụ có nhóm «<strong>Điều khiển phán định</strong>» gồm hai nút:</p>
<table>
<thead><tr><th>Nút</th><th>Chèn nội dung</th><th>Áp dụng cho</th></tr></thead>
<tbody>
<tr><td>Chọn</td><td>Một ô chọn OK / NG</td><td>Hạng mục cần kết luận rõ đạt / không đạt</td></tr>
<tr><td>Tick</td><td>Một ô tick</td><td>Hạng mục chỉ cần xác nhận «đã kiểm / đã xong»</td></tr>
</tbody>
</table>
<p><strong>Cách dùng:</strong></p>
<ol>
<li>Đặt con trỏ vào ô của bảng cần điền (thường là cột kết luận)</li>
<li>Bấm nút «Chọn» hoặc «Tick» trên thanh công cụ</li>
<li>Bấm mở ô chọn trong ô đó và chọn OK hoặc NG</li>
</ol>
<blockquote><strong>Lưu ý:</strong> nếu một dòng đã có lựa chọn OK/NG thủ công, phán định <strong>sẽ không ghi đè lựa chọn của bạn</strong> — chỉ tô màu cho nó, nội dung được giữ nguyên, mở lại vẫn sửa được.</blockquote>
<p>Kết quả chọn thủ công <strong>cũng được tính</strong> vào thống kê ba cấp ở trên (coi là phán định hợp lệ).</p>
`},{id:"spec-scope",title:"Những trang nào có bộ phán định này",body:`
<table>
<thead><tr><th>Trang</th><th>Phán định tự động</th><th>Dải thống kê ba cấp</th><th>Ô chọn thủ công</th></tr></thead>
<tbody>
<tr><td>Trang điền tuần tra IPQC</td><td>Có</td><td>Có</td><td>Có</td></tr>
<tr><td>Trang điền sản phẩm đầu tiên FAI</td><td>Có</td><td>Có</td><td>Có</td></tr>
<tr><td>Trang điền kiểm tra thiết bị</td><td>Có</td><td>Có</td><td>Có</td></tr>
</tbody>
</table>
<blockquote><strong>Ghi chú:</strong> Ba trang điền — tuần tra, sản phẩm đầu tiên, kiểm tra thiết bị — <strong>dùng cùng một tiêu chí</strong>: bảng có SPEC là phán định tự động. <strong>Khác biệt duy nhất của kiểm tra thiết bị nằm ở「báo cáo bất thường」</strong>: sau khi phán định ra NG, hệ thống <strong>không tự mở phiếu</strong>, cần người bấm「Báo cáo phiếu đề nghị sửa chữa thiết bị」. (Tuần tra / sản phẩm đầu tiên báo cáo phiếu bất thường chất lượng.)</blockquote>
`},{id:"spec-limits",title:"Hạn chế đã biết (cần nắm rõ)",body:`
<ol>
<li><strong>Tiêu đề bằng tiếng Việt chưa được nhận diện.</strong> Từ khóa nhận diện cột hiện chỉ nhận <strong>tiếng Trung và <code>spec</code> tiếng Anh</strong>. Nếu tệp Excel nhập vào có tiêu đề là <code>Tiêu chuẩn</code> / <code>Giá trị đo</code> / <code>Kết luận</code>, hệ thống không nhận ra cột, <strong>toàn bộ bảng sẽ bị bỏ qua và giao diện không báo lỗi</strong> (biểu hiện là bấm phán định không có phản hồi). Hãy sửa tiêu đề sang tiếng Trung trước, hoặc chờ phiên bản sau hỗ trợ tiêu đề tiếng Việt.</li>
<li><strong>Cách viết tiêu chuẩn bằng chữ tiếng Việt chưa được nhận diện.</strong> Các cách viết như <code>không nhỏ hơn</code>, <code>tối đa</code> chưa được hỗ trợ. Nhưng <strong>cách viết bằng ký hiệu không phụ thuộc ngôn ngữ</strong>: trong bảng tiếng Việt vẫn viết được <code>≥5</code>, <code>≤10</code>, <code>5-10</code>, <code>1.2±0.1</code>, <code>10max</code> và phán định bình thường.</li>
<li><strong>Chữ số toàn phần không nhận</strong> (<code>１２３</code> không hợp lệ), hãy dùng chữ số nửa phần <code>123</code>.</li>
<li><strong>Ký hiệu khoa học chỉ nhận <code>^</code></strong>, không nhận <code>1e3</code>.</li>
<li><strong>Dấu bất đẳng thức phải ở vị trí đầu tiên</strong>, cách viết «直径≥5» sẽ thất bại.</li>
<li><strong>Bắt buộc phải có cột «kết luận»</strong>, nếu không cả bảng không tham gia phán định.</li>
</ol>
<blockquote><strong>Khuyến nghị:</strong> hãy thống nhất ghi tên cột chuẩn trong Excel (bằng tiếng Trung), và giá trị tiêu chuẩn nên dùng <strong>cách viết ký hiệu</strong> (<code>≥</code> <code>≤</code> <code>~</code> <code>±</code>) để cả hai bên Trung và Việt đều dùng được.</blockquote>
`}]}];export{t as default};
