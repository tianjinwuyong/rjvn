const t=[{id:"equip",title:"Quản lý thiết bị",sections:[{id:"equip-ledger",title:"Sổ theo dõi thiết bị",body:`<p>Sổ theo dõi thiết bị là "sổ cái" của thiết bị: ghi thông tin cơ bản, chu kỳ bảo dưỡng và hiệu chuẩn ngoài, tần suất kiểm tra; cũng là nguồn dữ liệu cho việc gắn mẫu kiểm tra, in thẻ quản lý, quét mã kiểm tra và kiểm kê. Lối vào: menu「Quản lý thiết bị → Sổ theo dõi thiết bị」.</p>
<ol>
<li>Thêm mới: nhấn「Thêm thiết bị」ở góc trên bên phải, điền tối thiểu「Mã tài sản」và「Tên thiết bị」rồi lưu.</li>
<li>Nhập hàng loạt: nhấn「Nhập hàng loạt」→「Tải mẫu」, điền theo cột rồi tải lên Excel; hệ thống upsert theo mã thiết bị (đã có thì cập nhật, chưa có thì thêm mới).</li>
<li>Xuất: xuất toàn bộ sổ theo dõi ra Excel theo điều kiện lọc hiện tại.</li>
<li>Chi tiết: nhấn vào mã tài sản để mở ngăn kéo, xem「Dòng thời gian lịch sử / Hồ sơ kiểm tra / Hồ sơ hiệu chuẩn」.</li>
</ol>
<table>
<thead><tr><th>Trường thường dùng</th><th>Mô tả</th></tr></thead>
<tbody>
<tr><td>Mã tài sản / Tên thiết bị</td><td>Bắt buộc; mã tài sản là khóa upsert khi nhập và cũng là nội dung mã QR trên thẻ quản lý</td></tr>
<tr><td>Bộ phận sử dụng / Vị trí lắp đặt</td><td>Dùng khi giới hạn phạm vi kiểm kê theo bộ phận hoặc theo vị trí</td></tr>
<tr><td>Chu kỳ bảo dưỡng (ngày) / Chu kỳ hiệu chuẩn (ngày)</td><td>Dùng để tính bảo dưỡng kế tiếp, hiệu chuẩn kế tiếp</td></tr>
<tr><td>Ngày hiệu chuẩn lần đầu</td><td>Nhập thủ công, không tham gia tính toán tự động</td></tr>
<tr><td>Tần suất kiểm tra / Khoảng tần suất</td><td>Ngày/Tuần/Tháng/Quý/Năm + khoảng, dùng để tạo nhiệm vụ kiểm tra</td></tr>
<tr><td>Trạng thái</td><td>Đang vận hành / Đang bảo trì / Tạm dừng / Đã thanh lý</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>Trạng thái thiết bị là một giá trị「Trạng thái」duy nhất (không phải công tắc bật/tắt); thiết bị tạm dừng, thanh lý sẽ được nhận diện riêng và ghi vết khi quét mã kiểm tra/kiểm kê; xóa không thể khôi phục.</blockquote>`},{id:"equip-tpl",title:"Mẫu kiểm tra thiết bị (nhập Excel + rich text)",body:`<p>Mẫu kiểm tra thiết bị được duy trì theo cách「<strong>nhập Excel tạo bản nháp + soạn thảo rich text trực tuyến</strong>」— bản nháp chính là mẫu, không còn cấu hình từng hạng mục có cấu trúc. Lối vào: menu「Quản trị hệ thống → Mẫu kiểm tra」.</p>
<ol>
<li>Nhấn「Tạo mẫu mới」, điền「Mã mẫu」「Tên mẫu」「Tên tiếng Việt」.</li>
<li>Bắt buộc chọn「Thiết bị」— mẫu kiểm tra gắn với thiết bị (bắt buộc), nhiệm vụ được phát theo thiết bị.</li>
<li>Có thể đặt「Tần suất kiểm tra」(Ngày/Tuần/Tháng/Quý/Năm) và「Khoảng tần suất」; để trống thì không phát nhiệm vụ theo tần suất.</li>
<li>Nhấn「Nhập Excel tạo bản nháp」, chọn .xlsx/.xls; nếu có nhiều sheet, chọn sheet cần chuyển thành bản nháp; ô gộp sẽ được chuyển thành tiêu đề gộp.</li>
<li>Chỉnh sửa bản nháp trong trình soạn thảo bên dưới (bảng / chữ / ảnh); có thể tải「Lưu trữ Excel gốc」để đối chiếu.</li>
<li>Nhấn「Lưu mẫu」; sau đó có thể「Kích hoạt / Vô hiệu / Xóa」trên danh sách.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>① Mẫu bắt buộc gắn thiết bị, chưa chọn thiết bị thì không lưu được. ② Phát nhiệm vụ chỉ dùng<strong>tần suất cấp mẫu</strong>; tần suất ghi trong bản nháp Excel chỉ là ghi chú dạng chữ, không tham gia tạo nhiệm vụ. ③ Mẫu đã được hồ sơ kiểm tra tham chiếu không thể xóa. ④ Sau khi vô hiệu, mẫu không còn tạo nhiệm vụ và không còn xuất hiện trong danh sách mẫu chọn ở trang điền.</blockquote>`},{id:"equip-task",title:"Nhiệm vụ kiểm tra và điền",body:`<p>Nhiệm vụ kiểm tra được sinh theo thiết bị và tần suất của mẫu; khi thực hiện sẽ vào trang「Điền kiểm tra thiết bị」dạng rich text. Danh sách nhiệm vụ: menu「Quản lý thiết bị → Nhiệm vụ bảo dưỡng」(tiêu đề trang là「Nhiệm vụ kiểm tra」); trang điền và trang hồ sơ nằm trong menu「Quản lý chất lượng」.</p>
<ol>
<li>Trang danh sách lọc theo「Trạng thái nhiệm vụ + khoảng ngày」; nhấn「Tạo nhiệm vụ」để phát theo tần suất mẫu (cần quyền quản lý thiết bị).</li>
<li>Với nhiệm vụ chưa hoàn thành, nhấn「Thực hiện kiểm tra」để mở trang điền, hệ thống tự mang theo mẫu và thiết bị của nhiệm vụ đó.</li>
<li>Tại trang điền, đối chiếu thiết bị và điền theo bản nháp; có thể nhấn「Chụp ảnh」để chèn ảnh hiện trường vào bảng.</li>
<li>「Lưu nháp」để điền tiếp sau; sau khi「Gửi」nội dung được cố định (không sửa được).</li>
<li>Khi phát hiện bất thường, tích「Đánh dấu bất thường」và điền lý do, rồi nhấn「Báo cáo phiếu đề nghị sửa chữa thiết bị」.</li>
</ol>
<table>
<thead><tr><th>Mục</th><th>Giá trị</th></tr></thead>
<tbody>
<tr><td>Trạng thái nhiệm vụ</td><td>Chờ thực hiện / Đã hoàn thành / Quá hạn</td></tr>
<tr><td>Loại nhiệm vụ</td><td>Kiểm tra / Bảo dưỡng / Hiệu chuẩn ngoài / Sửa chữa</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>Kiểm tra thiết bị dùng <strong>cùng tiêu chí</strong> với tuần tra / sản phẩm đầu tiên — <strong>bảng có SPEC là phán định tự động</strong>: một dòng không đạt thì cả bảng không đạt, ô trống không chặn kết quả đạt (xem chuyên đề「Quy tắc phán định SPEC」). <strong>Báo cáo bất thường vẫn do người làm</strong>: người điền đánh dấu rồi báo cáo một nút thành phiếu đề nghị sửa chữa thiết bị, hệ thống không tự tạo phiếu. Sau khi gửi, nội dung cố định nhưng<strong>vẫn có thể bổ sung ảnh đính kèm</strong> để chụp bổ sung tại hiện trường.</blockquote>`},{id:"equip-calib",title:"Hiệu chuẩn thiết bị và cảnh báo",body:`<p>Hiệu chuẩn dùng để đăng ký kế hoạch hiệu chuẩn ngoài và chứng chỉ của thiết bị, đồng thời nhắc theo mức với các trường hợp sắp đến hạn hoặc đã quá hạn; 「Trung tâm cảnh báo」cho phép quét thủ công và gửi thông báo theo mức.</p>
<p><strong>Kế hoạch hiệu chuẩn</strong> (menu「Quản lý thiết bị → Kế hoạch hiệu chuẩn」)</p>
<ol>
<li>Nhấn「Thêm kế hoạch hiệu chuẩn」, chọn thiết bị và điền「Ngày hiệu chuẩn kế hoạch」「Đơn vị hiệu chuẩn」「Số chứng chỉ」v.v., rồi lưu.</li>
<li>Danh sách tự phân mức theo số ngày còn lại: Bình thường / Trong 30 ngày / Trong 10 ngày / Trong 7 ngày / Trong 3 ngày hoặc quá hạn, hiển thị bằng nhãn và nền màu khác nhau.</li>
<li>Sau khi hiệu chuẩn xong, nhấn「Đăng ký hoàn thành」và điền ngày thực tế cùng kết quả; sau khi lưu, hệ thống tự ghi lại kết quả hiệu chuẩn gần nhất của thiết bị và tính lại「Hiệu chuẩn kế tiếp」.</li>
</ol>
<p><strong>Trung tâm cảnh báo</strong> (menu「Quản lý thiết bị → Trung tâm cảnh báo」) hiển thị thiết bị đến hạn hiệu chuẩn ngoài trong 30 ngày, lịch sử cảnh báo đã gửi và nút「Quét ngay」.</p>
<table>
<thead><tr><th>Số ngày còn lại</th><th>Mức nhận thông báo</th></tr></thead>
<tbody>
<tr><td>≤ 30 ngày</td><td>Người thực hiện / Trưởng bộ phận</td></tr>
<tr><td>≤ 10 ngày</td><td>Trưởng phòng kỹ thuật</td></tr>
<tr><td>≤ 7 ngày</td><td>Phó tổng giám đốc</td></tr>
<tr><td>≤ 3 ngày / Đã quá hạn</td><td>Tổng giám đốc</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>Chuỗi cảnh báo<strong>chỉ áp dụng cho hiệu chuẩn ngoài</strong>, không áp dụng cho kiểm tra thiết bị; cùng một thiết bị cùng một mức chỉ gửi một lần. Việc quét cảnh báo được<strong>kích hoạt thủ công</strong>.</blockquote>`},{id:"equip-label",title:"In thẻ quản lý thiết bị",body:`<p>Thẻ quản lý thiết bị là nhãn in nhiệt 70mm × 50mm dán trên thiết bị, gồm các trường cơ bản và mã QR (nội dung mã QR = mã tài sản), dùng để quét mã kiểm tra tại hiện trường.</p>
<ol>
<li>Một thẻ: tại「Sổ theo dõi thiết bị」nhấn「In thẻ quản lý thiết bị」ở cột thao tác, trình duyệt mở cửa sổ in.</li>
<li>Hàng loạt: tích chọn nhiều thiết bị (cột chọn bên trái) → nhấn「In hàng loạt thẻ quản lý」→ tạo 1 cửa sổ in, N trang, mỗi trang một thiết bị.</li>
<li>Chọn máy in nhãn trong cửa sổ in và tiến hành in.</li>
</ol>
<table>
<thead><tr><th>Trường trên thẻ</th><th>Mô tả</th></tr></thead>
<tbody>
<tr><td>Mã tài sản / Tên thiết bị / Model</td><td>Lấy từ sổ theo dõi thiết bị</td></tr>
<tr><td>Bộ phận / Ngày mua / Hiệu chuẩn đầu</td><td>Ngày hiển thị dạng gạch chéo, chỉ dùng để in</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>① Ngày trên thẻ ở dạng<strong>gạch chéo</strong> (tiêu chí chỉ trong phạm vi in), khác với hiển thị ở các trang khác. ② <strong>In hàng loạt tối đa 50 thẻ mỗi lần</strong>, vượt sẽ được nhắc chia nhỏ. ③ Cần cho phép cửa sổ bật lên của trình duyệt; nếu bị chặn hãy cho phép rồi thử lại. ④ Khi mã tài sản trống sẽ không tạo mã QR, bố cục tự hạ cấp (mã hiển thị là「—」).</blockquote>`},{id:"equip-scan",title:"Quét mã kiểm tra thiết bị",body:`<p>Quét mã kiểm tra dùng tại hiện trường: dùng điện thoại quét mã QR trên thẻ quản lý thiết bị, hoặc nhập trực tiếp / dùng súng quét mã để nhập mã tài sản, vào nhanh trang điền kiểm tra.</p>
<ol>
<li>Mở lối vào kiểm tra trên trình duyệt điện thoại (<code>/m/equip</code>, sẽ tự chuyển đến trang「Điền kiểm tra thiết bị」).</li>
<li>Bảng「Quét mã」có hai cách: quét bằng<strong>camera</strong>, hoặc chuyển sang<strong>ô nhập / súng quét mã</strong>để nhập thủ công.</li>
<li>Đối chiếu thông tin thiết bị, chọn mẫu khả dụng, điền theo bản nháp và gửi.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>① Dùng <strong>camera quét mã bắt buộc truy cập qua HTTPS (cổng 8443)</strong>; khi dùng HTTP hoặc camera không khả dụng, bảng sẽ tự hạ cấp sang「ô nhập / súng quét mã」, không bị trắng trang. ② Khi thiết bị không tồn tại, thiết bị ở trạng thái tạm dừng/đã thanh lý, hoặc thiết bị không có mẫu khả dụng hay nhiệm vụ thực hiện được, hệ thống sẽ hiển thị thông báo rõ ràng. ③ Lối vào quét mã và tương tác theo giao diện thực tế.</blockquote>`},{id:"equip-stocktake",title:"Quét mã kiểm kê",body:`<p>Kiểm kê thiết bị là công việc「theo dự án」: tạo nhiệm vụ trước (tên, thời gian kiểm kê, phạm vi), sau hai lần phê duyệt của Tổng giám đốc (phát hành / kết thúc), nhân viên kiểm kê dùng điện thoại quét mã đối chiếu, hệ thống đưa ra tiến độ, danh sách chênh lệch và báo cáo.</p>
<ol>
<li>Menu「Quản lý thiết bị → Kiểm kê thiết bị」→「Tạo nhiệm vụ kiểm kê」: điền tên, thời gian kiểm kê, chọn phạm vi (Toàn bộ thiết bị / Theo bộ phận / Theo vị trí); trang hiển thị trực tiếp「Số thiết bị dự kiến」.</li>
<li>Chọn「Lưu bản nháp」hoặc「Gửi duyệt」; sau khi gửi, Tổng giám đốc xử lý tại「Chờ tôi phê duyệt」, sau khi duyệt nhiệm vụ tự động phát hành.</li>
<li>Nhân viên kiểm kê mở <code>/m/stocktake</code> trên điện thoại (trang chi tiết trên PC có thể sao chép liên kết), chọn nhiệm vụ rồi quét mã đối chiếu; tiến độ lấy theo máy chủ, quét lại cùng một thiết bị không bị tăng ảo.</li>
<li>Sau khi kiểm kê xong, nhấn「Gửi kết thúc」→ Tổng giám đốc phê duyệt → sau khi duyệt danh sách chênh lệch được chốt.</li>
<li>Nhấn「Xuất báo cáo」để tải báo cáo Excel.</li>
</ol>
<table>
<thead><tr><th>Trạng thái</th><th>Loại chênh lệch</th></tr></thead>
<tbody>
<tr><td>Bản nháp / Chờ duyệt / Đang thực hiện / Đang chờ duyệt kết thúc / Đã kết thúc / Đã từ chối</td><td>Đã đối chiếu / Cần kiểm chưa quét / Quét ngoài phạm vi / Trạng thái bất thường</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>① Khi số thiết bị dự kiến là 0 thì<strong>không cho phát hành</strong>, cần điều chỉnh phạm vi. ②「Cần kiểm chưa quét」chỉ được chốt sau khi kết thúc kiểm kê. ③ Quét mã đối chiếu trên điện thoại cần truy cập qua HTTPS (8443) mới gọi được camera, nếu không sẽ tự hạ cấp sang nhập thủ công / súng quét mã.</blockquote>`}]},{id:"quality",title:"Quản lý chất lượng",sections:[{id:"qc-ipqc",title:"Tuần tra IPQC",body:`<p>Tuần tra dùng mô thức「<strong>nhập Excel tạo mẫu → bản nháp rich text trực tuyến → điền rich text → đánh dấu bất thường thủ công → báo cáo một nút phiếu bất thường chất lượng</strong>」, đồng nhất với sản phẩm đầu tiên và kiểm tra thiết bị. Lối vào trang điền: menu「Quản lý chất lượng → Gửi tuần tra」; hồ sơ tại「Hồ sơ tuần tra」.</p>
<ol>
<li>Chọn mẫu tuần tra, hệ thống tải bản nháp rich text của mẫu đó.</li>
<li>Điền theo bản nháp: có thể sửa trực tiếp bảng, bổ sung chữ, chèn ảnh hiện trường vào bảng.</li>
<li>Nhấn「Lưu nháp」để điền tiếp sau; sau khi nhấn「Gửi」nội dung cố định.</li>
<li>Khi cần báo cáo bất thường: tích「Đánh dấu bất thường」và điền「Mô tả bất thường」, rồi nhấn「Báo cáo phiếu bất thường」; sau khi thành công, danh sách và chi tiết hiển thị「Mở phiếu bất thường」.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>Tuần tra / sản phẩm đầu tiên còn có năng lực「phán định tự động theo SPEC + thống kê ba cấp」(xem chuyên mục「Thông minh hóa bảng kiểm tra」). Các chỉ số <strong>tỷ lệ đạt / tỷ lệ bất thường / tỷ lệ đóng trên danh sách hồ sơ đều theo tiêu chí báo cáo thủ công</strong> — mẫu số của tỷ lệ đóng là「phiếu bất thường đã báo cáo」, không phải kết quả phán định từng hạng mục. Nhiệm vụ do「Tạo nhiệm vụ hôm nay」sinh mỗi ngày 1 bản ghi theo mẫu「đang bật và có dây chuyền」, thông báo dẫn trực tiếp đến trang điền.</blockquote>`},{id:"qc-fai",title:"Sản phẩm đầu tiên FAI",body:`<p>Sản phẩm đầu tiên dùng cùng mô thức và giao diện với tuần tra, chỉ khác trường ở đầu trang và tiêu chí thống kê: tuần tra theo dây chuyền, sản phẩm đầu tiên theo mã sản phẩm và công đoạn. Lối vào trang điền: menu「Quản lý chất lượng → Gửi kiểm tra đầu tiên」; hồ sơ tại「Hồ sơ sản phẩm đầu tiên」.</p>
<ol>
<li>Chọn mẫu sản phẩm đầu tiên (đầu mẫu là mã sản phẩm + công đoạn), tải bản nháp.</li>
<li>Điền nội dung bảng, chèn ảnh hiện trường; có thể lưu nháp hoặc gửi trực tiếp.</li>
<li>Tích「Đánh dấu bất thường」và điền mô tả, rồi nhấn「Báo cáo phiếu bất thường」.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>Sản phẩm đầu tiên và tuần tra đều báo cáo <strong>phiếu bất thường chất lượng</strong> (kiểm tra thiết bị báo cáo phiếu đề nghị sửa chữa thiết bị — hai loại khác nhau). Sản phẩm đầu tiên <strong>không có bảng nhiệm vụ</strong>, nên trang hồ sơ không hiển thị thẻ「tỷ lệ hoàn thành nhiệm vụ」. Phán định tự động theo SPEC và thống kê ba cấp cũng được áp dụng (xem chuyên mục).</blockquote>`},{id:"qc-template",title:"Mẫu kiểm tra và trường tùy chỉnh",body:`<p>Mẫu tuần tra và mẫu sản phẩm đầu tiên đều được duy trì bằng「nhập Excel + bản nháp rich text」, lối vào tại menu「Quản trị hệ thống → Mẫu tuần tra / Mẫu sản phẩm đầu tiên」. Trường khác nhau ở đầu mẫu: tuần tra là「Dây chuyền / Ca」, sản phẩm đầu tiên là「Mã sản phẩm / Công đoạn」.</p>
<ol>
<li>Nhấn「Tạo mẫu mới」, điền mã mẫu, tên mẫu, có thể điền thêm tên tiếng Việt và mô tả.</li>
<li>Nhấn「Nhập Excel tạo bản nháp」; khi có nhiều sheet thì chọn sheet cần chuyển; ô gộp được giữ thành tiêu đề gộp.</li>
<li>Chỉnh bản nháp trong trình soạn thảo rich text, nếu cần thì thay thế tệp Excel gốc lưu trữ.</li>
<li>Nhấn「Lưu mẫu」; sau đó có thể「Kích hoạt / Vô hiệu / Xóa」.</li>
</ol>
<p><strong>Trường tùy chỉnh của mẫu</strong>: menu「Quản trị hệ thống → Quản lý trường tùy chỉnh của mẫu」(cần quyền tương ứng). Có thể thêm trường ngang cho mẫu (như khách hàng, chủng loại máy, số lệnh sản xuất); phạm vi áp dụng gồm「Mẫu kiểm tra / Mẫu tuần tra / Mẫu sản phẩm đầu tiên」và các hạng mục nhỏ của chúng.</p>
<table>
<thead><tr><th>Mục cấu hình</th><th>Mô tả</th></tr></thead>
<tbody>
<tr><td>Khóa trường</td><td>Khóa tiếng Anh ổn định do hệ thống tự tạo</td></tr>
<tr><td>Nhãn (tiếng Trung) / Nhãn (tiếng Việt)</td><td>Nhãn song ngữ</td></tr>
<tr><td>Kiểu trường</td><td>Văn bản / Số / Ngày / Chọn danh sách (dạng chọn cần cấu hình lựa chọn song ngữ)</td></tr>
<tr><td>Nội bộ / Tùy chỉnh</td><td>Trường nội bộ có thể đổi tên, vô hiệu, sắp xếp, không thể xóa; khóa trường và kiểu không đổi được</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>① Mẫu kiểm tra thiết bị không dùng trường tùy chỉnh (bản nháp chính là mẫu), mẫu được hồ sơ tham chiếu thì không thể xóa. ② Trường tùy chỉnh cấp hạng mục nhỏ chủ yếu để cấu hình; việc có ghi giá trị hay không theo giao diện thực tế.</blockquote>`},{id:"qc-record",title:"Xem hồ sơ, báo cáo bất thường và xuất",body:`<p>Hồ sơ tuần tra, sản phẩm đầu tiên và kiểm tra thiết bị đều được xem tập trung tại đây: hỗ trợ lọc, xem chi tiết (rich text chỉ đọc), xuất Word và in PDF, đồng thời cung cấp dải thống kê theo「tiêu chí báo cáo」. Lối vào: menu「Quản lý chất lượng → Hồ sơ tuần tra / Hồ sơ sản phẩm đầu tiên / Hồ sơ kiểm tra thiết bị」.</p>
<ol>
<li>Lọc theo khoảng ngày, trạng thái (Nháp / Đã gửi), chỉ xem bất thường; tuần tra lọc theo dây chuyền, kiểm tra thiết bị lọc theo thiết bị.</li>
<li>Nhấn「Chi tiết bản ghi」để xem nội dung chỉ đọc trong ngăn kéo (bảng và ảnh hiển thị nguyên dạng).</li>
<li>Nhấn「Word」trên dòng để xuất tệp .doc; 「PDF」in qua trình duyệt rồi lưu thành PDF.</li>
<li>Hồ sơ đã báo cáo sẽ hiển thị liên kết「Phiếu bất thường」hoặc「Số phiếu sửa chữa」, nhấn vào để xem chứng từ quy trình.</li>
</ol>
<table>
<thead><tr><th>Cột</th><th>Mô tả</th></tr></thead>
<tbody>
<tr><td>Mẫu</td><td>Ảnh chụp tên mẫu (mẫu đổi tên vẫn đọc được)</td></tr>
<tr><td>Dây chuyền / Mã sản phẩm / Thiết bị</td><td>Tuần tra hiển thị dây chuyền, sản phẩm đầu tiên hiển thị mã sản phẩm, kiểm tra thiết bị hiển thị thiết bị</td></tr>
<tr><td>Người điền / Trạng thái / Kết luận</td><td>Kết luận là「Đạt」hoặc「Bất thường (đã báo cáo)」, do người dùng đánh dấu thủ công</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>① Dải thống kê (tỷ lệ hoàn thành nhiệm vụ / tỷ lệ đạt / tỷ lệ bất thường / tỷ lệ đóng) <strong>đều theo tiêu chí báo cáo thủ công</strong>. ② Xuất PDF đi qua in của trình duyệt, vui lòng chọn「Lưu thành PDF」trong hộp thoại in. ③ Sau khi gửi, nội dung cố định nhưng vẫn có thể bổ sung ảnh đính kèm.</blockquote>`}]},{id:"doc",title:"Tài liệu hệ thống",sections:[{id:"doc-ledger",title:"Tổng quan tài liệu kiểm soát",body:`<p>「Tổng quan tài liệu kiểm soát」liệt kê các tài liệu kiểm soát đã phát hành, là lối vào để tra cứu tài liệu đang dùng tại hiện trường. Lối vào: menu「Tài liệu hệ thống → Tổng quan tài liệu kiểm soát」; góc trên bên phải còn có hai lối vào「Kho công khai」và「Sổ theo dõi」.</p>
<ol>
<li>Lọc tài liệu theo từ khóa, phân loại, cấp, mức mật.</li>
<li>Nhấn vào một dòng bất kỳ để vào「Chi tiết tài liệu」, xem nội dung song ngữ, lịch sử phiên bản, bản gốc kiểm soát và tài liệu liên quan.</li>
<li>Nhấn「Sổ theo dõi」để vào「Sổ theo dõi tài liệu hệ thống」, chuyển giữa 7 loại sổ và xuất Excel theo ngôn ngữ giao diện hiện tại.</li>
</ol>
<table>
<thead><tr><th>Loại sổ</th><th>Nội dung</th></tr></thead>
<tbody>
<tr><td>Tổng quan tài liệu kiểm soát</td><td>Danh sách tài liệu kiểm soát (mặc định chỉ xem đã phát hành)</td></tr>
<tr><td>Ghi nhận cấp phát thu hồi / Danh sách hủy bỏ / Ghi nhận tiêu hủy</td><td>Ghi nhận quá trình cấp phát thu hồi, hủy bỏ, tiêu hủy</td></tr>
<tr><td>Đăng ký mượn / Danh sách tài liệu bên ngoài / Ghi nhận thẩm định</td><td>Ghi nhận mượn, tài liệu bên ngoài, thẩm định định kỳ</td></tr>
</tbody>
</table>
<blockquote><strong>Lưu ý:</strong>①「Đã phát hành」= trạng thái tài liệu là「Đã phát hành」; trang này <strong>mặc định chỉ hiển thị tài liệu đã phát hành</strong>. ② Tài liệu bản nháp / đang thẩm định vui lòng xem tại「Sổ theo dõi tài liệu hệ thống」. ③ Tài liệu có mức mật「Mật」chỉ xem trước trực tuyến (có hình mờ), <strong>cấm tải xuống và in</strong> (máy chủ kiểm tra bắt buộc).</blockquote>`},{id:"doc-issue",title:"Quy trình phát hành tài liệu",body:`<p>Phát hành kiểm soát là quy trình phê duyệt để phát hành chính thức một tài liệu đến các bộ phận liên quan và chuyển thành「Đã phát hành」. Lối vào khởi tạo nằm ở trang chi tiết tài liệu (trạng thái bản nháp) hoặc trang phát hành.</p>
<ol>
<li>Mở chi tiết tài liệu → nhấn「Phát hành kiểm soát」, chọn「Bộ phận nhận đợt đầu」(tức phạm vi phát hành, đồng thời là đối tượng đào tạo).</li>
<li>Chuỗi phê duyệt lần lượt: <strong>Trợ lý hệ thống kiểm định dạng → Bốn bộ phận + kỹ sư hệ thống ký đồng thời (≥4 người) → Trưởng bộ phận duyệt → Phê duyệt có điều kiện</strong> (sổ tay quản lý → Tổng giám đốc; loại sản phẩm → Chủ quản bộ phận; còn lại → Đại diện quản lý) <strong>→ Phản hồi phát hành → Xác nhận khép kín phát hành</strong>.</li>
<li>Sau khi quy trình hoàn tất, trạng thái tài liệu chuyển thành「Đã phát hành」và xuất hiện trong「Tổng quan tài liệu kiểm soát」.</li>
<li>Có thể xem thanh bước và dòng thời gian các nút tại chi tiết tài liệu hoặc trang「Phát hành kiểm soát」.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>① Phát hành và hủy bỏ đều là <strong>phê duyệt theo quy trình</strong>, thao tác phê duyệt thực hiện tại「Chờ tôi phê duyệt」. ② Nút「Phản hồi phát hành」cần điền thông tin thực hiện như đóng dấu, cấp phát, số đăng ký; khép kín xong mới coi là hoàn tất quy trình. ③ Biểu mẫu cấp 4 có thể bỏ qua thẩm định để phát hành trực tiếp, là trường hợp đặc biệt (xem gợi ý cạnh nút).</blockquote>`},{id:"doc-obsolete",title:"Quy trình hủy bỏ tài liệu",body:`<p>Việc hủy bỏ tài liệu đã phát hành không còn「một nút là xong」mà đi theo quy trình phê duyệt đồng dạng với phát hành; chỉ sau khi quy trình khép kín tài liệu mới thực sự chuyển thành「Đã hủy bỏ」. Lối vào tại「Yêu cầu hủy bỏ」trong trang chi tiết tài liệu đã phát hành.</p>
<ol>
<li>Mở chi tiết tài liệu đã phát hành → nhấn「Yêu cầu hủy bỏ」, <strong>bắt buộc điền lý do hủy bỏ</strong>; nếu có tài liệu thay thế thì điền mã tài liệu thay thế.</li>
<li>Chuỗi phê duyệt: <strong>Trợ lý hệ thống rà soát → Bốn bộ phận + kỹ sư hệ thống ký đồng thời → Trưởng bộ phận duyệt → Phê duyệt có điều kiện → Phản hồi thực hiện hủy bỏ (thu hồi / tiêu hủy / số đăng ký) → Xác nhận hủy bỏ khép kín</strong>.</li>
<li>Trong thời gian chờ, tài liệu <strong>vẫn hiển thị là「Đã phát hành」</strong>(trạng thái chờ được thể hiện bằng phiên bản quy trình); chỉ sau khi phê duyệt mới chuyển thành「Đã hủy bỏ」và được ghi vào「Danh sách hủy bỏ」.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>① Khi cùng một tài liệu đã có yêu cầu hủy bỏ đang chờ thì không thể khởi tạo lại. ② Sau khi hủy bỏ không thể khôi phục. ③ Lối vào danh sách hủy bỏ: menu「Tài liệu hệ thống → Danh sách hủy bỏ」.</blockquote>`},{id:"doc-borrow",title:"Mượn và cấp phát tài liệu",body:`<p>Chương này tương ứng hai loại ghi nhận「cấp phát thu hồi」và「mượn tài liệu」, đều xem và xuất dưới dạng sổ theo dõi.</p>
<p><strong>Ghi nhận cấp phát thu hồi</strong>: menu「Tài liệu hệ thống → Ghi nhận cấp phát thu hồi」. Cột: Loại ghi nhận, Mã tài liệu, Phiên bản, Bộ phận, Người giữ, Số bản, Ngày thao tác, Người thao tác, Lý do.</p>
<p><strong>Đăng ký mượn</strong>: lối vào riêng <code>/doc-borrow</code>, hoặc chuyển loại sang「Đăng ký mượn」trong「Sổ theo dõi tài liệu hệ thống」. Cột: Mã tài liệu, Phiên bản, Người mượn, Mục đích, Ngày mượn, Ngày phải trả, Ngày trả, Trạng thái.</p>
<ol>
<li>Vào sổ tương ứng, lọc theo ngày và từ khóa.</li>
<li>Nhấn「Xuất Excel」ở góc trên bên phải; tiêu đề cột được tạo theo ngôn ngữ giao diện hiện tại.</li>
</ol>
<blockquote><strong>Lưu ý:</strong>① Thao tác liên quan đến mượn tài liệu cần quyền「mượn tài liệu hệ thống」. ② Trang này chủ yếu phục vụ <strong>tra cứu và xuất sổ theo dõi</strong>; lối vào cụ thể để khởi tạo mượn hoặc đăng ký trả theo giao diện thực tế.</blockquote>`}]}];export{t as default};
