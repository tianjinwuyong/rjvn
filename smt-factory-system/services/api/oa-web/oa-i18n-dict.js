/* ==========================================================================
   OA 独立页面多语言字典（中文原文 → 越南语 / 英语）
   --------------------------------------------------------------------------
   · 键是界面上真实出现的中文，与页面/脚本逐字一致；`{1} {2}` 为插值位。
   · 只放数据，不含逻辑。新增页面时在这张表里加一段即可。
   · 单字（一/二/…/日、天、人 等）不进表：同字不同义会误翻，
     星期几由 OAI18N.weekdays() 提供。
   ========================================================================== */
window.OA_I18N_DICT = {

  /* ================= 通用 / 登录 ================= */
  'OA协同管理平台': { vi: 'Nền tảng quản trị OA', en: 'OA Management Platform' },
  '用户名': { vi: 'Tên đăng nhập', en: 'Username' },
  '密码': { vi: 'Mật khẩu', en: 'Password' },
  '登录': { vi: 'Đăng nhập', en: 'Sign in' },
  '登录失败': { vi: 'Đăng nhập thất bại', en: 'Sign-in failed' },
  '登录已失效，请重新登录': { vi: 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại', en: 'Session expired. Please sign in again' },
  '未登录': { vi: 'Chưa đăng nhập', en: 'Not signed in' },
  '请输入用户名和密码': { vi: 'Vui lòng nhập tên đăng nhập và mật khẩu', en: 'Please enter your username and password' },
  '加载中…': { vi: 'Đang tải…', en: 'Loading…' },
  '系统管理员': { vi: 'Quản trị hệ thống', en: 'System administrator' },
  '普通用户': { vi: 'Người dùng thường', en: 'Standard user' },

  /* ================= 侧边栏 / 顶栏（oa-shell.js） ================= */
  '我的工作台': { vi: 'Bảng làm việc của tôi', en: 'My Workspace' },
  '体系文件': { vi: 'Tài liệu hệ thống', en: 'System Documents' },
  '公共盘': { vi: 'Ổ đĩa chung', en: 'Shared Drive' },
  '知识共享': { vi: 'Chia sẻ tri thức', en: 'Knowledge Sharing' },
  '品质管理': { vi: 'Quản lý chất lượng', en: 'Quality Management' },
  '设备管理': { vi: 'Quản lý thiết bị', en: 'Equipment Management' },
  '人事管理': { vi: 'Quản lý nhân sự', en: 'HR Management' },
  '系统管理': { vi: 'Quản trị hệ thống', en: 'System Settings' },
  '搜索菜单': { vi: 'Tìm kiếm menu', en: 'Search menu' },
  '收起 / 展开菜单': { vi: 'Thu gọn / mở rộng menu', en: 'Collapse / expand menu' },
  '刷新页面': { vi: 'Tải lại trang', en: 'Refresh page' },
  '切换界面配色': { vi: 'Đổi màu giao diện', en: 'Change theme colour' },
  '使用说明': { vi: 'Hướng dẫn sử dụng', en: 'Help' },
  '返回工作台': { vi: 'Về bảng làm việc', en: 'Back to workspace' },
  '退出登录': { vi: 'Đăng xuất', en: 'Sign out' },
  '界面配色：': { vi: 'Màu giao diện: ', en: 'Theme: ' },
  '经典蓝': { vi: 'Xanh cổ điển', en: 'Classic blue' },
  '科技蓝': { vi: 'Xanh công nghệ', en: 'Tech blue' },
  '靛蓝': { vi: 'Xanh chàm', en: 'Indigo' },
  '琥珀深色': { vi: 'Hổ phách tối', en: 'Amber dark' },
  '侧边栏可返回各业务模块；本页仅管理员可见，配置保存后立即生效。': {
    vi: 'Thanh bên giúp quay lại các phân hệ nghiệp vụ; trang này chỉ quản trị viên thấy, cấu hình có hiệu lực ngay sau khi lưu.',
    en: 'The sidebar returns you to each module. This page is admin-only; saved settings take effect immediately.'
  },

  /* ================= 人事 / 工资 公共页签 ================= */
  '员工花名册': { vi: 'Danh sách nhân viên', en: 'Employee roster' },
  '考勤管理': { vi: 'Quản lý chấm công', en: 'Attendance' },
  '考勤与排班': { vi: 'Chấm công & xếp ca', en: 'Attendance & Shifts' },
  '工作日历': { vi: 'Lịch làm việc', en: 'Work calendar' },
  '工资结构': { vi: 'Cơ cấu lương', en: 'Salary structure' },
  '工资核算 v2': { vi: 'Tính lương v2', en: 'Payroll v2' },
  '薪资核算': { vi: 'Tính lương', en: 'Payroll' },
  '工资核算': { vi: 'Tính lương', en: 'Payroll' },
  '越盾': { vi: 'VND', en: 'VND' },

  /* ================= 工作日历（work-calendar.html） ================= */
  '工作日历维护': { vi: 'Quản lý lịch làm việc', en: 'Work Calendar' },
  '工作日历 · 越南工厂': { vi: 'Lịch làm việc · Nhà máy Việt Nam', en: 'Work Calendar · Vietnam Plant' },
  '工作日历维护 - OA协同管理平台': { vi: 'Quản lý lịch làm việc - Nền tảng quản trị OA', en: 'Work Calendar - OA Management Platform' },
  '按自然周排列（周一 → 周日）· 逐日权重：全天 / 半天 / 休息 · 保存后立即参与考勤与薪资计算': {
    vi: 'Xếp theo tuần (Thứ 2 → Chủ nhật) · Trọng số từng ngày: cả ngày / nửa ngày / nghỉ · Lưu xong là tham gia tính chấm công và lương ngay',
    en: 'Aligned by calendar week (Mon → Sun) · Daily weight: full day / half day / rest · Takes effect in attendance and payroll immediately after saving'
  },
  '刷新': { vi: 'Tải lại', en: 'Refresh' },
  '上一月': { vi: 'Tháng trước', en: 'Previous month' },
  '下一月': { vi: 'Tháng sau', en: 'Next month' },
  '本月': { vi: 'Tháng này', en: 'This month' },
  '规则': { vi: 'Quy tắc', en: 'Rule' },
  '按规则生成': { vi: 'Tạo theo quy tắc', en: 'Generate by rule' },
  '保存': { vi: 'Lưu', en: 'Save' },
  '全天': { vi: 'Cả ngày', en: 'Full day' },
  '半天': { vi: 'Nửa ngày', en: 'Half day' },
  '休息': { vi: 'Nghỉ', en: 'Rest' },
  '法定节假日': { vi: 'Ngày lễ pháp định', en: 'Public holiday' },
  '今天': { vi: 'Hôm nay', en: 'Today' },
  '五天工作制': { vi: 'Làm 5 ngày/tuần', en: '5-day week' },
  '六天工作制': { vi: 'Làm 6 ngày/tuần', en: '6-day week' },
  '大小周': { vi: 'Tuần xen kẽ', en: 'Alternating weeks' },
  '自定义': { vi: 'Tùy chỉnh', en: 'Custom' },
  '本月天数': { vi: 'Số ngày trong tháng', en: 'Days in month' },
  '折合工作日': { vi: 'Ngày công quy đổi', en: 'Converted workdays' },
  '休息日': { vi: 'Ngày nghỉ', en: 'Rest days' },
  '有未保存的修改': { vi: 'Có thay đổi chưa lưu', en: 'Unsaved changes' },
  '已与库一致': { vi: 'Đã khớp với dữ liệu', en: 'Matches saved data' },
  '假日取自内置清单（服务未重启）': {
    vi: 'Ngày lễ lấy từ danh sách nội bộ (dịch vụ chưa khởi động lại)',
    en: 'Holidays from built-in list (service not restarted yet)'
  },
  '库中规则：': { vi: 'Quy tắc đã lưu: ', en: 'Saved rule: ' },
  '库中还没有这个月': { vi: 'Chưa có cấu hình cho tháng này', en: 'This month is not configured yet' },
  '天': { vi: 'ngày', en: 'days' },
  '修改日历需要「考勤管理」权限（attend:manage）': {
    vi: 'Sửa lịch cần quyền 「Quản lý chấm công」(attend:manage)',
    en: 'Editing the calendar requires the Attendance permission (attend:manage)'
  },
  '当前账号只有查看权限，修改需要「考勤管理」（attend:manage）': {
    vi: 'Tài khoản hiện tại chỉ có quyền xem; muốn sửa cần quyền 「Quản lý chấm công」(attend:manage)',
    en: 'This account is read-only; editing requires the Attendance permission (attend:manage)'
  },
  '需要「考勤管理」权限（attend:manage）才能保存': {
    vi: 'Cần quyền 「Quản lý chấm công」(attend:manage) để lưu',
    en: 'Attendance permission (attend:manage) is required to save'
  },
  '需要「考勤管理」权限（attend:manage）才能修改': {
    vi: 'Cần quyền 「Quản lý chấm công」(attend:manage) để sửa',
    en: 'Attendance permission (attend:manage) is required to edit'
  },
  '没有「考勤管理」权限（attend:manage），无法保存': {
    vi: 'Không có quyền 「Quản lý chấm công」(attend:manage), không thể lưu',
    en: 'Missing Attendance permission (attend:manage); cannot save'
  },
  '接口不存在（/api/attendance/calendar）': {
    vi: 'Không tìm thấy API (/api/attendance/calendar)',
    en: 'Endpoint not found (/api/attendance/calendar)'
  },
  '法定节假日加班按 3.0 / 4.1 倍率计酬': {
    vi: 'Làm thêm vào ngày lễ tính theo hệ số 3.0 / 4.1',
    en: 'Work on a public holiday is paid at 3.0 / 4.1×'
  },
  '与周休重叠，顺延补休': { vi: 'Trùng ngày nghỉ tuần, nghỉ bù sau', en: 'Falls on a weekly rest day, compensatory leave' },
  '已保存：': { vi: 'Đã lưu: ', en: 'Saved: ' },

  /* 含插值的句子（调用点用 tf() 显式替换，不参与 DOM 自动匹配） */
  '本月有 {1} 天越南法定节假日（{2}），已自动置为休息。': {
    vi: 'Tháng này có {1} ngày lễ pháp định Việt Nam ({2}), đã tự động đặt là nghỉ.',
    en: 'This month has {1} Vietnamese public holidays ({2}); set to rest automatically.'
  },
  '{1} 尚未配置。下方是按「{2}」给出的预演，点「保存」才会写入，在此之前不影响考勤计算。': {
    vi: '{1} chưa được cấu hình. Bên dưới là bản xem trước theo 「{2}」; chỉ khi bấm 「Lưu」 mới ghi vào hệ thống, trước đó không ảnh hưởng tính chấm công.',
    en: '{1} is not configured. Below is a preview based on 「{2}」; nothing is written until you click Save, and attendance is unaffected until then.'
  },
  '加载 {1} 失败：{2}': { vi: 'Tải {1} thất bại: {2}', en: 'Failed to load {1}: {2}' },
  '{1} 有未保存的修改，切换后会丢弃。继续？': {
    vi: '{1} có thay đổi chưa lưu, chuyển đi sẽ mất. Tiếp tục?',
    en: '{1} has unsaved changes that will be lost. Continue?'
  },
  ' 等 {1} 天': { vi: ' và {1} ngày khác', en: ' and {1} more days' },
  '{1} 现有 {2} 天与「{3}」的结果不同：': {
    vi: '{1} hiện có {2} ngày khác với kết quả của 「{3}」:',
    en: '{1} has {2} days that differ from the 「{3}」 result:'
  },
  '通常是法定节假日或调休，按规则生成会把它们改回规则值。': {
    vi: 'Thường là ngày lễ hoặc nghỉ bù; tạo theo quy tắc sẽ đưa chúng về giá trị của quy tắc.',
    en: 'Usually public holidays or make-up days; generating by rule will reset them to the rule value.'
  },
  '确定覆盖吗？（点取消可保留现状）': {
    vi: 'Xác nhận ghi đè? (Bấm Hủy để giữ nguyên hiện trạng)',
    en: 'Overwrite? (Click Cancel to keep the current data)'
  },
  '；{1} 天法定节假日已自动置为休息': {
    vi: '; {1} ngày lễ pháp định đã tự động đặt là nghỉ',
    en: '; {1} public holidays were set to rest automatically'
  },
  '已按「{1}」覆盖 {2}{3}，可继续点格子微调，然后保存': {
    vi: 'Đã áp dụng 「{1}」 cho {2}{3}; có thể bấm vào ô để chỉnh tiếp rồi lưu',
    en: 'Applied 「{1}」 to {2}{3}; click cells to fine-tune, then save'
  },
  '{1} 是法定节假日「{2}」，恒为休息、按节假日倍率计酬；如需调整请先修改假日表': {
    vi: '{1} là ngày lễ pháp định 「{2}」, luôn là nghỉ và tính theo hệ số ngày lễ; muốn điều chỉnh hãy sửa bảng ngày lễ trước',
    en: '{1} is the public holiday 「{2}」 — always a rest day and paid at the holiday rate; change the holiday table first if you need to adjust it'
  },
  '（{1} 已按假日强制休息）': {
    vi: ' ({1} đã bị buộc đặt là nghỉ theo ngày lễ)',
    en: ' ({1} were forced to rest as public holidays)'
  },
  '，含 {1} 天法定节假日': { vi: ', gồm {1} ngày lễ pháp định', en: ', including {1} public holidays' },
  '，全天 {1} 天 / 休息 {2} 天 / 折合 {3} 个工作日': {
    vi: ', cả ngày {1} ngày / nghỉ {2} ngày / quy đổi {3} ngày công',
    en: ', {1} full days / {2} rest days / {3} converted workdays'
  },
  '保存失败：{1}': { vi: 'Lưu thất bại: {1}', en: 'Save failed: {1}' },
  '，已参与考勤与薪资计算': {
    vi: ', đã tham gia tính chấm công và lương',
    en: ', now included in attendance and payroll'
  },

  /* 工作日历页内说明块（整块 HTML 替换） */
  'wc.help': {
    vi: '<b>Cách dùng:</b> chọn tháng → chọn quy tắc → bấm 「Tạo theo quy tắc」 để phủ cả tháng → nếu cần thì bấm vào ô để chỉnh (cả ngày → nửa ngày → nghỉ, lặp lại) → bấm 「Lưu」. ' +
        '<b>Đổi quy tắc sẽ tính lại bản xem trước ngay</b>, không phải bấm tạo lại; không bấm lưu thì không ghi vào hệ thống.' +
        '<br />' +
        '<b>Quy ước làm 6 ngày/tuần:</b> mặc định Thứ 7 cả ngày, Chủ nhật nghỉ. Nếu Thứ 7 chỉ làm nửa ngày, sau khi tạo hãy bấm ô Thứ 7 đổi thành 「Nửa ngày」 rồi lưu. ' +
        '<b>Nửa ngày = 0,5 ngày công</b>, tham gia quy đổi 「27 ngày công đủ」 và cả cách tính cơ sở làm thêm.' +
        '<br />' +
        '<b>Ngày lễ pháp định Việt Nam (đã nhập sẵn đến 2030):</b> theo Điều 112 Bộ luật Lao động — mỗi năm Tết Dương lịch 1 ngày, Tết Nguyên đán 5 ngày (Giao thừa + Mùng 1–4), Giỗ Tổ Hùng Vương 1 ngày, 30/4 và 1/5 là 2 ngày, Quốc khánh 2 ngày; trùng ngày nghỉ tuần thì nghỉ bù theo Điều 111. ' +
        'Trên lịch hiển thị <b>nền đỏ + tên ngày lễ</b>, <b>luôn là nghỉ, không đổi thành ngày làm được</b>; ngày nghỉ bù có viền nét đứt. ' +
        'Làm việc ngày lễ tính theo hệ số 3.0 / 4.1. Danh sách lấy từ bảng <code>attendance_holiday</code>, <b>2027–2030 là giá trị tính trước theo âm lịch và quy tắc trên</b>; khi có công bố chính thức chỉ cần cập nhật dữ liệu, lịch tự theo.' +
        '<br />' +
        '<b>Đổi ngày nghỉ (đổi Chủ nhật thành ngày làm):</b> bấm ô đổi thành 「Cả ngày」. Những tháng như vậy <b>đừng bấm thẳng 「Tạo theo quy tắc」</b> — ' +
        'hệ thống sẽ báo trước những ngày khác quy tắc, xác nhận mới ghi đè; bấm 「Hủy」 để giữ nguyên. 「Tải lại」 luôn đưa về trạng thái đã lưu gần nhất.' +
        '<br />' +
        '<b>Tháng chưa cấu hình:</b> khi mở sẽ hiện bản xem trước theo quy tắc hiện tại (thanh vàng phía trên), bấm lưu mới ghi vào; không tự nhảy về chế độ 5 ngày như trước.',
    en: '<b>How to use:</b> pick a month → pick a rule → click 「Generate by rule」 to cover the whole month → click cells to fine-tune if needed (full day → half day → rest, cycling) → click 「Save」. ' +
        '<b>Changing the rule recomputes the preview immediately</b>; no need to regenerate. Nothing is written until you save.' +
        '<br />' +
        '<b>6-day week convention:</b> Saturday full day, Sunday off by default. If Saturday is only half a day, after generating click the Saturday cell and change it to 「Half day」, then save. ' +
        '<b>A half day = 0.5 workday</b> and counts toward the 「27 workdays for full attendance」 conversion and the overtime base.' +
        '<br />' +
        '<b>Vietnamese public holidays (built in through 2030):</b> per Article 112 of the Labour Code — New Year 1 day, Tet 5 days (New Year\'s Eve + days 1–4), Hung Kings 1 day, 30 Apr & 1 May 2 days, National Day 2 days; when they fall on a weekly rest day, compensatory leave applies under Article 111. ' +
        'On the calendar they appear with a <b>red background and the holiday name</b>, are <b>always rest days and cannot be turned into workdays</b>; compensatory days have a dashed border. ' +
        'Work on a holiday is paid at 3.0 / 4.1×. The list comes from the <code>attendance_holiday</code> table; <b>2027–2030 are pre-computed from the lunar calendar and the rule above</b> — just update the data once officially announced and the calendar follows.' +
        '<br />' +
        '<b>Make-up workdays (turning Sunday into a workday):</b> click the cell until it reads 「Full day」. For such months <b>do not click 「Generate by rule」 directly</b> — ' +
        'the system first lists the days that differ from the rule and only overwrites after you confirm; click Cancel to keep the current state. 「Refresh」 always restores the last saved state.' +
        '<br />' +
        '<b>Unconfigured months:</b> opening one shows a preview based on the current rule (yellow bar on top); it is only written when you save, and it no longer silently falls back to the 5-day week.'
  },

  /* ================= 越南法定节假日名称 ================= */
  '元旦': { vi: 'Tết Dương lịch', en: "New Year's Day" },
  '元旦·顺延补休': { vi: 'Nghỉ bù Tết Dương lịch', en: "New Year's Day (observed)" },
  '春节·除夕': { vi: 'Tết Nguyên đán (Giao thừa)', en: 'Tet holiday - New Year\'s Eve' },
  '春节·正月初一': { vi: 'Tết Nguyên đán (Mùng 1)', en: 'Tet holiday - Day 1' },
  '春节·正月初二': { vi: 'Tết Nguyên đán (Mùng 2)', en: 'Tet holiday - Day 2' },
  '春节·正月初三': { vi: 'Tết Nguyên đán (Mùng 3)', en: 'Tet holiday - Day 3' },
  '春节·正月初四': { vi: 'Tết Nguyên đán (Mùng 4)', en: 'Tet holiday - Day 4' },
  '春节·顺延补休': { vi: 'Nghỉ bù Tết Nguyên đán', en: 'Tet holiday (observed)' },
  '春节·顺延补休 1': { vi: 'Nghỉ bù Tết Nguyên đán (1)', en: 'Tet holiday (observed 1)' },
  '春节·顺延补休 2': { vi: 'Nghỉ bù Tết Nguyên đán (2)', en: 'Tet holiday (observed 2)' },
  '雄王纪念日': { vi: 'Giỗ Tổ Hùng Vương', en: 'Hung Kings Commemoration Day' },
  '雄王纪念日·顺延补休': { vi: 'Nghỉ bù Giỗ Tổ Hùng Vương', en: 'Hung Kings Commemoration Day (observed)' },
  '南方解放日': { vi: 'Ngày Giải phóng miền Nam', en: 'Reunification Day' },
  '南方解放日·顺延补休': { vi: 'Nghỉ bù ngày 30/4', en: 'Reunification Day (observed)' },
  '国际劳动节': { vi: 'Ngày Quốc tế Lao động', en: 'International Labour Day' },
  '劳动节·顺延补休': { vi: 'Nghỉ bù ngày 1/5', en: 'Labour Day (observed)' },
  '国庆节': { vi: 'Quốc khánh', en: 'National Day' },
  '国庆节·第2天': { vi: 'Quốc khánh (ngày thứ 2)', en: 'National Day - Day 2' },
  '国庆节·顺延补休': { vi: 'Nghỉ bù Quốc khánh', en: 'National Day (observed)' },
  '国庆节·顺延补休 1': { vi: 'Nghỉ bù Quốc khánh (1)', en: 'National Day (observed 1)' },
  '国庆节·顺延补休 2': { vi: 'Nghỉ bù Quốc khánh (2)', en: 'National Day (observed 2)' },

  /* ================= 工资结构（salary-console.html） ================= */
  '工资结构 - OA协同管理平台': { vi: 'Cơ cấu lương - Nền tảng quản trị OA', en: 'Salary Structure - OA Management Platform' },
  '工资结构 · 越南工厂': { vi: 'Cơ cấu lương · Nhà máy Việt Nam', en: 'Salary Structure · Vietnam Plant' },
  '需要「工资管理」权限（salary:manage）': {
    vi: 'Cần quyền 「Quản lý tiền lương」(salary:manage)',
    en: 'Requires the Payroll permission (salary:manage)'
  },
  '月薪制 · 薪酬项目字典驱动 · 版本化生效 · 时薪分母固定 208': {
    vi: 'Lương tháng · Điều khiển bằng danh mục khoản lương · Hiệu lực theo phiên bản · Mẫu số lương giờ cố định 208',
    en: 'Monthly salary · Item-dictionary driven · Versioned effective dates · Hourly divisor fixed at 208'
  },
  '薪资结构': { vi: 'Cơ cấu lương', en: 'Salary structure' },
  '薪酬项目字典': { vi: 'Danh mục khoản lương', en: 'Salary item dictionary' },
  '职类与分配': { vi: 'Nhóm chức danh & phân bổ', en: 'Job classes & assignment' },
  '这一版界面改了什么': { vi: 'Giao diện phiên bản này đã đổi gì', en: 'What changed in this version' },
  '✕ 删掉「加班费率 1.5 / 2.0 / 3.0」': { vi: '✕ Bỏ 「Hệ số làm thêm 1.5 / 2.0 / 3.0」', en: '✕ Removed 「OT rate 1.5 / 2.0 / 3.0」' },
  '✕ 删掉「计入班次津贴」开关': { vi: '✕ Bỏ công tắc 「Tính phụ cấp ca」', en: '✕ Removed the 「include shift allowance」 switch' },
  '✕ 删掉「社保 8% / 1.5% / 1% + 封顶 106,200,000」': {
    vi: '✕ Bỏ 「BHXH 8% / 1,5% / 1% + mức trần 106.200.000」',
    en: '✕ Removed 「insurance 8% / 1.5% / 1% + cap 106,200,000」'
  },
  '✓ 新增「薪酬项目字典」': { vi: '✓ Thêm 「Danh mục khoản lương」', en: '✓ Added 「Salary item dictionary」' },

  /* —— 整块说明（含内联标签，键为整段文字） —— */
  '倍率现在只有一处真值：14 段时段倍率表（工资核算 → 时段倍率）。结构里再存一份，就会出现「改了倍率没生效」或「两个地方不一样谁对」的问题。': {
    vi: 'Hệ số giờ chỉ còn một nguồn duy nhất: bảng hệ số 14 khung giờ (Tính lương → Hệ số khung giờ). Nếu lưu thêm một bản trong cơ cấu, sẽ xảy ra 「đổi hệ số mà không có hiệu lực」 hoặc 「hai nơi khác nhau thì tin nơi nào」.',
    en: 'Rates now have a single source of truth: the 14-band rate table (Payroll → Time bands). Storing another copy in the structure causes 「changed the rate but nothing happened」 or 「two places disagree, which is right」.'
  },
  '新口径下夜班津贴 = 夜班各段的倍率差（②1.0 → ③1.3）自然产生，是算出来的，不是发一笔固定的。开关留着等于让人重复给钱。': {
    vi: 'Theo cách tính mới, phụ cấp ca đêm = chênh lệch hệ số giữa các khung ca đêm (②1,0 → ③1,3) tự sinh ra, là tính toán chứ không phải một khoản cố định. Giữ công tắc lại chỉ khiến người ta trả tiền hai lần.',
    en: 'Under the new rules the night-shift allowance emerges from the rate difference between night bands (②1.0 → ③1.3) — it is computed, not paid as a fixed amount. Keeping the switch just lets people pay twice.'
  },
  '这三项以前写在每个员工的明细里，改一次政策要改几百条。现在统一在 社保与参数 → 分险种费率 按生效日维护，且三个险种封顶各不相同（养老/医疗 46.8M、失业 106.2M）。': {
    vi: 'Ba khoản này trước đây ghi trong chi tiết từng nhân viên, đổi chính sách một lần phải sửa hàng trăm dòng. Nay giữ tập trung ở BHXH & tham số → Tỷ lệ theo từng loại bảo hiểm, quản lý theo ngày hiệu lực, và mức trần ba loại khác nhau (hưu trí/y tế 46,8 triệu; thất nghiệp 106,2 triệu).',
    en: 'These three used to be written into each employee\'s detail line, so one policy change meant editing hundreds of rows. They now live in Insurance & parameters → per-scheme rates, maintained by effective date, with different caps (pension/health 46.8M, unemployment 106.2M).'
  },
  '每个项目带 5 个属性位：计入时薪基数、计入社保基数、计税、免税规则、按出勤折算。以后加「高温补贴」只是字典加一行 + 结构里填个金额，不改代码、不发版。': {
    vi: 'Mỗi khoản có 5 thuộc tính: tính vào cơ sở lương giờ, tính vào cơ sở BHXH, chịu thuế, quy tắc miễn thuế, quy đổi theo chấm công. Sau này thêm 「phụ cấp nóng」 chỉ là thêm một dòng danh mục + nhập số tiền trong cơ cấu, không sửa mã, không phát hành phiên bản.',
    en: 'Each item carries 5 attributes: counts toward the hourly base, counts toward the insurance base, taxable, tax-exemption rule, and pro-rated by attendance. Adding a 「heat allowance」 later is just one dictionary row plus an amount in the structure — no code change, no release.'
  },
  '同一对象可以有多个版本：按生效日期取最近一个已审批版本计薪；更早的版本自动补失效日，历史工资单仍按当时的版本可追。 金额全 0 的草稿可以存，但审批会被拦——避免把 0 元结构放出去。': {
    vi: 'Mỗi đối tượng có thể có nhiều phiên bản: khi tính lương lấy phiên bản đã duyệt gần nhất theo ngày hiệu lực; các phiên bản cũ hơn tự động được bổ sung ngày hết hiệu lực, phiếu lương lịch sử vẫn truy được theo phiên bản lúc đó. Bản nháp có số tiền toàn 0 vẫn lưu được, nhưng sẽ bị chặn khi duyệt — tránh đưa ra cơ cấu 0 đồng.',
    en: 'One target can have multiple versions: payroll uses the latest approved version by effective date; older versions get an end date automatically, and historical payslips remain traceable to the version in force then. A draft with all-zero amounts can be saved, but approval is blocked — to avoid letting a zero-value structure go live.'
  },
  '五个属性位就是这个项目的全部语义。「计入时薪基数」决定它进不进 时薪 = Σ / 208 的分子—— 只有基本工资和职务津贴该进，其他项目进了会虚抬时薪，把加班费一起抬上去。 「计入社保基数」决定社保缴费基数，「计税 / 免税规则」决定个税，「按出勤折算」决定月中入职离职要不要按天打折。': {
    vi: 'Năm thuộc tính chính là toàn bộ ngữ nghĩa của khoản này. 「Tính vào cơ sở lương giờ」 quyết định khoản đó có vào tử số của 时薪 = Σ / 208 hay không — chỉ lương cơ bản và phụ cấp chức vụ nên vào; khoản khác vào sẽ làm lương giờ bị thổi lên, kéo tiền làm thêm tăng theo. 「Tính vào cơ sở BHXH」 quyết định mức đóng bảo hiểm, 「Chịu thuế / Quy tắc miễn thuế」 quyết định thuế TNCN, 「Quy đổi theo chấm công」 quyết định việc vào/ra giữa tháng có bị tính theo ngày hay không.',
    en: 'The five attributes are the entire semantics of an item. 「Counts toward hourly base」 decides whether it enters the numerator of hourly rate = Σ / 208 — only base salary and job allowance should; other items inflate the hourly rate and drag overtime pay up with them. 「Counts toward insurance base」 sets the contribution base, 「Taxable / exemption rule」 sets PIT, and 「Pro-rated by attendance」 decides whether mid-month joiners/leavers are prorated by day.'
  },
  '职类模板是「批量生效」的载体：员工没有个人专属结构时，按他的职类找模板。 优先级：个人专属（已审批）＞ 职类模板（已审批）。': {
    vi: 'Mẫu theo nhóm chức danh là công cụ 「áp dụng hàng loạt」: khi nhân viên không có cơ cấu riêng, hệ thống tìm mẫu theo nhóm chức danh của họ. Ưu tiên: riêng nhân viên (đã duyệt) ＞ mẫu nhóm chức danh (đã duyệt).',
    en: 'Class templates are the vehicle for bulk effect: when an employee has no personal structure, the template for their job class is used. Priority: personal (approved) ＞ class template (approved).'
  },
  '只勾选需要变更的人；已在目标职类的人会自动跳过。入离职日期为空的人不会触发首月免扣递延，建议一并补齐。': {
    vi: 'Chỉ tích những người cần thay đổi; người đã ở nhóm đích sẽ tự động bỏ qua. Người chưa có ngày vào/ra sẽ không kích hoạt hoãn trừ tháng đầu, nên bổ sung luôn.',
    en: 'Tick only the people who need changing; those already in the target class are skipped automatically. People with no join/leave date will not trigger first-month deferred deductions — worth filling in.'
  },
  '「加班/夜班工资」不出现是正常的——它由 14 段倍率按实际打卡自动算，不是固定金额。 社保、工会费、缺勤、迟到早退同理，全部按规则自动产生。': {
    vi: 'Việc 「lương làm thêm/ca đêm」 không xuất hiện là bình thường — khoản này do hệ số 14 khung giờ tính tự động theo chấm công thực tế, không phải số tiền cố định. BHXH, phí công đoàn, vắng mặt, đi muộn/về sớm cũng vậy, tất cả tự sinh theo quy tắc.',
    en: 'It is normal that 「overtime / night-shift pay」 does not appear here — it is computed automatically from the 14 time bands against actual punches, not a fixed amount. Insurance, union fee, absence and lateness/early leave work the same way, all generated by rule.'
  },
  '计入时薪基数 —— 进入 时薪 = Σ / 208 的分子': {
    vi: 'Tính vào cơ sở lương giờ — cộng vào tử số của 时薪 = Σ / 208',
    en: 'Counts toward hourly base — enters the numerator of hourly rate = Σ / 208'
  },
  '计入社保基数 —— 进入 BHXH / BHYT / BHTN 缴费基数': {
    vi: 'Tính vào cơ sở BHXH — vào mức đóng BHXH / BHYT / BHTN',
    en: 'Counts toward insurance base — enters the BHXH / BHYT / BHTN contribution base'
  },
  '计税 —— 计入应税工资': { vi: 'Chịu thuế — tính vào thu nhập chịu thuế', en: 'Taxable — included in taxable salary' },
  '按出勤折算 —— 月中入职/离职按天打折': {
    vi: 'Quy đổi theo chấm công — vào/ra giữa tháng thì tính theo ngày',
    en: 'Prorated by attendance — mid-month joiners/leavers are prorated by day'
  },

  /* —— 结构与明细 —— */
  '结构版本': { vi: 'Phiên bản cơ cấu', en: 'Structure version' },
  '全部状态': { vi: 'Tất cả trạng thái', en: 'All statuses' },
  '全部对象': { vi: 'Tất cả đối tượng', en: 'All targets' },
  '草稿': { vi: 'Bản nháp', en: 'Draft' },
  '已审批': { vi: 'Đã duyệt', en: 'Approved' },
  '已作废': { vi: 'Đã hủy', en: 'Voided' },
  '已审批通过': { vi: 'Đã duyệt xong', en: 'Approved' },
  '职类模板': { vi: 'Mẫu nhóm chức danh', en: 'Class template' },
  '员工专属': { vi: 'Riêng nhân viên', en: 'Employee-specific' },
  '查询': { vi: 'Tìm kiếm', en: 'Search' },
  '新建结构': { vi: 'Tạo cơ cấu', en: 'New structure' },
  '绑定对象': { vi: 'Đối tượng áp dụng', en: 'Target' },
  '类型': { vi: 'Loại', en: 'Type' },
  '版本': { vi: 'Phiên bản', en: 'Version' },
  '状态': { vi: 'Trạng thái', en: 'Status' },
  '生效日': { vi: 'Ngày hiệu lực', en: 'Effective date' },
  '生效日期': { vi: 'Ngày hiệu lực', en: 'Effective date' },
  '正班工资 G': { vi: 'Lương ca chính G', en: 'Regular pay G' },
  '津贴合计': { vi: 'Tổng phụ cấp', en: 'Total allowances' },
  '月固定合计': { vi: 'Tổng cố định tháng', en: 'Monthly fixed total' },
  '时薪 G/208': { vi: 'Lương giờ G/208', en: 'Hourly G/208' },
  '覆盖人数': { vi: 'Số người áp dụng', en: 'People covered' },
  '操作': { vi: 'Thao tác', en: 'Actions' },
  '新增项目': { vi: 'Thêm khoản', en: 'Add item' },
  '编码': { vi: 'Mã', en: 'Code' },
  '名称': { vi: 'Tên', en: 'Name' },
  '越文': { vi: 'Tiếng Việt', en: 'Vietnamese' },
  '类别': { vi: 'Nhóm', en: 'Category' },
  '计算方式': { vi: 'Cách tính', en: 'Calculation' },
  '时薪基数': { vi: 'Cơ sở lương giờ', en: 'Hourly base' },
  '社保基数': { vi: 'Cơ sở BHXH', en: 'Insurance base' },
  '计税': { vi: 'Chịu thuế', en: 'Taxable' },
  '免税规则': { vi: 'Quy tắc miễn thuế', en: 'Tax exemption' },
  '出勤折算': { vi: 'Quy đổi chấm công', en: 'Attendance proration' },
  '被引用': { vi: 'Đang được dùng', en: 'In use' },
  '把员工挂到职类': { vi: 'Gán nhân viên vào nhóm', en: 'Assign employees to class' },
  '分配到所选职类': { vi: 'Gán vào nhóm đã chọn', en: 'Assign to selected class' },
  '工号': { vi: 'Mã NV', en: 'Employee ID' },
  '姓名': { vi: 'Họ tên', en: 'Name' },
  '当前职类': { vi: 'Nhóm hiện tại', en: 'Current class' },
  '个人专属结构': { vi: 'Cơ cấu riêng', en: 'Personal structure' },
  '入职日期': { vi: 'Ngày vào làm', en: 'Hire date' },
  '新建薪资结构': { vi: 'Tạo cơ cấu lương', en: 'New salary structure' },
  '关闭': { vi: 'Đóng', en: 'Close' },
  '取消': { vi: 'Hủy', en: 'Cancel' },
  '一、绑定对象与生效': { vi: '1. Đối tượng áp dụng và hiệu lực', en: '1. Target and effective date' },
  '二、薪酬项目明细（只填金额，倍率和费率不在这里配）': {
    vi: '2. Chi tiết khoản lương (chỉ nhập số tiền; hệ số và tỷ lệ không cấu hình ở đây)',
    en: '2. Salary items (amounts only; rates and ratios are not configured here)'
  },
  '三、结果预览': { vi: '3. Xem trước kết quả', en: '3. Result preview' },
  '职类': { vi: 'Nhóm chức danh', en: 'Job class' },
  '员工': { vi: 'Nhân viên', en: 'Employee' },
  '货币': { vi: 'Tiền tệ', en: 'Currency' },
  '备注': { vi: 'Ghi chú', en: 'Remark' },
  '+ 添加项目': { vi: '+ Thêm khoản', en: '+ Add item' },
  '项目': { vi: 'Khoản', en: 'Item' },
  '金额（VND）': { vi: 'Số tiền (VND)', en: 'Amount (VND)' },
  '占比': { vi: 'Tỷ trọng', en: 'Share' },
  '保存草稿': { vi: 'Lưu nháp', en: 'Save draft' },
  '保存并审批': { vi: 'Lưu và duyệt', en: 'Save and approve' },
  '新增薪酬项目': { vi: 'Thêm khoản lương', en: 'New salary item' },
  '名称（中）': { vi: 'Tên (Trung)', en: 'Name (Chinese)' },
  '名称（越）': { vi: 'Tên (Việt)', en: 'Name (Vietnamese)' },
  '基本工资': { vi: 'Lương cơ bản', en: 'Base salary' },
  '津贴': { vi: 'Phụ cấp', en: 'Allowance' },
  '其他收入': { vi: 'Thu nhập khác', en: 'Other income' },
  '绩效': { vi: 'Hiệu suất', en: 'Performance' },
  '加班': { vi: 'Làm thêm giờ', en: 'Overtime' },
  '固定金额': { vi: 'Số tiền cố định', en: 'Fixed amount' },
  '按底薪比例': { vi: 'Theo tỷ lệ lương cơ bản', en: 'Percent of base salary' },
  '手工录入': { vi: 'Nhập tay', en: 'Manual entry' },
  '绩效绝对额': { vi: 'Hiệu suất (số tuyệt đối)', en: 'Performance (absolute)' },
  '绩效系数': { vi: 'Hệ số hiệu suất', en: 'Performance factor' },
  '默认金额': { vi: 'Số tiền mặc định', en: 'Default amount' },
  '排序': { vi: 'Thứ tự', en: 'Order' },
  '属性位（决定这个项目怎么参与计薪）': {
    vi: 'Thuộc tính (quyết định khoản này tham gia tính lương thế nào)',
    en: 'Attributes (how this item participates in payroll)'
  },
  '免税规则：': { vi: 'Quy tắc miễn thuế: ', en: 'Tax exemption: ' },
  '全额计税（none）': { vi: 'Chịu thuế toàn bộ (none)', en: 'Fully taxable (none)' },
  '全额免税（full）': { vi: 'Miễn thuế toàn bộ (full)', en: 'Fully exempt (full)' },
  '按时段免税系数（ot_band_by_factor）': { vi: 'Hệ số miễn thuế theo khung giờ (ot_band_by_factor)', en: 'Exemption by band factor (ot_band_by_factor)' },
  '定额免税（fixed_cap）': { vi: 'Miễn thuế theo định mức (fixed_cap)', en: 'Fixed-cap exemption (fixed_cap)' },
  '启用': { vi: 'Bật', en: 'Enabled' },
  '停用': { vi: 'Tắt', en: 'Disabled' },
  '是': { vi: 'Có', en: 'Yes' },
  '否': { vi: 'Không', en: 'No' },
  '字典为空': { vi: 'Danh mục trống', en: 'Dictionary is empty' },
  '编辑': { vi: 'Sửa', en: 'Edit' },
  '查看': { vi: 'Xem', en: 'View' },
  '删除': { vi: 'Xóa', en: 'Delete' },
  '审批': { vi: 'Duyệt', en: 'Approve' },
  '移除': { vi: 'Bỏ', en: 'Remove' },
  '作废': { vi: 'Hủy bỏ', en: 'Void' },
  '明细': { vi: 'Chi tiết', en: 'Details' },
  '确认': { vi: 'Xác nhận', en: 'Confirm' },
  '豁免': { vi: 'Miễn trừ', en: 'Waive' },
  '低于最低': { vi: 'Dưới mức tối thiểu', en: 'Below minimum' },
  '还没有任何薪资结构。点右上角「新建结构」，先给一个职类建模板。': {
    vi: 'Chưa có cơ cấu lương nào. Bấm 「Tạo cơ cấu」 ở góc trên bên phải, tạo mẫu cho một nhóm chức danh trước.',
    en: 'No salary structure yet. Click 「New structure」 at the top right and create a template for a job class first.'
  },
  '还没有项目，点「添加项目」从字典里选。': {
    vi: 'Chưa có khoản nào. Bấm 「Thêm khoản」 để chọn từ danh mục.',
    en: 'No items yet. Click 「Add item」 to pick from the dictionary.'
  },
  '审批通过后，从生效日起按此结构计薪；同期更早版本会自动补失效日。继续？': {
    vi: 'Sau khi duyệt, tính lương theo cơ cấu này từ ngày hiệu lực; phiên bản cũ hơn cùng kỳ sẽ tự động được bổ sung ngày hết hiệu lực. Tiếp tục?',
    en: 'Once approved, payroll follows this structure from its effective date; earlier versions in the same period get an end date automatically. Continue?'
  },
  '作废后该版本不再参与计薪（历史工资单不受影响）。继续？': {
    vi: 'Sau khi hủy, phiên bản này không tham gia tính lương nữa (phiếu lương lịch sử không bị ảnh hưởng). Tiếp tục?',
    en: 'Once voided, this version no longer participates in payroll (historical payslips are unaffected). Continue?'
  },
  '删除这条草稿？不可恢复。': { vi: 'Xóa bản nháp này? Không thể khôi phục.', en: 'Delete this draft? This cannot be undone.' },
  '草稿已删除': { vi: 'Đã xóa bản nháp', en: 'Draft deleted' },
  '请选择员工': { vi: 'Vui lòng chọn nhân viên', en: 'Please select employees' },
  '请选择生效日期': { vi: 'Vui lòng chọn ngày hiệu lực', en: 'Please select an effective date' },
  '请选择职类': { vi: 'Vui lòng chọn nhóm chức danh', en: 'Please select a job class' },
  '请先勾选员工': { vi: 'Vui lòng tích chọn nhân viên trước', en: 'Please tick employees first' },
  '项目名称必填': { vi: 'Bắt buộc nhập tên khoản', en: 'Item name is required' },
  '项目已更新。已审批的结构需要重新保存才会带上新属性。': {
    vi: 'Đã cập nhật khoản. Cơ cấu đã duyệt cần lưu lại mới mang thuộc tính mới.',
    en: 'Item updated. Approved structures must be saved again to pick up the new attributes.'
  },
  '项目已新增，可在结构里填金额了': {
    vi: 'Đã thêm khoản, có thể nhập số tiền trong cơ cấu',
    en: 'Item added; you can now enter the amount in the structure'
  },
  '编辑薪酬项目：': { vi: 'Sửa khoản lương: ', en: 'Edit salary item: ' },
  '字典里可用的收入项目都已加进来了。要新增项目请去「薪酬项目字典」页。': {
    vi: 'Tất cả khoản thu nhập có trong danh mục đã được thêm. Muốn thêm khoản mới, vào trang 「Danh mục khoản lương」.',
    en: 'Every income item in the dictionary has been added. To create a new one, go to the 「Salary item dictionary」 page.'
  },
  '人数：': { vi: 'Số người: ', en: 'People: ' },
  '人': { vi: 'người', en: 'people' },
  '生效结构：': { vi: 'Cơ cấu hiệu lực: ', en: 'Effective structure: ' },
  '未配置': { vi: 'Chưa cấu hình', en: 'Not configured' },
  '未分配': { vi: 'Chưa phân bổ', en: 'Unassigned' },
  '未填': { vi: 'Chưa nhập', en: 'Not set' },
  '没有职类': { vi: 'Chưa có nhóm chức danh', en: 'No job class' },
  '没有匹配的员工': { vi: 'Không có nhân viên phù hợp', en: 'No matching employees' },
  '所有员工都已挂职类': { vi: 'Tất cả nhân viên đã được gán nhóm', en: 'All employees are assigned to a class' },
  '无（走职类）': { vi: 'Không (theo nhóm chức danh)', en: 'None (use job class)' },
  '有': { vi: 'Có', en: 'Yes' },
  '未分配职类': { vi: 'Chưa gán nhóm chức danh', en: 'No job class assigned' },
  '计入时薪基数': { vi: 'Tính vào cơ sở lương giờ', en: 'Counts toward hourly base' },
  '计入社保基数': { vi: 'Tính vào cơ sở BHXH', en: 'Counts toward insurance base' },
  '按出勤折算': { vi: 'Quy đổi theo chấm công', en: 'Prorated by attendance' },

  /* ================= 薪资核算（payroll-console.html） ================= */
  '薪资核算 - OA协同管理平台': { vi: 'Tính lương - Nền tảng quản trị OA', en: 'Payroll - OA Management Platform' },
  '薪资核算 · 越南工厂': { vi: 'Tính lương · Nhà máy Việt Nam', en: 'Payroll · Vietnam Plant' },
  '月薪制 + 14 段倍率 + 分险种社保 + 免税个税 + 首月递延 · 引擎 v2': {
    vi: 'Lương tháng + hệ số 14 khung giờ + BHXH theo từng loại + thuế TNCN có miễn thuế + hoãn trừ tháng đầu · Engine v2',
    en: 'Monthly salary + 14 time bands + per-scheme insurance + PIT with exemption + first-month deferral · Engine v2'
  },
  '概览': { vi: 'Tổng quan', en: 'Overview' },
  '工资单': { vi: 'Phiếu lương', en: 'Payslips' },
  '试算': { vi: 'Tính thử', en: 'Simulate' },
  '时段倍率': { vi: 'Hệ số khung giờ', en: 'Time-band rates' },
  '社保与参数': { vi: 'BHXH & tham số', en: 'Insurance & parameters' },
  '递延台账': { vi: 'Sổ hoãn trừ', en: 'Deferral ledger' },
  '本月批次': { vi: 'Lô tính tháng này', en: 'This month run' },
  '「生成工资单」写入草稿，可反复重算；「确认」后工资单锁定、递延台账才真正记账。 确认过的月份要重算，必须先把该批次作废。': {
    vi: '「Tạo phiếu lương」 ghi vào bản nháp, có thể tính lại nhiều lần; sau khi 「Xác nhận」 phiếu lương bị khóa và sổ hoãn trừ mới thực sự ghi sổ. Muốn tính lại tháng đã xác nhận thì phải hủy lô đó trước.',
    en: '「Generate payslips」 writes to a draft and can be recalculated; after 「Confirm」 the payslips are locked and the deferral ledger is actually posted. To recalculate a confirmed month you must void that run first.'
  },
  '试算全厂（不写库）': { vi: 'Tính thử toàn nhà máy (không ghi dữ liệu)', en: 'Simulate whole plant (no writes)' },
  '生成工资单': { vi: 'Tạo phiếu lương', en: 'Generate payslips' },
  '期间': { vi: 'Kỳ', en: 'Period' },
  '批次': { vi: 'Lô', en: 'Run' },
  '人数': { vi: 'Số người', en: 'Headcount' },
  '应发': { vi: 'Lương gộp', en: 'Gross' },
  '社保': { vi: 'BHXH', en: 'Insurance' },
  '个税': { vi: 'Thuế TNCN', en: 'PIT' },
  '递延': { vi: 'Hoãn trừ', en: 'Deferral' },
  '实发': { vi: 'Lương thực nhận', en: 'Net pay' },
  '社保费率': { vi: 'Tỷ lệ BHXH', en: 'Insurance rates' },
  '社保费率（个人合计': { vi: 'Tỷ lệ BHXH (tổng phần cá nhân', en: 'Insurance rates (employee total' },
  '社保基数取「基本工资 + 岗位津贴」（不含加班费）；BHXH/BHYT 与 BHTN 封顶口径不同，故分险种维护。': {
    vi: 'Cơ sở đóng BHXH lấy 「lương cơ bản + phụ cấp chức vụ」 (không gồm tiền làm thêm); BHXH/BHYT và BHTN có mức trần khác nhau nên quản lý theo từng loại.',
    en: 'The insurance base is 「base salary + job allowance」 (excluding overtime); BHXH/BHYT and BHTN have different caps, so they are maintained per scheme.'
  },
  '险种': { vi: 'Loại bảo hiểm', en: 'Scheme' },
  '个人': { vi: 'Cá nhân', en: 'Employee' },
  '公司': { vi: 'Công ty', en: 'Employer' },
  '封顶基数': { vi: 'Mức trần', en: 'Cap base' },
  '说明': { vi: 'Diễn giải', en: 'Description' },
  '个税税率表与减除额': { vi: 'Biểu thuế TNCN và mức giảm trừ', en: 'PIT brackets and deductions' },
  '应税所得 = 应发 − 免税加班收入 − 个人社保 − 工会费 − 本人减除 − 抚养人×每名减除。': {
    vi: 'Thu nhập chịu thuế = Lương gộp − Thu nhập làm thêm miễn thuế − BHXH phần cá nhân − Phí công đoàn − Giảm trừ bản thân − Số người phụ thuộc × giảm trừ mỗi người.',
    en: 'Taxable income = Gross − tax-exempt overtime − employee insurance − union fee − personal deduction − dependants × per-dependant deduction.'
  },
  '月度工资单': { vi: 'Phiếu lương tháng', en: 'Monthly payslips' },
  '全部': { vi: 'Tất cả', en: 'All' },
  '已确认': { vi: 'Đã xác nhận', en: 'Confirmed' },
  '月薪基数': { vi: 'Lương tháng cơ sở', en: 'Monthly base' },
  '工会': { vi: 'Công đoàn', en: 'Union' },
  '工资单试算（不写库）': { vi: 'Tính thử phiếu lương (không ghi dữ liệu)', en: 'Payslip simulation (no writes)' },
  '按「班次 + 上下班时刻 + 出勤天数」造出一份虚拟打卡，走完整条链路（时段切片 → 应发 → 社保 → 个税 → 递延 → 实发）。 用来验证口径、给员工解释工资构成，不会产生任何工资记录。': {
    vi: 'Tạo một bộ chấm công giả theo 「ca + giờ vào/ra + số ngày công」, chạy toàn bộ chuỗi (cắt khung giờ → lương gộp → BHXH → thuế TNCN → hoãn trừ → thực nhận). Dùng để kiểm tra cách tính và giải thích cơ cấu lương cho nhân viên, không sinh bản ghi lương nào.',
    en: 'Builds a virtual punch set from 「shift + clock-in/out + attendance days」 and runs the whole chain (band slicing → gross → insurance → PIT → deferral → net). Used to verify the rules and explain pay composition to employees; it creates no payroll records.'
  },
  '月薪基数 G（基本工资+岗位津贴）': { vi: 'Lương tháng cơ sở G (lương cơ bản + phụ cấp chức vụ)', en: 'Monthly base G (base salary + job allowance)' },
  '班次': { vi: 'Ca', en: 'Shift' },
  '白班 08:00-20:00': { vi: 'Ca ngày 08:00-20:00', en: 'Day shift 08:00-20:00' },
  '夜班 20:00-08:00': { vi: 'Ca đêm 20:00-08:00', en: 'Night shift 20:00-08:00' },
  '上班时刻': { vi: 'Giờ vào', en: 'Clock-in' },
  '下班时刻': { vi: 'Giờ ra', en: 'Clock-out' },
  '出勤天数（0=全月工作日）': { vi: 'Số ngày công (0 = toàn bộ ngày làm việc trong tháng)', en: 'Attendance days (0 = all workdays in month)' },
  '迟到分钟（每天）': { vi: 'Số phút đi muộn (mỗi ngày)', en: 'Late minutes (per day)' },
  '早退分钟（每天）': { vi: 'Số phút về sớm (mỗi ngày)', en: 'Early-leave minutes (per day)' },
  '免税口径': { vi: 'Cách tính miễn thuế', en: 'Exemption basis' },
  '按参数（默认）': { vi: 'Theo tham số (mặc định)', en: 'By parameter (default)' },
  'A 口径（只免加班溢价）': { vi: 'Cách A (chỉ miễn phần phụ trội làm thêm)', en: 'Option A (exempt the overtime premium only)' },
  'B 口径（加班费整段免税）': { vi: 'Cách B (miễn thuế toàn bộ tiền làm thêm)', en: 'Option B (whole overtime pay exempt)' },
  '首月模拟': { vi: 'Mô phỏng tháng đầu', en: 'First-month simulation' },
  '按花名册入职日期': { vi: 'Theo ngày vào làm trong danh sách', en: 'By hire date in the roster' },
  '模拟入职首月（三项递延）': { vi: 'Mô phỏng tháng đầu (hoãn 3 khoản)', en: 'Simulate first month (three deferrals)' },
  '模拟非首月': { vi: 'Mô phỏng tháng không phải đầu tiên', en: 'Simulate a non-first month' },
  '重置': { vi: 'Đặt lại', en: 'Reset' },
  '计薪时段与倍率': { vi: 'Khung giờ tính lương và hệ số', en: 'Pay bands and rates' },
  '倍率必须按「班次 × 日型」维护：同一个 20:00-22:00，对夜班是正班（1.0），对白班延时是加班（1.5）。 表内倍率不得低于法定下限；采用倍率取两者较大值。': {
    vi: 'Hệ số phải quản lý theo 「ca × loại ngày」: cùng khung 20:00-22:00, với ca đêm là ca chính (1,0), với ca ngày tăng ca là làm thêm (1,5). Hệ số trong bảng không được thấp hơn mức sàn luật định; hệ số áp dụng lấy giá trị lớn hơn trong hai.',
    en: 'Rates must be maintained per 「shift × day type」: the same 20:00-22:00 is regular time for the night shift (1.0) but overtime for a day-shift extension (1.5). Table rates may not fall below the statutory floor; the applied rate is the greater of the two.'
  },
  '段': { vi: 'Khung', en: 'Band' },
  '日型': { vi: 'Loại ngày', en: 'Day type' },
  '时间': { vi: 'Thời gian', en: 'Time' },
  '标准工时': { vi: 'Giờ tiêu chuẩn', en: 'Standard hours' },
  '表内倍率': { vi: 'Hệ số trong bảng', en: 'Table rate' },
  '法定下限': { vi: 'Mức sàn luật định', en: 'Statutory floor' },
  '采用': { vi: 'Áp dụng', en: 'Applied' },
  '免税A': { vi: 'Miễn thuế A', en: 'Exempt A' },
  '免税B': { vi: 'Miễn thuế B', en: 'Exempt B' },
  '不计薪用餐窗口': { vi: 'Khung giờ ăn không tính lương', en: 'Unpaid meal window' },
  '修改会按「今日」新开一版，历史月份不受影响。封顶基数留空 = 不封顶。': {
    vi: 'Chỉnh sửa sẽ mở phiên bản mới theo 「hôm nay」, các tháng lịch sử không bị ảnh hưởng. Để trống mức trần = không giới hạn trần.',
    en: 'Edits open a new version dated 「today」; historical months are unaffected. Leave the cap blank = no cap.'
  },
  '个人 %': { vi: '% cá nhân', en: 'Employee %' },
  '公司 %': { vi: '% công ty', en: 'Employer %' },
  '基数口径': { vi: 'Cách xác định cơ sở', en: 'Base definition' },
  '扣款口径开关': { vi: 'Công tắc cách tính khấu trừ', en: 'Deduction switches' },
  '免税口径 A/B 决定加班费免多少税——B 口径下加班费几乎全免（个税接近 0），A 口径只免高于正常工资的部分。 最终口径以财务书面意见为准，这里改的是参数、不是代码。': {
    vi: 'Cách miễn thuế A/B quyết định tiền làm thêm được miễn bao nhiêu thuế — cách B gần như miễn toàn bộ (thuế TNCN gần 0), cách A chỉ miễn phần cao hơn lương bình thường. Cách cuối cùng theo ý kiến bằng văn bản của tài chính; ở đây đổi tham số, không đổi mã.',
    en: 'Exemption option A/B decides how much overtime pay is tax-free — under B almost all of it (PIT near zero), under A only the part above normal pay. The final basis follows written finance guidance; what changes here is a parameter, not code.'
  },
  'B · 加班费整段免税': { vi: 'B · Miễn thuế toàn bộ tiền làm thêm', en: 'B · Whole overtime pay exempt' },
  'A · 只免加班溢价': { vi: 'A · Chỉ miễn phần phụ trội làm thêm', en: 'A · Exempt the premium only' },
  '首月扣款模式': { vi: 'Chế độ khấu trừ tháng đầu', en: 'First-month deduction mode' },
  'defer · 递延到次月（公司垫付）': { vi: 'defer · Hoãn sang tháng sau (công ty ứng trước)', en: 'defer · Deferred to next month (company advances)' },
  'none · 首月照扣': { vi: 'none · Tháng đầu vẫn khấu trừ', en: 'none · Deduct in the first month' },
  '个税先扣免税收入': { vi: 'Thuế TNCN trừ thu nhập miễn thuế trước', en: 'Deduct exempt income before PIT' },
  '是（符合越南口径）': { vi: 'Có (đúng cách tính của Việt Nam)', en: 'Yes (matches Vietnamese rules)' },
  '否（退回全额计税）': { vi: 'Không (quay lại tính thuế toàn bộ)', en: 'No (fall back to full taxation)' },
  '社保最低基数（0=不启用）': { vi: 'Cơ sở BHXH tối thiểu (0 = không áp dụng)', en: 'Minimum insurance base (0 = disabled)' },
  '保存开关': { vi: 'Lưu công tắc', en: 'Save switches' },
  '入职日期（决定首月递延）': { vi: 'Ngày vào làm (quyết định hoãn trừ tháng đầu)', en: 'Hire date (drives first-month deferral)' },
  '没登记入职日期的员工不会触发首月免扣——否则等于白送一个月社保。请在花名册补全。': {
    vi: 'Nhân viên chưa có ngày vào làm sẽ không kích hoạt miễn trừ tháng đầu — nếu không thì coi như tặng không một tháng BHXH. Vui lòng bổ sung trong danh sách nhân viên.',
    en: 'Employees without a hire date will not trigger the first-month exemption — otherwise it amounts to gifting a month of insurance. Please complete the roster.'
  },
  '个人结构': { vi: 'Cơ cấu riêng', en: 'Personal structure' },
  '递延扣缴台账': { vi: 'Sổ hoãn trừ', en: 'Deferral ledger' },
  '首月不扣的社保 / 工会费 / 个税在这里挂账，次月连本月一起扣回。离职月应结清；确需不收回的，用「豁免」并写明原因（会留痕）。': {
    vi: 'BHXH / phí công đoàn / thuế TNCN không khấu trừ ở tháng đầu được ghi nợ ở đây, tháng sau thu lại cùng tháng đó. Tháng nghỉ việc phải tất toán; nếu thực sự không thu lại thì dùng 「Miễn trừ」 và ghi rõ lý do (có lưu vết).',
    en: 'Insurance, union fee and PIT not deducted in the first month are accrued here and recovered together with the next month. The leaving month should be settled; if it truly should not be recovered, use 「Waive」 and state the reason (it is logged).'
  },
  '待扣回': { vi: 'Chờ thu lại', en: 'To recover' },
  '已结清': { vi: 'Đã tất toán', en: 'Settled' },
  '已豁免': { vi: 'Đã miễn trừ', en: 'Waived' },
  '所属月份': { vi: 'Tháng phát sinh', en: 'Period' },
  '金额': { vi: 'Số tiền', en: 'Amount' },
  '结清月份': { vi: 'Tháng tất toán', en: 'Settled in' },
  '工资单明细': { vi: 'Chi tiết phiếu lương', en: 'Payslip detail' },
  '个税登记': { vi: 'Đăng ký thuế TNCN', en: 'PIT registration' },
  '在职员工': { vi: 'Nhân viên đang làm', en: 'Active employees' },
  '人缺入职日期': { vi: 'người thiếu ngày vào làm', en: 'people missing a hire date' },
  '入职日期已齐': { vi: 'Đã đủ ngày vào làm', en: 'Hire dates complete' },
  '未生成': { vi: 'Chưa tạo', en: 'Not generated' },
  '点下方生成': { vi: 'Bấm tạo ở bên dưới', en: 'Click generate below' },
  '应发合计': { vi: 'Tổng lương gộp', en: 'Total gross' },
  '含加班与津贴': { vi: 'Gồm làm thêm và phụ cấp', en: 'Including overtime and allowances' },
  '实发合计': { vi: 'Tổng thực nhận', en: 'Total net' },
  '扣完社保个税递延': { vi: 'Sau khi trừ BHXH, thuế, hoãn trừ', en: 'After insurance, PIT and deferral' },
  '个税合计': { vi: 'Tổng thuế TNCN', en: 'Total PIT' },
  '本月实扣': { vi: 'Thực trừ tháng này', en: 'Actually deducted this month' },
  '公司成本': { vi: 'Chi phí công ty', en: 'Employer cost' },
  '含公司社保': { vi: 'Gồm BHXH phần công ty', en: 'Including employer insurance' },
  '递延待收回': { vi: 'Hoãn trừ chờ thu hồi', en: 'Deferral to recover' },
  '笔': { vi: 'mục', en: 'entries' },
  '还没有批次': { vi: 'Chưa có lô nào', en: 'No runs yet' },
  '确认后工资单锁定、递延台账开始记账。确认？': {
    vi: 'Sau khi xác nhận, phiếu lương bị khóa và sổ hoãn trừ bắt đầu ghi sổ. Xác nhận?',
    en: 'After confirming, payslips are locked and the deferral ledger starts posting. Confirm?'
  },
  '批次已确认': { vi: 'Lô đã được xác nhận', en: 'Run confirmed' },
  '作废原因（会记进批次快照）': { vi: 'Lý do hủy (ghi vào ảnh chụp lô)', en: 'Void reason (recorded in the run snapshot)' },
  '重算': { vi: 'Tính lại', en: 'Recalculate' },
  '生成': { vi: 'Tạo', en: 'Generate' },
  '的工资单？会写入 salary_record（草稿状态）。': {
    vi: ' phiếu lương? Sẽ ghi vào salary_record (trạng thái nháp).',
    en: ' payslips? This writes to salary_record (draft status).'
  },
  '正在试算全厂…': { vi: 'Đang tính thử toàn nhà máy…', en: 'Simulating the whole plant…' },
  '正在生成…': { vi: 'Đang tạo…', en: 'Generating…' },
  '跳过': { vi: 'Bỏ qua', en: 'Skipped' },
  '跳过原因：': { vi: 'Lý do bỏ qua: ', en: 'Skip reason: ' },
  '试算完成：': { vi: 'Tính thử xong: ', en: 'Simulation done: ' },
  '已生成：': { vi: 'Đã tạo: ', en: 'Generated: ' },
  '共': { vi: 'Tổng', en: 'Total' },
  '条': { vi: 'bản ghi', en: 'records' },
  '该月没有工资单。先到「概览」生成，或确认该月已有打卡数据。': {
    vi: 'Tháng này chưa có phiếu lương. Vào 「Tổng quan」 để tạo trước, hoặc kiểm tra tháng đó đã có dữ liệu chấm công chưa.',
    en: 'No payslips for this month. Generate them in 「Overview」 first, or check that the month has punch data.'
  },
  '应发构成': { vi: 'Cơ cấu lương gộp', en: 'Gross composition' },
  '月薪基数 G': { vi: 'Lương tháng cơ sở G', en: 'Monthly base G' },
  '时薪 H = G÷208': { vi: 'Lương giờ H = G÷208', en: 'Hourly rate H = G÷208' },
  '应出勤 B / 实际折算 W': { vi: 'Ngày công chuẩn B / quy đổi thực tế W', en: 'Standard days B / converted actual W' },
  '差额工时 × 时薪': { vi: 'Giờ chênh lệch × lương giờ', en: 'Hour difference × hourly rate' },
  '不计时津贴': { vi: 'Phụ cấp không tính giờ', en: 'Non-hourly allowance' },
  '应发工资': { vi: 'Lương gộp', en: 'Gross pay' },
  '扣款构成': { vi: 'Cơ cấu khấu trừ', en: 'Deduction composition' },
  '个人社保（': { vi: 'BHXH phần cá nhân (', en: 'Employee insurance (' },
  '工会费': { vi: 'Phí công đoàn', en: 'Union fee' },
  '个人所得税': { vi: 'Thuế thu nhập cá nhân', en: 'Personal income tax' },
  '结清上期递延': { vi: 'Tất toán hoãn trừ kỳ trước', en: 'Settle prior deferral' },
  '个税计算过程': { vi: 'Quá trình tính thuế TNCN', en: 'PIT calculation' },
  '− 免税加班收入': { vi: '− Thu nhập làm thêm miễn thuế', en: '− Tax-exempt overtime' },
  '− 个人社保': { vi: '− BHXH phần cá nhân', en: '− Employee insurance' },
  '− 工会费': { vi: '− Phí công đoàn', en: '− Union fee' },
  '− 本人减除': { vi: '− Giảm trừ bản thân', en: '− Personal deduction' },
  '− 抚养人减除（': { vi: '− Giảm trừ người phụ thuộc (', en: '− Dependant deduction (' },
  '应税所得': { vi: 'Thu nhập chịu thuế', en: 'Taxable income' },
  '应纳税额': { vi: 'Thuế phải nộp', en: 'Tax payable' },
  '14 段工时明细': { vi: 'Chi tiết giờ 14 khung', en: '14-band hours detail' },
  '计薪工时': { vi: 'Giờ tính lương', en: 'Paid hours' },
  '倍率': { vi: 'Hệ số', en: 'Rate' },
  '折算工时': { vi: 'Giờ quy đổi', en: 'Converted hours' },
  '免税工时': { vi: 'Giờ miễn thuế', en: 'Exempt hours' },
  '提示': { vi: 'Lưu ý', en: 'Notice' },
  '日历缺失': { vi: 'Thiếu lịch', en: 'Missing calendar' },
  '试算中…': { vi: 'Đang tính thử…', en: 'Simulating…' },
  '个人社保': { vi: 'BHXH phần cá nhân', en: 'Employee insurance' },
  '结清递延': { vi: 'Tất toán hoãn trừ', en: 'Settle deferral' },
  '当前按「入职首月」模拟：本月社保/工会费/个税一分不扣，合计': {
    vi: 'Đang mô phỏng theo 「tháng đầu vào làm」: tháng này không khấu trừ BHXH / phí công đoàn / thuế TNCN, tổng cộng',
    en: 'Simulating the 「first month」: no insurance, union fee or PIT is deducted this month, totalling'
  },
  '越盾记入递延台账，次月扣回。实发因此比正常月多。': {
    vi: ' VND được ghi vào sổ hoãn trừ và thu lại vào tháng sau. Vì vậy thực nhận cao hơn tháng bình thường.',
    en: ' VND is accrued in the deferral ledger and recovered next month, so net pay is higher than a normal month.'
  },
  '应发 → 扣款 → 实发': { vi: 'Lương gộp → Khấu trừ → Thực nhận', en: 'Gross → Deductions → Net' },
  '差额工时': { vi: 'Giờ chênh lệch', en: 'Hour difference' },
  '差额工资': { vi: 'Lương chênh lệch', en: 'Pay difference' },
  '使用内置默认值（库中无时段集）': {
    vi: 'Dùng giá trị mặc định tích hợp (cơ sở dữ liệu chưa có bộ khung giờ)',
    en: 'Using built-in defaults (no time-band set in the database)'
  },
  '工作日': { vi: 'Ngày làm việc', en: 'Workday' },
  '周日': { vi: 'Chủ nhật', en: 'Sunday' },
  '法定假日': { vi: 'Ngày lễ pháp định', en: 'Public holiday' },
  '白班': { vi: 'Ca ngày', en: 'Day shift' },
  '夜班': { vi: 'Ca đêm', en: 'Night shift' },
  '通用': { vi: 'Chung', en: 'General' },
  '无': { vi: 'Không', en: 'None' },
  '倍率已保存。已生成的工资单需要重算才生效。': {
    vi: 'Đã lưu hệ số. Phiếu lương đã tạo cần tính lại mới có hiệu lực.',
    en: 'Rates saved. Existing payslips must be recalculated to take effect.'
  },
  '基本工资+岗位津贴': { vi: 'Lương cơ bản + phụ cấp chức vụ', en: 'Base salary + job allowance' },
  '缺入职日期': { vi: 'Thiếu ngày vào làm', en: 'Missing hire date' },
  '已保存': { vi: 'Đã lưu', en: 'Saved' },
  '已更新': { vi: 'Đã cập nhật', en: 'Updated' },
  '参数无变化': { vi: 'Tham số không thay đổi', en: 'No parameter changes' },
  '没有递延记录': { vi: 'Chưa có bản ghi hoãn trừ', en: 'No deferral records' },
  '豁免原因（会写进备注，必须填）': {
    vi: 'Lý do miễn trừ (ghi vào ghi chú, bắt buộc)',
    en: 'Waiver reason (written to remarks, required)'
  },
  '离职协商不追': { vi: 'Nghỉ việc, thỏa thuận không thu hồi', en: 'Leaver — agreed not to recover' },
  '个税税率表的速算扣除数有问题：': { vi: 'Bảng thuế TNCN có vấn đề về số giảm trừ nhanh: ', en: 'PIT bracket has a problem with the quick-deduction amount: ' },
  '还没有配置社保费率，社保会按 0 计。': {
    vi: 'Chưa cấu hình tỷ lệ BHXH, BHXH sẽ tính bằng 0.',
    en: 'No insurance rates configured; insurance will be calculated as 0.'
  },
  '加班月上限': { vi: 'Giới hạn giờ làm thêm theo tháng', en: 'Monthly overtime cap' },
  '小时（已向劳动局备案，超限只提示不拦发薪）。': {
    vi: ' giờ (đã đăng ký với Sở Lao động; vượt mức chỉ cảnh báo, không chặn trả lương).',
    en: ' hours (filed with the labour authority; exceeding it only warns, payroll is not blocked).'
  },
  '不封顶': { vi: 'Không giới hạn trần', en: 'No cap' },
  '本人减除': { vi: 'Giảm trừ bản thân', en: 'Personal deduction' },
  '/ 每名抚养人': { vi: '/ mỗi người phụ thuộc', en: '/ per dependant' },
  '· 税率表生效日': { vi: '· Ngày hiệu lực biểu thuế', en: '· Bracket effective date' },
  '个税已关闭': { vi: 'Thuế TNCN đã tắt', en: 'PIT disabled' },
  '级': { vi: 'Bậc', en: 'Bracket' },
  '下限': { vi: 'Từ', en: 'From' },
  '税率': { vi: 'Thuế suất', en: 'Rate' },
  '速算扣除': { vi: 'Giảm trừ nhanh', en: 'Quick deduction' },
  '薪资核算 v2': { vi: 'Tính lương v2', en: 'Payroll v2' },
  '扣款': { vi: 'Khấu trừ', en: 'Deduction' },
  '缺勤': { vi: 'Vắng mặt', en: 'Absence' },
  '迟到早退': { vi: 'Đi muộn / về sớm', en: 'Lateness / early leave' },
  '个人保险': { vi: 'Bảo hiểm phần cá nhân', en: 'Employee insurance' },
  '公司保险': { vi: 'Bảo hiểm phần công ty', en: 'Employer insurance' },
  '按时段自动': { vi: 'Tự động theo khung giờ', en: 'Automatic by time band' },
  '缺勤自动': { vi: 'Vắng mặt tự động', en: 'Absence (automatic)' },
  '迟到早退自动': { vi: 'Đi muộn/về sớm tự động', en: 'Lateness/early leave (automatic)' },
  '序号不对': { vi: 'Số thứ tự không đúng', en: 'Invalid number' },
  '选择要添加的项目（输入序号）：': { vi: 'Chọn khoản cần thêm (nhập số thứ tự): ', en: 'Pick the item to add (enter its number): ' },
  '已保存并审批通过': { vi: 'Đã lưu và duyệt xong', en: 'Saved and approved' },
  '草稿已保存，但审批被拦：': { vi: 'Đã lưu bản nháp, nhưng duyệt bị chặn: ', en: 'Draft saved, but approval was blocked: ' },
  '还有': { vi: 'Còn', en: 'Still' },
  '≥ 地区最低工资': { vi: '≥ Lương tối thiểu vùng', en: '≥ Regional minimum wage' },
  '，合规。': { vi: ', hợp lệ.', en: ', compliant.' },
  '。审批后才会参与计薪。': { vi: '. Chỉ sau khi duyệt mới tham gia tính lương.', en: '. It only participates in payroll after approval.' },
  '折算': { vi: 'Quy đổi', en: 'Converted' },
  '免税': { vi: 'Miễn thuế', en: 'Exempt' },
  '项：': { vi: 'mục: ', en: 'items: ' },
  '已生效（': { vi: 'Đã có hiệu lực (', en: 'Effective (' },
  '· 生效': { vi: '· Hiệu lực', en: '· Effective' },
  '· 出勤': { vi: '· Chấm công', en: '· Attendance' },
  '试算完成：实发': { vi: 'Tính thử xong: thực nhận', en: 'Simulation done: net pay' },
  '/ 实发合计': { vi: '/ Tổng thực nhận', en: '/ Total net' },
  '/ 公司': { vi: '/ Công ty', en: '/ Employer' },
  '正班工资为 0：可以存草稿，但<b>审批会被拦截</b>——0 元结构放出去会算出 0 元工资。': {
    vi: 'Lương ca chính bằng 0: vẫn lưu nháp được, nhưng <b>duyệt sẽ bị chặn</b> — đưa ra cơ cấu 0 đồng sẽ tính ra lương 0.',
    en: 'Regular pay is 0: the draft can be saved, but <b>approval will be blocked</b> — a zero-value structure would produce zero pay.'
  },
  '已存为草稿 v{1}。审批后才会参与计薪。': {
    vi: 'Đã lưu thành bản nháp v{1}. Chỉ sau khi duyệt mới tham gia tính lương.',
    en: 'Saved as draft v{1}. It participates in payroll only after approval.'
  },
  '草稿已保存，但审批被拦：{1}': {
    vi: 'Đã lưu bản nháp, nhưng duyệt bị chặn: {1}',
    en: 'Draft saved, but approval was blocked: {1}'
  },
  '还有 {1} 人未挂职类 —— 这些人如果也没有个人专属结构，计薪时会被跳过': {
    vi: 'Còn {1} người chưa gán nhóm chức danh — nếu họ cũng không có cơ cấu riêng thì sẽ bị bỏ qua khi tính lương',
    en: '{1} people still have no job class — if they also lack a personal structure they will be skipped in payroll'
  },
  '已把 {1} 人挂到「{2}」': { vi: 'Đã gán {1} người vào 「{2}」', en: 'Assigned {1} people to 「{2}」' },
  '正班工资 {1} 低于地区最低工资 {2}，差 {3}。这是劳动法硬约束（第 90 条 + 第 38/2022/NĐ-CP），<b>审批会被拦</b>。': {
    vi: 'Lương ca chính {1} thấp hơn lương tối thiểu vùng {2}, thiếu {3}. Đây là ràng buộc cứng của luật lao động (Điều 90 + Nghị định 38/2022/NĐ-CP), <b>duyệt sẽ bị chặn</b>.',
    en: 'Regular pay {1} is below the regional minimum wage {2}, short by {3}. This is a hard legal constraint (Article 90 + Decree 38/2022/NĐ-CP); <b>approval will be blocked</b>.'
  },
  '✓ 正班工资 {1} ≥ 地区最低工资 {2}，合规。': {
    vi: '✓ Lương ca chính {1} ≥ lương tối thiểu vùng {2}, hợp lệ.',
    en: '✓ Regular pay {1} ≥ regional minimum wage {2}, compliant.'
  },
  '有 {1} 名员工没登记入职日期，首月递延不会触发（等于白送一个月社保）。请到「社保与参数」页补全。': {
    vi: 'Có {1} nhân viên chưa có ngày vào làm, hoãn trừ tháng đầu sẽ không kích hoạt (coi như tặng không một tháng BHXH). Vui lòng bổ sung ở trang 「BHXH & tham số」.',
    en: '{1} employees have no hire date, so the first-month deferral will not trigger (equivalent to gifting a month of insurance). Please complete them on the 「Insurance & parameters」 page.'
  },

  /* ============ 职类改为「岗位字典」口径（2026-10-27） ============ */
  "岗位与职类": { vi: "Vị trí & nhóm lương", en: "Positions & pay classes" },
  "岗位与计薪职类": { vi: "Vị trí và nhóm lương", en: "Positions and pay classes" },
  "员工岗位与计薪来源": { vi: "Vị trí nhân viên và nguồn tính lương", en: "Employee position and pay source" },
  "岗位模板": { vi: "Mẫu theo vị trí", en: "Position template" },
  "只看未配置": { vi: "Chỉ xem chưa cấu hình", en: "Unconfigured only" },
  "岗位": { vi: "Vị trí", en: "Position" },
  "岗位字典里还没有岗位": { vi: "Từ điển vị trí chưa có vị trí nào", en: "No positions in the dictionary yet" },
  "都配好了，没有缺结构的员工": { vi: "Đã cấu hình đủ, không còn ai thiếu cơ cấu", en: "All set — no employees missing a structure" },
  "设岗位": { vi: "Đặt vị trí", en: "Set position" },
  "计薪来源": { vi: "Nguồn tính lương", en: "Pay source" },
  "批量设置岗位": { vi: "Đặt vị trí hàng loạt", en: "Set positions in bulk" },
  "设为所选岗位": { vi: "Đặt thành vị trí đã chọn", en: "Set to selected position" },
  "未设岗位": { vi: "Chưa có vị trí", en: "No position" },
  "未配置": { vi: "Chưa cấu hình", en: "Not configured" },
  "草稿待审批": { vi: "Bản nháp chờ duyệt", en: "Draft pending approval" },
  "{1} 个岗位 · {2} 名在职 · 已配模板 {3} 个 · 未设岗位 {4} 人": { vi: "{1} vị trí · {2} nhân viên đang làm · {3} vị trí đã có mẫu · {4} người chưa có vị trí", en: "{1} positions · {2} active employees · {3} with a template · {4} without a position" },
  "已把 {1} 人的岗位设为「{2}」": { vi: "Đã đặt vị trí của {1} người thành 「{2}」", en: "Set the position of {1} people to 「{2}」" },
  "确认把这 {1} 人的岗位设为「{2}」？会同时改掉他们的 HR 岗位（组织与岗位管理、审批流按岗位找人都跟着变），不只是工资口径。": { vi: "Xác nhận đặt vị trí của {1} người thành 「{2}」? Thao tác này đồng thời đổi vị trí HR của họ (quản lý tổ chức và luồng phê duyệt tìm người theo vị trí đều thay đổi), không chỉ là khẩu phần lương.", en: "Set the position of {1} people to 「{2}」? This also changes their HR position (org management and approval routing by position change accordingly), not just the pay basis." },
  "岗位「{1}」已停用，先到岗位字典启用": { vi: "Vị trí 「{1}」 đã ngừng dùng, hãy bật lại trong từ điển vị trí", en: "Position 「{1}」 is disabled — enable it in the position dictionary first" },
  "个人专属 v{1}": { vi: "Riêng nhân viên v{1}", en: "Personal v{1}" },
  "岗位模板 v{1}": { vi: "Mẫu theo vị trí v{1}", en: "Position template v{1}" },

  /* ---------- 岗位页签的三段整块说明（键＝页面文字，勿手改） ---------- */
  "职类就是岗位：下面这份清单直接取「组织与岗位管理 → 岗位字典」，与字典一一对应，不另立一套分类。 每个岗位可以有一份已审批的薪资结构模板，员工按自己的岗位自动套用，不需要手工挂职类。 优先级：个人专属（已审批）＞ 岗位模板（已审批）。点岗位卡片可直接给该岗位建模板。": { vi: "Nhóm lương chính là vị trí: danh sách dưới đây lấy trực tiếp từ 「Quản lý tổ chức & vị trí → Từ điển vị trí」, tương ứng 1-1 với từ điển, không tạo thêm bộ phân loại khác. Mỗi vị trí có thể có một mẫu cơ cấu lương đã duyệt, nhân viên tự động áp dụng theo vị trí của mình, không cần gán tay. Ưu tiên: riêng nhân viên (đã duyệt) > mẫu theo vị trí (đã duyệt). Bấm vào thẻ vị trí để tạo mẫu cho vị trí đó.", en: "Pay class is the position itself: the list below comes straight from 「Organization & Positions → Position dictionary」 and matches it one-to-one, with no separate classification. Each position may have one approved salary structure template; employees inherit it automatically by their position, with no manual assignment. Priority: personal (approved) > position template (approved). Click a position card to create a template for it." },
  "岗位为空的人不会套用任何模板，计薪时会被跳过。补岗位请到「组织与岗位管理」，或在下方批量设置。 入离职日期为空的人不会触发首月免扣递延，建议一并补齐。": { vi: "Người chưa có vị trí sẽ không được áp dụng mẫu nào và bị bỏ qua khi tính lương. Hãy bổ sung vị trí ở 「Quản lý tổ chức & vị trí」 hoặc đặt hàng loạt bên dưới. Người chưa có ngày vào làm sẽ không kích hoạt hoãn trừ tháng đầu, nên bổ sung.", en: "Employees without a position get no template and are skipped in payroll. Add positions in 「Organization & Positions」 or set them in bulk below. Employees without a hire date will not trigger first-month deferral — please complete those too." },
  "勾选上方表格里的人 → 设为该岗位。注意：这会同时改掉员工的 HR 岗位（组织与岗位管理、审批流按岗位找人都跟着变）， 不只是工资口径；已在目标岗位的人自动跳过。": { vi: "Tick người ở bảng trên → đặt vào vị trí này. Lưu ý: thao tác này cũng đổi vị trí HR của nhân viên (quản lý tổ chức và luồng phê duyệt tìm người theo vị trí đều thay đổi), không chỉ là khẩu phần lương; người đã ở vị trí đích sẽ tự động bỏ qua.", en: "Tick people in the table above → set them to this position. Note: this also changes their HR position (org management and approval routing by position change accordingly), not just the pay basis; those already in the target position are skipped." },
  /* ==========================================================
     计薪方案 / 参保与工会 / 休假字典 / 年假台账
     （SRS 对标那一轮新增的三个页签，2026-10-28 补齐译文）
     ========================================================== */
  "计薪方案": { vi: "Phương án tính lương", en: "Pay scheme" },
  "参保与工会": { vi: "Bảo hiểm và công đoàn", en: "Insurance & Union" },
  "年假台账": { vi: "Sổ phép năm", en: "Annual leave ledger" },
  "计薪方案 · 多用途计薪基数": { vi: "Phương án tính lương · Cơ sở lương đa mục đích", en: "Pay scheme · Multi-purpose pay base" },
  "保存方案": { vi: "Lưu phương án", en: "Save scheme" },
  "工龄津贴分档（thâm niên）": { vi: "Bậc phụ cấp thâm niên (thâm niên)", en: "Seniority allowance tiers (thâm niên)" },
  "加一档": { vi: "Thêm một bậc", en: "Add tier" },
  "保存分档": { vi: "Lưu bậc", en: "Save tiers" },
  "按「入职月数」落在 [下限, 上限) 区间取金额；上限留空表示封顶档。金额留 0 表示该档不发。": { vi: "Theo 「số tháng vào làm」 nằm trong khoảng [từ, đến) để lấy số tiền; để trống cận trên là bậc cao nhất. Số tiền 0 nghĩa là bậc đó không chi.", en: "The amount is picked by the 「months since hire」 falling in [from, to); leaving the upper bound blank means the top tier. An amount of 0 means that tier pays nothing." },
  "SRS 口径自检": { vi: "Tự kiểm tra chuẩn SRS", en: "SRS self-check" },
  "运行自检": { vi: "Chạy tự kiểm tra", en: "Run self-check" },
  "员工计薪属性": { vi: "Thuộc tính tính lương của nhân viên", en: "Employee payroll attributes" },
  "部门": { vi: "Bộ phận", en: "Department" },
  "人员类别": { vi: "Loại nhân sự", en: "Employee category" },
  "试用期(天)": { vi: "Thử việc (ngày)", en: "Probation (days)" },
  "试用期止": { vi: "Hết thử việc", en: "Probation ends" },
  "参保": { vi: "Tham gia BH", en: "Insured" },
  "未参保原因": { vi: "Lý do chưa tham gia BH", en: "Reason not insured" },
  "工会会员": { vi: "Thành viên công đoàn", en: "Union member" },
  "休假类型字典（越南法规口径）": { vi: "Từ điển loại nghỉ phép (theo luật Việt Nam)", en: "Leave type dictionary (Vietnam labour law)" },
  "依据《劳动法》45/2019/QH14 与《社会保险法》58/2014/QH13。": { vi: "Căn cứ Bộ luật Lao động 45/2019/QH14 và Luật Bảo hiểm xã hội 58/2014/QH13.", en: "Based on the Labour Code 45/2019/QH14 and the Social Insurance Law 58/2014/QH13." },
  "公司发薪": { vi: "Công ty trả lương", en: "Paid by company" },
  "＝按「时薪 × 8 × 天数」计入应发；": { vi: "= tính vào lương gộp theo 「lương giờ × 8 × số ngày」;", en: "= included in gross pay as 「hourly rate × 8 × days」;" },
  "计入算考勤天数": { vi: "Tính vào số ngày chuyên cần", en: "Counts toward attendance days" },
  "＝满勤奖与按天折算补贴不因该假扣减（年假、婚假、丧假、调休、献血假属此列）。 病假/产假/陪产假由社保发津贴，公司不发工资；事假与无薪假既不发薪也不计考勤。 休假申请单的下拉选项取自本字典，改动字典即改单据口径。": { vi: "= Tiền thưởng chuyên cần và phụ cấp quy đổi theo ngày không bị trừ vì loại nghỉ này (phép năm, kết hôn, tang, nghỉ bù, hiến máu thuộc nhóm này). Nghỉ ốm / thai sản / nghỉ cha do BHXH chi trả, công ty không trả lương; nghỉ việc riêng và nghỉ không lương vừa không trả lương vừa không tính chuyên cần. Danh sách chọn trên phiếu nghỉ lấy từ từ điển này, sửa từ điển là sửa chuẩn của phiếu.", en: "= Attendance bonus and day-prorated allowances are not reduced by this leave (annual, marriage, bereavement, compensatory and blood-donation leave belong here). Sick, maternity and paternity leave are paid by social insurance, not by the company; personal and unpaid leave are neither paid nor counted as attendance. The options on the leave form come from this dictionary, so editing it changes the form." },
  "年假额度": { vi: "Hạn mức phép năm", en: "Annual leave quota" },
  "＝每上满一个自然月攒 1 天，年度封顶 12 天，未上满的月份不计、上年未休完不结转；": { vi: "= Mỗi tháng làm đủ được 1 ngày, tối đa 12 ngày/năm, tháng chưa đủ không tính, phép năm trước chưa nghỉ không chuyển sang;", en: "= 1 day accrued per full calendar month, capped at 12 days a year; partial months do not count and unused days do not carry over;" },
  "超额不可提交": { vi: "Vượt hạn mức không thể gửi", en: "Over-quota cannot be submitted" },
  "（系统在提交单据时就拒，不再等计薪告警）。其它假别维持「只告警不拦」。": { vi: "(Hệ thống từ chối ngay khi gửi phiếu, không chờ cảnh báo tính lương). Các loại nghỉ khác vẫn chỉ cảnh báo, không chặn.", en: "(The system rejects it at submission instead of waiting for a payroll warning.) Other leave types remain warning-only." },
  "越南语法定名称": { vi: "Tên pháp lý tiếng Việt", en: "Vietnamese legal name" },
  "天数规则": { vi: "Quy tắc số ngày", en: "Day rule" },
  "谁付钱": { vi: "Ai chi trả", en: "Paid by" },
  "法定上限": { vi: "Hạn mức pháp lý", en: "Legal cap" },
  "额度规则": { vi: "Quy tắc hạn mức", en: "Quota rule" },
  "计薪影响": { vi: "Ảnh hưởng tính lương", en: "Payroll effect" },
  "法规依据": { vi: "Căn cứ pháp lý", en: "Legal basis" },
  "额度试算（请假前先看还剩几天）": { vi: "Tính thử hạn mức (xem còn mấy ngày trước khi xin nghỉ)", en: "Quota estimate (check remaining days before applying)" },
  "年假台账（全员）": { vi: "Sổ phép năm (toàn bộ nhân viên)", en: "Annual leave ledger (all employees)" },
  "年度": { vi: "Năm", en: "Year" },
  "假别": { vi: "Loại nghỉ", en: "Leave type" },
  "姓名 / 工号": { vi: "Họ tên / Mã số", en: "Name / Employee No." },
  "算到（默认今天）": { vi: "Tính đến (mặc định hôm nay)", en: "As of (default today)" },
  "保存本期记账": { vi: "Lưu ghi sổ kỳ này", en: "Save this period" },
  "导出 CSV": { vi: "Xuất CSV", en: "Export CSV" },
  "入职日": { vi: "Ngày vào làm", en: "Hire date" },
  "满月": { vi: "Tháng đủ", en: "Full months" },
  "系统累积": { vi: "Hệ thống tích lũy", en: "System accrued" },
  "结转": { vi: "Chuyển sang", en: "Carried over" },
  "切换前已休": { vi: "Đã nghỉ trước khi chuyển hệ thống", en: "Taken before switch" },
  "调账": { vi: "Điều chỉnh", en: "Adjustment" },
  "可享": { vi: "Được hưởng", en: "Entitled" },
  "电子流已休": { vi: "Đã nghỉ (phiếu điện tử)", en: "Taken (e-form)" },
  "审批中": { vi: "Đang duyệt", en: "Pending approval" },
  "可休": { vi: "Còn được nghỉ", en: "Available" },
  "额度规则 ·": { vi: "Quy tắc hạn mức · ", en: "Quota rule · " },
  "累积方式": { vi: "Cách tích lũy", en: "Accrual method" },
  "固定额度（不累积）": { vi: "Hạn mức cố định (không tích lũy)", en: "Fixed quota (no accrual)" },
  "每满一个自然月累积": { vi: "Tích lũy mỗi tháng đủ", en: "Accrue per full month" },
  "每月累积天数": { vi: "Số ngày tích lũy mỗi tháng", en: "Days accrued per month" },
  "年度额度上限": { vi: "Hạn mức tối đa năm", en: "Annual cap" },
  "超额处理": { vi: "Xử lý vượt hạn mức", en: "Over-quota handling" },
  "不可透支（提交时拦截）": { vi: "Không cho vượt (chặn khi gửi)", en: "No overdraft (blocked at submission)" },
  "允许超额（仅计薪告警）": { vi: "Cho phép vượt (chỉ cảnh báo khi tính lương)", en: "Overdraft allowed (payroll warning only)" },
  "上年未休完": { vi: "Phép năm trước chưa nghỉ", en: "Unused last year" },
  "不结转": { vi: "Không chuyển sang", en: "No carry-over" },
  "结转到次年": { vi: "Chuyển sang năm sau", en: "Carry over to next year" },
  "休假明细 ·": { vi: "Chi tiết nghỉ phép · ", en: "Leave detail · " },
  "电子流（休假申请单，自动抵扣）": { vi: "Phiếu điện tử (đơn xin nghỉ, tự động trừ)", en: "E-forms (leave requests, auto-deducted)" },
  "单据": { vi: "Phiếu", en: "Document" },
  "起": { vi: "Từ", en: "From" },
  "止": { vi: "Đến", en: "To" },
  "天数": { vi: "Số ngày", en: "Days" },
  "手工记账（切换前存量 / 结转 / 调账）": { vi: "Ghi tay (tồn trước khi chuyển / chuyển sang / điều chỉnh)", en: "Manual entries (opening / carry-over / adjustment)" },
  "原因": { vi: "Lý do", en: "Reason" },
  "记账时间": { vi: "Thời điểm ghi sổ", en: "Recorded at" },

  /* ---------- 发放规则（2026-10-28 新增：按出勤天数 / 按夜班天数 / 工时阶梯） ---------- */
  "发放规则": { vi: "Quy tắc chi trả", en: "Payment rule" },
  "固定金额（不随出勤变）": { vi: "Số tiền cố định (không đổi theo chấm công)", en: "Fixed amount (independent of attendance)" },
  "按出勤天数（金额 ÷ 计薪分母 × 出勤天数）": { vi: "Theo ngày công (số tiền ÷ mẫu số tính lương × ngày công)", en: "Per attendance day (amount ÷ payroll denominator × days)" },
  "按夜班天数（金额 × 夜班天数）": { vi: "Theo số ngày ca đêm (số tiền × số ngày)", en: "Per night-shift day (amount × days)" },
  "按夜班班次（金额 × 班次数）": { vi: "Theo số ca đêm (số tiền × số ca)", en: "Per night shift (amount × shifts)" },
  "工时阶梯（全发 / 50% / 不发）": { vi: "Bậc thang giờ (đủ / 50% / không)", en: "Hour tiers (full / 50% / none)" },
  "工时阶梯（全发/50%/不发）": { vi: "Bậc thang giờ (đủ/50%/không)", en: "Hour tiers (full/50%/none)" },
  "度量对象": { vi: "Đối tượng đo", en: "Measured on" },
  "缺勤工时（越少越发）": { vi: "Giờ vắng (càng ít càng nhiều)", en: "Absent hours (fewer pays more)" },
  "出勤工时（越多越发）": { vi: "Giờ đi làm (càng nhiều càng nhiều)", en: "Attended hours (more pays more)" },
  "小于该小时数 → 发全部": { vi: "Nhỏ hơn số giờ này → trả đủ", en: "Below this many hours → pay in full" },
  "大于等于该小时数 → 不发": { vi: "Từ số giờ này trở lên → không trả", en: "At or above this many hours → pay nothing" },
  "中间段自动发 50%。示例：缺勤 < 8h 全发 / 8~16h 发 50% / ≥16h 不发。": { vi: "Khoảng giữa tự động 50%. Ví dụ: vắng < 8h trả đủ / 8~16h trả 50% / ≥16h không trả.", en: "The middle band pays 50%. Example: absent < 8h full / 8~16h 50% / ≥16h none." },
  "中间段发 50%。示例：缺勤 < 8h 全发 / 8~16h 发 50% / ≥16h 不发。": { vi: "Khoảng giữa trả 50%. Ví dụ: vắng < 8h trả đủ / 8~16h 50% / ≥16h không trả.", en: "The middle band pays 50%. Example: absent < 8h full / 8~16h 50% / ≥16h none." },
  "确定": { vi: "Xác nhận", en: "OK" },
  "按出勤天数": { vi: "Theo ngày công", en: "Per attendance day" },
  "按夜班天数": { vi: "Theo ngày ca đêm", en: "Per night-shift day" },
  "按夜班班次": { vi: "Theo ca đêm", en: "Per night shift" },
  "按出勤比例": { vi: "Theo tỷ lệ ngày công", en: "Prorated by attendance" },
  "工时阶梯阈值（按当月累计工时判定）": { vi: "Ngưỡng bậc thang giờ (theo giờ lũy kế trong tháng)", en: "Hour-tier thresholds (by monthly cumulative hours)" },

  /* ---------- 上述页签的整块说明（键＝页面文字，勿手改） ---------- */
  "SRS 4.1：同一名员工在正常工时 / 加班 / 法定假日可以用不同基数——工人三套相同，干部加班基数约为全薪的一半。 每个用途勾选参与计算的工资项（权重默认 1），时薪 = 该用途基数 ÷ 分母工时。金额仍然只在「薪资结构」里维护，这里只决定哪几项相加。": { vi: "SRS 4.1: Cùng một nhân viên có thể dùng cơ sở khác nhau cho giờ bình thường / tăng ca / ngày lễ — công nhân ba cơ sở giống nhau, cán bộ cơ sở tăng ca khoảng một nửa lương đầy đủ. Mỗi mục đích chọn các khoản lương tham gia tính (trọng số mặc định 1); lương giờ = cơ sở của mục đích ÷ giờ mẫu số. Số tiền vẫn chỉ khai ở 「Cơ cấu lương」, ở đây chỉ quyết định cộng những khoản nào.", en: "SRS 4.1: the same employee may use different bases for normal hours / overtime / public holidays — workers use the same base for all three, while staff use roughly half of full salary for overtime. For each purpose, tick the pay items that participate (weight defaults to 1); hourly rate = that purpose base ÷ denominator hours. Amounts are still maintained only in 「Salary Structure」; here you decide which items are summed." },
  "逐条复算 SRS 正文里给出的数值示例（工人/干部时薪、采用倍率、舍入、加班小时、个税、方案构成）， 不涉及任何真人数据。全绿说明代码口径与文件一致；任何一条红了就说明代码和文件已经分叉。": { vi: "Tính lại từng ví dụ số trong nội dung SRS (lương giờ công nhân / cán bộ, hệ số áp dụng, làm tròn, giờ tăng ca, thuế TNCN, cấu trúc phương án), không dùng dữ liệu người thật. Tất cả xanh nghĩa là mã nguồn khớp tài liệu; một dòng đỏ nghĩa là đã lệch.", en: "Recomputes every numeric example given in the SRS (worker and staff hourly rates, applied multipliers, rounding, overtime hours, PIT, scheme composition) — no real personal data. All green means code matches the document; any red means they have diverged." },
  "SRS FR-STAT-03：每位员工必须有参保状态，未参保必须选原因，否则阻断封账；工会费按会员标志计 27,000/月； 试用期天数用于按 85% 计发并与正式期分列。未填写的员工在计薪时会出「未登记参保状态」告警。": { vi: "SRS FR-STAT-03: Mỗi nhân viên phải có trạng thái tham gia BH, nếu không tham gia phải chọn lý do, nếu không sẽ chặn chốt kỳ; phí công đoàn tính 27.000/tháng theo cờ thành viên; số ngày thử việc dùng để trả 85% và tách riêng khỏi giai đoạn chính thức. Nhân viên chưa khai sẽ có cảnh báo 「chưa đăng ký tham gia BH」 khi tính lương.", en: "SRS FR-STAT-03: every employee must have an insurance status; if not insured a reason is mandatory, otherwise period closing is blocked; the union fee is 27,000/month per membership flag; probation days are paid at 85% and shown separately from the regular period. Employees left blank trigger an 「insurance status not registered」 warning during payroll." },
  "可享＝系统累积（每满一个自然月 1 天）＋结转＋调账−切换前已休；可休＝可享−电子流占用（已休＋审批中）。 中途切系统时，员工在旧系统或纸面已经休掉的年假填「切换前已休」，跨年带来的余额填「结转」—— 都按人按年只存一格，改完点保存本期记账。休假申请单（电子流）会自动累加，不要重复录， 否则同一段假会被扣两次。": { vi: "Được hưởng = tích lũy hệ thống (1 ngày mỗi tháng đủ) + chuyển sang + điều chỉnh − đã nghỉ trước khi chuyển hệ thống; Còn được nghỉ = được hưởng − phiếu điện tử chiếm chỗ (đã nghỉ + đang duyệt). Khi chuyển hệ thống giữa năm, phép năm nhân viên đã nghỉ trên hệ thống cũ hoặc trên giấy thì nhập vào 「Đã nghỉ trước khi chuyển hệ thống」, số dư mang từ năm trước nhập vào 「Chuyển sang」 — mỗi người mỗi năm chỉ lưu một ô, sửa xong bấm lưu ghi sổ kỳ này. Đơn xin nghỉ (phiếu điện tử) tự động cộng dồn, không nhập lại, nếu không cùng một đợt nghỉ sẽ bị trừ hai lần.", en: "Entitled = system accrued (1 day per full calendar month) + carried over + adjustment − taken before the system switch; Available = entitled − e-form usage (taken + pending approval). When switching systems mid-year, enter leave already taken on the old system or on paper as 「Taken before switch」, and any balance brought from previous years as 「Carried over」 — one cell per person per year. After editing, click save. Leave e-forms accumulate automatically; do not enter them again or the same leave is deducted twice." },
  "表格里只有「结转」「切换前已休」两列可以改，其余都是算出来的。要填负数请用「调账」，它留流水可追溯。 点「调账」可以给某人补一笔 ±天数并写原因（例如离职清算、录错更正）。": { vi: "Trong bảng chỉ hai cột 「Chuyển sang」 và 「Đã nghỉ trước khi chuyển hệ thống」 là sửa được, còn lại đều là tính ra. Muốn nhập số âm hãy dùng 「Điều chỉnh」 để còn lưu vết. Bấm 「Điều chỉnh」 để cộng hoặc trừ ± ngày cho một người kèm lý do (ví dụ quyết toán nghỉ việc, sửa nhập sai).", en: "Only the 「Carried over」 and 「Taken before switch」 columns are editable; the rest are computed. To enter a negative number use 「Adjustment」, which keeps an audit trail. Use 「Adjustment」 to add or subtract ± days for one person with a reason (e.g. exit settlement, correcting a data-entry error)." },
  "「每满一月累积」按入职日逐月推进，未上满的月份不计，每年 1 月 1 日重新起算（不结转）。 设成不可透支后，员工提交休假单时额度不足会当场被拒，文案里会给出已累积/已占用/可休天数。": { vi: "「Tích lũy mỗi tháng đủ」 tiến theo ngày vào làm, tháng chưa đủ không tính, ngày 1/1 hằng năm tính lại từ đầu (không chuyển sang). Khi đặt là không cho vượt, nhân viên gửi đơn nghỉ mà không đủ hạn mức sẽ bị từ chối ngay, nội dung sẽ ghi rõ đã tích lũy / đã dùng / còn được nghỉ.", en: "「Accrue per full month」 advances from the hire date; partial months do not count; the count restarts on 1 January each year (no carry-over). With overdraft disabled, a leave request without enough quota is rejected immediately, and the message states accrued / used / available days." },

  "工时比例阶梯（任意档位 · 任意比例）": { vi: "Thang tỷ lệ theo giờ (số bậc tùy ý · tỷ lệ tùy ý)", en: "Hour-based ratio tiers (any number of tiers · any ratio)" },
  "比例阶梯（从上往下取第一个满足的档，比例可任意填）": { vi: "Thang tỷ lệ (lấy bậc đầu tiên thỏa từ trên xuống, tỷ lệ điền tùy ý)", en: "Ratio tiers (first matching tier from the top wins; any ratio allowed)" },
  "条件": { vi: "Điều kiện", en: "Condition" },
  "发放比例": { vi: "Tỷ lệ chi trả", en: "Payout ratio" },
  "+ 添加一档": { vi: "+ Thêm một bậc", en: "+ Add tier" },
  "超出最后一档时": { vi: "Khi vượt bậc cuối cùng", en: "When above the last tier" },
  "比例阶梯（按当月累计工时判定，任意档位、任意比例）": { vi: "Thang tỷ lệ (xét theo giờ tích lũy trong tháng, số bậc và tỷ lệ tùy ý)", en: "Ratio tiers (judged on month-to-date hours; any tiers, any ratios)" },
  "例：缺勤 < 8h 发 100% / < 12h 发 50% / < 16h 发 10% / 其余不发。 比例可以填任意值（10、33.3 都行），中间不做插值。": { vi: "Ví dụ: vắng < 8h trả 100% / < 12h trả 50% / < 16h trả 10% / còn lại không trả. Tỷ lệ điền giá trị bất kỳ (10 hay 33.3 đều được), không nội suy ở giữa.", en: "Example: absence < 8h pays 100% / < 12h pays 50% / < 16h pays 10% / otherwise nothing. Any ratio is allowed (10 or 33.3), with no interpolation between tiers." },
  "个人 % / 定额": { vi: "Cá nhân % / định mức", en: "Employee % / fixed amount" },
  "定额": { vi: "Định mức", en: "Fixed amount" },
  "不适用": { vi: "Không áp dụng", en: "N/A" },
  /* @@APPEND@@ */
};

