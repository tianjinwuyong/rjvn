/**
 * 受控文件评审 · 阅读抽屉（oa-doc-review-drawer.js）
 * ---------------------------------------------------------------------------
 * 背景（ISO 9001 7.5.2 / 8.3）：
 *   体系文件必须"经过评审才能生效"，而评审的前提是评审人能读到被评审内容。
 *   但 /flow/detail/:id 只渲染 form_schema 里的元数据（版本号/级别/密级…），
 *   正文与附件完全不可见 —— 审批人是在没看到文件的情况下点"通过"的。
 *
 * 本脚本提供两处入口：
 *   1) /flow/detail/<id>   右下角浮动按钮「受审文件」：打开抽屉 = 文件本体
 *                          （版本/密级/编制人 + 中越正文 + 附件）+ 评审进度与意见
 *   2) /docs/ledger*、/docs 查询结果：每行插「评审」按钮 → 同一抽屉
 *                          （只看评审过程，正文给链接跳到文件页）
 *
 * 数据来源：
 *   GET /api/instances/:id/doc-review            实例 → 被评审文件（参与人可见）
 *   GET /api/instances/:id/doc-content?lang=zh   正文 HTML（懒加载，700KB 不预取）
 *   GET /api/docs/:id/review-nodes               评审进度（含各人意见）
 *   GET /api/docs/:id                            无实例时取正文
 *
 * 卸除：删除本文件 + index.html 中 <script>，无副作用。
 */
(function () {
  'use strict';

  var STYLE_ID = 'oa-doc-rev-drawer-style';
  var DRAWER_ID = 'oa-doc-rev-drawer';
  var FAB_ID = 'oa-doc-rev-fab';
  var ROW_CLS = 'oa-rev-row-btn';

  var T = {
    zh: {
      fab: '受审文件',
      fabPending: '待评审文件',
      title: '受控文件评审',
      docNo: '文件编号',
      docName: '文件名称',
      version: '评审版本',
      level: '文件级别',
      category: '分类',
      security: '密级',
      author: '编制',
      dept: '责任部门',
      status: '文件状态',
      change: '修订摘要',
      content: '文件正文',
      readNow: '阅读全文',
      loading: '加载中…',
      noContent: '该语言没有正文，请看附件或切换语言。',
      attachments: '附件',
      download: '下载',
      noAttach: '无附件',
      progress: '评审过程',
      progressEmpty: '该文件还没有发起评审。',
      openDoc: '打开文件页',
      close: '关闭',
      approver: '审批人',
      comment: '意见',
      notCurrent: '注意：评审版本不是文件当前版本',
      skipped: '已跳过',
      processing: '处理中',
      pending: '待处理',
      approved: '已通过',
      rejected: '已驳回',
      autoSkip: '发起人本人即本节点审批人，自动跳过',
      st_draft: '草稿',
      st_reviewing: '评审中',
      st_published: '已发行',
      st_rejected: '已驳回',
      st_obsolete: '已作废',
      lv1: '一级（管理手册）', lv2: '二级（程序文件）',
      lv3: '三级（作业指导书）', lv4: '四级（记录表单）',
      rowBtn: '评审',
      rowTip: '查看评审过程',
      fail: '加载失败',
      noPerm: '无权查看该文件',
      fileTitle: '受审文件',
      readBody: '阅读文件正文',
      pendingHint: '本单待您处理，请先阅读文件正文再决定是否通过',
      bannerTip: '评审人可在下方抽屉中查看正文、附件与各节点意见',
      assignDeptLeader: '部门负责人',
      assignPosition: '岗位',
      assignPositionSelf: '本人职级及以上',
      assignRole: '角色',
      // ---- 没读不能批（ISO 7.5.2）----
      readOk: '已阅读',
      readAtTip: '阅读于 ',
      waivedTip: '已确认未读',
      readAgain: '再看正文',
      gateTitle: '请先阅读受审文件',
      gateBody1: '系统没有记录到您阅读本单受审文件的正文。按 ISO 9001 7.5.2，评审人应先阅读文件正文，再作批准或驳回。',
      gateBody2: '如正文不在系统里（纸质版、扫描件、或本版只有附件），可确认未读并说明原因后继续，该说明会写入审计痕迹。',
      gateFile: '受审文件',
      gateGoRead: '先去阅读正文',
      gateWaive: '确认未读，仍要通过',
      gateWaiveSubmit: '确认通过',
      gateCancel: '取消',
      gateReasonPh: '例如：纸质版已现场评审并签字，系统内无正文',
      gateReasonShort: '请填写原因（至少 2 个字）',
      gateFail: '校验失败，请重试',
      gateOldVersion: '系统记录到您阅读的是该文件的上一版本（V{ver}），请重新阅读本次评审版本。',
    },
    vi: {
      fab: 'Tài liệu thẩm định',
      fabPending: 'Tài liệu chờ duyệt',
      title: 'Thẩm định tài liệu kiểm soát',
      docNo: 'Mã tài liệu',
      docName: 'Tên tài liệu',
      version: 'Phiên bản thẩm định',
      level: 'Cấp tài liệu',
      category: 'Phân loại',
      security: 'Mức mật',
      author: 'Người soạn',
      dept: 'Bộ phận',
      status: 'Trạng thái',
      change: 'Tóm tắt sửa đổi',
      content: 'Nội dung tài liệu',
      readNow: 'Đọc toàn văn',
      loading: 'Đang tải…',
      noContent: 'Phiên bản này không có nội dung, xem tệp đính kèm hoặc đổi ngôn ngữ.',
      attachments: 'Tệp đính kèm',
      download: 'Tải',
      noAttach: 'Không có tệp',
      progress: 'Quá trình thẩm định',
      progressEmpty: 'Tài liệu chưa được đưa ra thẩm định.',
      openDoc: 'Mở trang tài liệu',
      close: 'Đóng',
      approver: 'Người duyệt',
      comment: 'Ý kiến',
      notCurrent: 'Lưu ý: phiên bản thẩm định không phải bản hiện hành',
      skipped: 'Bỏ qua',
      processing: 'Đang xử lý',
      pending: 'Chờ xử lý',
      approved: 'Đã duyệt',
      rejected: 'Từ chối',
      autoSkip: 'Người gửi chính là người duyệt duy nhất — tự động bỏ qua',
      st_draft: 'Bản nháp',
      st_reviewing: 'Đang thẩm định',
      st_published: 'Đã ban hành',
      st_rejected: 'Bị từ chối',
      st_obsolete: 'Hết hiệu lực',
      lv1: 'Cấp 1 (Sổ tay)', lv2: 'Cấp 2 (Quy trình)',
      lv3: 'Cấp 3 (Hướng dẫn)', lv4: 'Cấp 4 (Biểu mẫu)',
      rowBtn: 'Thẩm định',
      rowTip: 'Xem quá trình thẩm định',
      fail: 'Tải thất bại',
      noPerm: 'Không có quyền xem tài liệu',
      fileTitle: 'Tài liệu thẩm định',
      readBody: 'Đọc nội dung tài liệu',
      pendingHint: 'Phiếu này đang chờ bạn xử lý — vui lòng đọc nội dung tài liệu trước khi quyết định',
      bannerTip: 'Người thẩm định xem nội dung, tệp đính kèm và ý kiến từng bước trong ngăn kéo bên dưới',
      assignDeptLeader: 'Trưởng bộ phận',
      assignPosition: 'Vị trí',
      assignPositionSelf: 'Từ cấp bậc của bạn trở lên',
      assignRole: 'Vai trò',
      // ---- Chưa đọc thì không được duyệt (ISO 7.5.2) ----
      readOk: 'Đã đọc',
      readAtTip: 'Đọc lúc ',
      waivedTip: 'Đã xác nhận chưa đọc',
      readAgain: 'Xem lại nội dung',
      gateTitle: 'Vui lòng đọc tài liệu thẩm định trước',
      gateBody1: 'Hệ thống chưa ghi nhận việc bạn đọc nội dung tài liệu của phiếu này. Theo ISO 9001 7.5.2, người thẩm định phải đọc nội dung trước khi phê duyệt hoặc từ chối.',
      gateBody2: 'Nếu nội dung không có trên hệ thống (bản giấy, bản scan, hoặc phiên bản này chỉ có tệp đính kèm), bạn có thể xác nhận chưa đọc kèm lý do để tiếp tục; lý do sẽ được ghi vào dấu vết kiểm toán.',
      gateFile: 'Tài liệu thẩm định',
      gateGoRead: 'Đọc nội dung trước',
      gateWaive: 'Xác nhận chưa đọc, vẫn duyệt',
      gateWaiveSubmit: 'Xác nhận duyệt',
      gateCancel: 'Hủy',
      gateReasonPh: 'Ví dụ: bản giấy đã được thẩm định và ký trực tiếp, hệ thống không có nội dung',
      gateReasonShort: 'Vui lòng nhập lý do (ít nhất 2 ký tự)',
      gateFail: 'Kiểm tra thất bại, vui lòng thử lại',
      gateOldVersion: 'Hệ thống ghi nhận bạn đã đọc phiên bản trước (V{ver}). Vui lòng đọc lại phiên bản đang thẩm định.',
    },
  };

  function lang() {
    try {
      var v = localStorage.getItem('oa_lang') || localStorage.getItem('oa-locale') || 'zh';
      return v === 'vi' ? 'vi' : 'zh';
    } catch (e) { return 'zh'; }
  }
  function t(k) { var d = T[lang()] || T.zh; return d[k] != null ? d[k] : (T.zh[k] || k); }
  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function req(path) {
    var tk = token();
    return fetch(path, { headers: tk ? { Authorization: 'Bearer ' + tk } : {} })
      .then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, status: r.status, json: j }; })
          .catch(function () { return { ok: r.ok, status: r.status, json: null }; });
      })
      .catch(function () { return { ok: false, status: 0, json: null }; });
  }

  // ---------------------------------------------------------------- 样式
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var st = document.createElement('style');
    st.id = STYLE_ID;
    st.textContent = [
      '#oa-doc-rev-fab{position:fixed;right:22px;bottom:96px;z-index:3200;display:flex;align-items:center;gap:8px;',
      'padding:11px 16px;border:0;border-radius:26px;background:#2563eb;color:#fff;font-size:13.5px;font-weight:600;',
      'box-shadow:0 6px 22px rgba(37,99,235,.36);cursor:pointer;font-family:inherit}',
      '#oa-doc-rev-fab:hover{background:#1d4ed8}',
      '#oa-doc-rev-fab.oa-pending{background:#d97706;box-shadow:0 6px 22px rgba(217,119,6,.4)}',
      '#oa-doc-rev-fab .oa-dot{width:7px;height:7px;border-radius:50%;background:#fde68a;flex:0 0 auto}',
      '#oa-doc-rev-mask{position:fixed;inset:0;background:rgba(17,24,39,.34);z-index:3290}',
      '#oa-doc-rev-drawer{position:fixed;top:0;right:0;bottom:0;width:min(860px,94vw);background:#fff;z-index:3300;',
      'display:flex;flex-direction:column;box-shadow:-8px 0 32px rgba(15,23,42,.22);font-size:13px;color:#1f2937}',
      '#oa-doc-rev-drawer .odrd-head{padding:14px 18px;border-bottom:1px solid #e5e7eb;display:flex;gap:12px;align-items:flex-start}',
      '#oa-doc-rev-drawer .odrd-head h3{margin:0;font-size:15px;font-weight:600;line-height:1.4}',
      '#oa-doc-rev-drawer .odrd-sub{color:#6b7280;font-size:12px;margin-top:3px}',
      '#oa-doc-rev-drawer .odrd-x{margin-left:auto;border:0;background:transparent;font-size:20px;line-height:1;color:#9ca3af;cursor:pointer;padding:0 4px}',
      '#oa-doc-rev-drawer .odrd-body{flex:1 1 auto;overflow:auto;padding:16px 18px 24px}',
      '.odrd-sec{margin-bottom:18px}',
      '.odrd-sec-h{font-size:12.5px;font-weight:600;color:#374151;margin-bottom:8px;display:flex;align-items:center;gap:8px}',
      '.odrd-meta{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px 18px;background:#f8fafc;border:1px solid #eef2f7;border-radius:8px;padding:12px 14px}',
      '.odrd-meta div{font-size:12.5px;color:#374151;word-break:break-word}',
      '.odrd-meta span{color:#9ca3af;margin-right:6px}',
      '.odrd-tag{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11.5px;background:#eef2ff;color:#4338ca}',
      '.odrd-warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:6px;padding:7px 10px;font-size:12px;margin-bottom:10px}',
      '.odrd-btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:6px;background:#2563eb;color:#fff;border:0;font-size:12.5px;cursor:pointer;font-family:inherit}',
      '.odrd-btn.ghost{background:#fff;color:#2563eb;border:1px solid #bfdbfe}',
      '.odrd-frame{width:100%;border:1px solid #e5e7eb;border-radius:8px;background:#fff;min-height:220px}',
      '.odrd-node{border:1px solid #eef2f7;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#fff}',
      '.odrd-node-h{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:#374151}',
      '.odrd-st{font-size:11px;padding:1px 7px;border-radius:999px;font-weight:500}',
      '.odrd-st.approved{background:#e8f7ee;color:#047857}',
      '.odrd-st.rejected{background:#fdecec;color:#b91c1c}',
      '.odrd-st.processing{background:#fff7e6;color:#b45309}',
      '.odrd-st.pending{background:#f1f5f9;color:#64748b}',
      '.odrd-st.skipped{background:#f3f4f6;color:#9ca3af}',
      '.odrd-person{font-size:12px;color:#4b5563;margin-top:6px;line-height:1.7}',
      '.odrd-person b{font-weight:600;color:#111827}',
      '.odrd-cmt{color:#6b7280}',
      '.odrd-empty{color:#9ca3af;font-size:12.5px;padding:10px 0}',
      '.odrd-langs{display:flex;gap:6px;margin-bottom:8px}',
      '.odrd-lang{padding:4px 12px;border-radius:6px;border:1px solid #e5e7eb;background:#fff;font-size:12px;cursor:pointer}',
      '.odrd-lang.on{background:#eef2ff;border-color:#c7d2fe;color:#4338ca;font-weight:600}',
      '#oa-doc-rev-banner{display:flex;align-items:center;gap:12px;margin:0 0 12px;padding:12px 16px;',
      'border:1px solid #dbeafe;background:linear-gradient(180deg,#f7fbff,#f2f7ff);border-radius:10px;font-family:inherit}',
      '#oa-doc-rev-banner.oa-pending{border-color:#fcd34d;background:linear-gradient(180deg,#fffdf5,#fff8e8)}',
      '#oa-doc-rev-banner .odb-ico{flex:0 0 auto;display:flex;align-items:center;justify-content:center;width:34px;height:34px;',
      'border-radius:8px;background:#fff;border:1px solid #e2e8f0}',
      '#oa-doc-rev-banner.oa-pending .odb-ico{border-color:#fde68a}',
      '#oa-doc-rev-banner .odb-main{min-width:0;flex:1 1 auto}',
      '#oa-doc-rev-banner .odb-t{font-size:13.5px;font-weight:600;color:#111827;line-height:1.5;word-break:break-word}',
      '#oa-doc-rev-banner .odb-s{font-size:12px;color:#6b7280;margin-top:3px;line-height:1.5}',
      '#oa-doc-rev-banner .odb-warn{font-size:12px;color:#b45309;margin-top:4px;font-weight:600}',
      '#oa-doc-rev-banner .odb-b{flex:0 0 auto;padding:8px 16px;font-size:13px;border-radius:8px}',
      '@media (max-width:640px){#oa-doc-rev-banner{flex-wrap:wrap}#oa-doc-rev-banner .odb-b{width:100%;justify-content:center}}',
      'td .oa-rev-row-btn{display:inline-block;padding:1px 8px;border-radius:10px;border:1px solid #bfdbfe;',
      'background:#eff6ff;color:#2563eb;font-size:11.5px;line-height:18px;cursor:pointer;white-space:nowrap}',
      'td .oa-rev-row-btn:hover{background:#dbeafe}',
      '#oa-doc-rev-banner .odb-read{color:#047857;font-weight:600}',
      // ---- 「没读不能批」确认弹层 ----
      '#oa-doc-gate-mask{position:fixed;inset:0;background:rgba(17,24,39,.45);z-index:3400}',
      '#oa-doc-gate{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(540px,92vw);max-height:88vh;',
      'overflow:auto;background:#fff;border-radius:12px;z-index:3410;box-shadow:0 18px 48px rgba(15,23,42,.3);',
      'font-family:inherit;color:#1f2937}',
      '#oa-doc-gate .odg-h{padding:16px 20px 0;font-size:15.5px;font-weight:600;display:flex;align-items:center;gap:8px}',
      '#oa-doc-gate .odg-b{padding:10px 20px 0;font-size:13px;line-height:1.75;color:#374151}',
      '#oa-doc-gate .odg-b + .odg-b{padding-top:6px;color:#6b7280;font-size:12.5px}',
      '#oa-doc-gate .odg-file{margin:12px 20px 0;padding:9px 12px;background:#f8fafc;border:1px solid #eef2f7;',
      'border-radius:8px;font-size:12.5px;line-height:1.6}',
      '#oa-doc-gate .odg-file b{color:#111827;font-weight:600}',
      '#oa-doc-gate .odg-reason{padding:12px 20px 0}',
      '#oa-doc-gate textarea{width:100%;box-sizing:border-box;min-height:66px;resize:vertical;border:1px solid #e5e7eb;',
      'border-radius:8px;padding:8px 10px;font:13px/1.6 inherit;color:#1f2937;outline:none}',
      '#oa-doc-gate textarea:focus{border-color:#93c5fd;box-shadow:0 0 0 3px rgba(59,130,246,.12)}',
      '#oa-doc-gate .odg-err{color:#b91c1c;font-size:12px;padding:6px 20px 0;display:none}',
      '#oa-doc-gate .odg-f{display:flex;gap:8px;justify-content:flex-end;padding:16px 20px 18px;flex-wrap:wrap}',
      '#oa-doc-gate .odg-btn{padding:8px 15px;border-radius:8px;border:1px solid transparent;font-size:13px;',
      'cursor:pointer;font-family:inherit}',
      '#oa-doc-gate .odg-btn.ghost{background:#fff;border-color:#e5e7eb;color:#4b5563}',
      '#oa-doc-gate .odg-btn.primary{background:#2563eb;color:#fff}',
      '#oa-doc-gate .odg-btn.warn{background:#fff;border-color:#fcd34d;color:#b45309}',
      '#oa-doc-gate .odg-btn.warn.solid{background:#d97706;border-color:#d97706;color:#fff}',
    ].join('');
    document.head.appendChild(st);
  }

  // ---------------------------------------------------------------- 抽屉
  var ST = { docId: null, instanceId: null, payload: null, progress: null, lang: 'zh',
             contentDone: false, contentLoading: false,
             // 阅读痕迹：正文渲染出来的时刻（用于上报停留时长）与最后一次上报的字符数
             readStartAt: 0, readChars: 0 };

  /** 上报阅读痕迹（正文真的渲染出来了才调；字符数由服务端按库内正文实测，不采信前端） */
  function reportRead(dwellMs) {
    if (!ST.instanceId) return;
    var tk = token();
    fetch('/api/instances/' + ST.instanceId + '/doc-read', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' },
        tk ? { Authorization: 'Bearer ' + tk } : {}),
      body: JSON.stringify({ lang: ST.lang, dwellMs: Math.max(0, dwellMs || 0) }),
      keepalive: true,
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.code === 0) {
        // 本页之内立即生效：点「通过」时不用再等一次状态查询
        if (GATE.status) {
          GATE.status.read = true; GATE.status.satisfied = true; GATE.status.reason = 'read';
          if (j.data && j.data.last_read_at) GATE.status.readAt = j.data.last_read_at;
        }
        if (GATE.state === 'block') GATE.state = 'pass';
        refreshBannerRead();
      }
    }).catch(function () { /* 上报失败不影响阅读本身，审批时后端还会再拦一次 */ });
  }

  function closeDrawer() {
    // 关抽屉时补一次停留时长（服务端取较大值，不会因重复上报而累加虚高）
    if (ST.readStartAt) {
      var dwell = Date.now() - ST.readStartAt;
      ST.readStartAt = 0;
      if (dwell > 1000) reportRead(dwell);
    }
    var d = document.getElementById(DRAWER_ID);
    if (d && d.parentNode) d.parentNode.removeChild(d);
    var m = document.getElementById('oa-doc-rev-mask');
    if (m && m.parentNode) m.parentNode.removeChild(m);
  }

  function ensureDrawer() {
    ensureStyle();
    var old = document.getElementById(DRAWER_ID);
    if (old) return old;
    var mask = document.createElement('div');
    mask.id = 'oa-doc-rev-mask';
    mask.onclick = closeDrawer;
    document.body.appendChild(mask);

    var d = document.createElement('div');
    d.id = DRAWER_ID;
    d.innerHTML =
      '<div class="odrd-head">' +
        '<div style="min-width:0">' +
          '<h3 id="odrd-title"></h3>' +
          '<div class="odrd-sub" id="odrd-sub"></div>' +
        '</div>' +
        '<button type="button" class="odrd-x" title="' + esc(t('close')) + '">×</button>' +
      '</div>' +
      '<div class="odrd-body" id="odrd-body"><div class="odrd-empty">' + esc(t('loading')) + '</div></div>';
    d.querySelector('.odrd-x').onclick = closeDrawer;
    document.body.appendChild(d);
    return d;
  }

  function statusChip(s) {
    var map = { draft: 'draft', reviewing: 'reviewing', published: 'published', rejected: 'rejected', obsolete: 'obsolete' };
    var cls = map[String(s)] || 'draft';
    return '<span class="odrd-tag">' + esc(t('st_' + cls)) + '</span>';
  }

  function levelText(lv) {
    var n = Number(lv) || 0;
    return n >= 1 && n <= 4 ? t('lv' + n) : (lv || '-');
  }

  function renderHead(doc, version) {
    var d = document.getElementById(DRAWER_ID);
    if (!d) return;
    d.querySelector('#odrd-title').textContent = (doc.code || '') + '　' + (lang() === 'vi' && doc.title_vi ? doc.title_vi : doc.title || '');
    d.querySelector('#odrd-sub').textContent = t('version') + ' V' + (version || doc.current_version || '') + ' · ' + t('title');
  }

  function renderBody() {
    var body = document.getElementById('odrd-body');
    if (!body) return;
    var p = ST.payload;
    if (!p) { body.innerHTML = '<div class="odrd-empty">' + esc(t('fail')) + '</div>'; return; }

    var doc = p.doc || p;
    var version = p.version || doc.current_version || '';
    var html = '';

    if (p.notCurrent) html += '<div class="odrd-warn">' + esc(t('notCurrent')) + '</div>';

    // 基本信息
    html += '<div class="odrd-sec"><div class="odrd-meta">' +
      '<div><span>' + esc(t('docNo')) + '</span>' + esc(doc.code || '-') + '</div>' +
      '<div><span>' + esc(t('version')) + '</span><b>V' + esc(version) + '</b></div>' +
      '<div><span>' + esc(t('level')) + '</span>' + esc(levelText(doc.level)) + '</div>' +
      '<div><span>' + esc(t('security')) + '</span>' + esc(doc.security_level === 'secret' ? '秘密' : '公开') + '</div>' +
      '<div><span>' + esc(t('author')) + '</span>' + esc(doc.created_by_name || '-') + '</div>' +
      '<div><span>' + esc(t('dept')) + '</span>' + esc(doc.owner_dept || '-') + '</div>' +
      '<div><span>' + esc(t('status')) + '</span>' + statusChip(doc.status) + '</div>' +
      '</div></div>';

    // 正文（仅流程详情页需要；查询页给跳转）
    if (ST.instanceId) {
      var langs = (p.langs || []).filter(function (x) { return Number(x.content_len) > 0 || x.file_name; });
      var hasZh = langs.some(function (x) { return x.lang === 'zh'; });
      var hasVi = langs.some(function (x) { return x.lang === 'vi'; });
      html += '<div class="odrd-sec"><div class="odrd-sec-h">' + esc(t('content')) + '</div>';
      if (hasZh || hasVi) {
        html += '<div class="odrd-langs">';
        if (hasZh) html += '<button type="button" class="odrd-lang' + (ST.lang === 'zh' ? ' on' : '') + '" data-lang="zh">中文</button>';
        if (hasVi) html += '<button type="button" class="odrd-lang' + (ST.lang === 'vi' ? ' on' : '') + '" data-lang="vi">Tiếng Việt</button>';
        html += '</div>';
      }
      html += '<div id="odrd-content"><button type="button" class="odrd-btn" id="odrd-read">' + esc(t('readNow')) + '</button></div>';
      html += '</div>';
    }

    // 附件
    var atts = p.attachments || [];
    html += '<div class="odrd-sec"><div class="odrd-sec-h">' + esc(t('attachments')) + '</div>';
    if (!atts.length) html += '<div class="odrd-empty">' + esc(t('noAttach')) + '</div>';
    else {
      html += '<div>';
      atts.forEach(function (a) {
        html += '<div style="font-size:12.5px;padding:4px 0">' +
          '<a href="/api/files/' + encodeURI(a.file_path || '') + '" target="_blank" rel="noopener" ' +
          'style="color:#2563eb;text-decoration:none">' + esc(a.file_name || '文件') + '</a>' +
          '<span style="color:#9ca3af;margin-left:8px">' + esc(fmtSize(a.file_size)) + '</span></div>';
      });
      html += '</div>';
    }
    html += '</div>';

    // 评审过程
    html += '<div class="odrd-sec"><div class="odrd-sec-h">' + esc(t('progress')) + '</div>' +
            '<div id="odrd-progress"><div class="odrd-empty">' + esc(t('loading')) + '</div></div></div>';

    // 底部
    if (ST.docId) {
      html += '<div style="padding-top:6px"><a class="odrd-btn ghost" href="/docs/' + ST.docId + '" ' +
              'style="text-decoration:none">' + esc(t('openDoc')) + ' →</a></div>';
    }

    body.innerHTML = html;

    body.querySelectorAll('.odrd-lang').forEach(function (b) {
      b.onclick = function () {
        if (ST.lang === b.getAttribute('data-lang')) return;
        ST.lang = b.getAttribute('data-lang'); ST.contentDone = false; ST.contentLoading = false; renderBody();
      };
    });
    var readBtn = body.querySelector('#odrd-read');
    if (readBtn) readBtn.onclick = loadContent;
    // 打开即加载正文：评审人点这个抽屉就是为了看文件，再点一次「阅读全文」纯属多余
    // （2026-11-04 反馈「看不到文件正文」）。正文仅在打开抽屉时请求，不影响详情页首屏。
    if (!ST.contentDone && !ST.contentLoading && body.querySelector('#odrd-content')) loadContent();

    renderProgress();
  }

  function fmtSize(n) {
    var v = Number(n) || 0;
    if (!v) return '';
    if (v < 1024) return v + ' B';
    if (v < 1048576) return (v / 1024).toFixed(1) + ' KB';
    return (v / 1048576).toFixed(1) + ' MB';
  }

  function loadContent() {
    var box = document.getElementById('odrd-content');
    if (!box) return;
    if (ST.contentLoading) return;
    ST.contentLoading = true;
    box.innerHTML = '<div class="odrd-empty">' + esc(t('loading')) + '</div>';
    var url = ST.instanceId
      ? '/api/instances/' + ST.instanceId + '/doc-content?lang=' + ST.lang
      : '/api/docs/' + ST.docId;
    req(url).then(function (r) {
      if (!r.ok) {
        ST.contentLoading = false;
        box.innerHTML = '<div class="odrd-empty">' + esc(r.json && r.json.msg ? r.json.msg : t('noContent')) + '</div>';
        return;
      }
      var content = '';
      if (ST.instanceId) content = (r.json && r.json.data && r.json.data.content) || '';
      else {
        var d = (r.json && r.json.data) || {};
        // getDoc 的双语正文字段是 currentLang（不是 langs），取不到时退中文
        var cur = d.currentLang || d.langs || {};
        var L = cur[ST.lang] || cur.zh;
        content = (L && L.content) || '';
      }
      if (!content) { ST.contentLoading = false; box.innerHTML = '<div class="odrd-empty">' + esc(t('noContent')) + '</div>'; return; }
      // sandbox 不给 allow-scripts：正文是作者粘贴的富文本，不允许执行任何脚本。
      var frame = document.createElement('iframe');
      frame.className = 'odrd-frame';
      frame.setAttribute('sandbox', 'allow-same-origin');
      // 正文是整本手册（84 页 ≈ 10 万 px），不能让它无限撑高抽屉：
      // 固定成「视口高 - 头部/元信息」由 iframe 自己滚，抽屉头部与下方评审过程始终可达
      frame.style.height = Math.max(360, (window.innerHeight || 800) - 300) + 'px';
      frame.srcdoc = '<!doctype html><html><head><meta charset="utf-8">' +
        '<style>body{margin:12px;font:13px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1f2937;word-break:break-word}' +
        'table{max-width:100%}img{max-width:100%;height:auto}td,th{padding:2px 4px}</style></head><body>' +
        content + '</body></html>';
      frame.onload = function () {
        try {
          var h = frame.contentDocument && frame.contentDocument.body ? frame.contentDocument.body.scrollHeight : 0;
          var cap = Math.max(360, (window.innerHeight || 800) - 300);
          if (h > 160) frame.style.height = Math.min(h + 28, cap) + 'px';   // 短文档贴合内容，长文档封顶内滚
        } catch (e) { /* 跨源读不到就保留默认高度 */ }
      };
      box.innerHTML = '';
      box.appendChild(frame);
      ST.contentDone = true;
      ST.contentLoading = false;
      // 正文真的渲染出来了 → 落一条阅读痕迹（ISO 7.5.2 的"读过"证据）
      if (ST.instanceId) {
        ST.readChars = content.length;
        if (!ST.readStartAt) ST.readStartAt = Date.now();
        reportRead(0);
      }
    });
  }

  function renderProgress() {
    var box = document.getElementById('odrd-progress');
    if (!box) return;
    var nodes = (ST.progress && ST.progress.nodes) || [];
    if (!nodes.length) {
      box.innerHTML = '<div class="odrd-empty">' + esc(t('progressEmpty')) + '</div>';
      return;
    }
    var html = '';
    nodes.forEach(function (n) {
      if (n.applies === false) return;
      var st = n.status || 'pending';
      // 进度接口把任务放在 approvers（不是 tasks）：含 status/comment/position/dept
      var people = n.approvers || n.tasks || [];
      html += '<div class="odrd-node">' +
        '<div class="odrd-node-h">' + esc(n.index + 1) + '. ' +
          esc(lang() === 'vi' && n.nameVi ? n.nameVi : n.name) +
          '<span class="odrd-st ' + esc(st) + '">' + esc(t(st)) + '</span>' +
          (n.autoSkipSelf ? '<span style="font-size:11px;color:#9ca3af">' + esc(t('autoSkip')) + '</span>' : '') +
        '</div>';
      if (people.length) {
        html += '<div class="odrd-person">';
        people.forEach(function (p) {
          var nm = p.name || p.real_name || p.username || '—';
          var meta = [p.position, p.dept].filter(Boolean).join(' · ');
          var ps = p.status ? '　' + t(p.status === 'approved' ? 'approved'
            : (p.status === 'rejected' ? 'rejected'
            : (p.status === 'skipped' ? 'skipped' : 'pending'))) : '';
          html += '<div><b>' + esc(nm) + '</b>' +
            (meta ? '<span style="color:#9ca3af">（' + esc(meta) + '）</span>' : '') +
            '<span style="color:#6b7280">' + esc(ps) + '</span>' +
            (p.comment ? '<span class="odrd-cmt">　' + esc(t('comment')) + '：' + esc(p.comment) + '</span>' : '') +
            '</div>';
        });
        html += '</div>';
      } else if (n.assignLabels && n.assignLabels.length) {
        html += '<div class="odrd-person" style="color:#9ca3af">' +
          esc(n.assignLabels.map(function (x) { return humanizeAssign(x[lang()] || x.zh); }).join('、')) + '</div>';
      }
      html += '</div>';
    });
    box.innerHTML = html || '<div class="odrd-empty">' + esc(t('progressEmpty')) + '</div>';
  }

  /**
   * 审批人表达式翻成人话：接口给的是 dept_leader:QA / position:gm 这类引擎口径，
   * 直接显示给评审人等于让他看源码。
   */
  function humanizeAssign(s) {
    var v = String(s == null ? '' : s);
    var i = v.indexOf(':');
    if (i < 0) return v;
    var k = v.slice(0, i), a = v.slice(i + 1);
    if (k === 'dept_leader') return t('assignDeptLeader') + (a ? '（' + a + '）' : '');
    if (k === 'position') return t('assignPosition') + '：' + a;
    if (k === 'position_self') return t('assignPositionSelf') + '：' + a;
    if (k === 'role') return t('assignRole') + '：' + a;
    return a;
  }

  function loadProgress() {
    if (!ST.docId) { ST.progress = null; renderProgress(); return; }
    req('/api/docs/' + ST.docId + '/review-nodes').then(function (r) {
      ST.progress = (r.ok && r.json && r.json.data) ? r.json.data : null;
      renderProgress();
    });
  }

  function openFlow(instanceId) {
    ST.instanceId = Number(instanceId);
    ST.docId = null; ST.payload = null; ST.progress = null; ST.contentDone = false;
    ST.readStartAt = 0; ST.readChars = 0;
    ST.lang = lang();
    ensureDrawer();
    document.getElementById('odrd-body').innerHTML = '<div class="odrd-empty">' + esc(t('loading')) + '</div>';
    document.getElementById('odrd-title').textContent = t('title');
    document.getElementById('odrd-sub').textContent = '';

    req('/api/instances/' + instanceId + '/doc-review').then(function (r) {
      if (!r.ok) {
        document.getElementById('odrd-body').innerHTML =
          '<div class="odrd-empty">' + esc(r.status === 403 ? t('noPerm') : (r.json && r.json.msg) || t('fail')) + '</div>';
        return;
      }
      ST.payload = r.json.data;
      ST.docId = ST.payload.doc && ST.payload.doc.id;
      renderHead(ST.payload.doc, ST.payload.version);
      // 只显示当前实例对应的版本正文；未命中语言时按有内容的那个语言起
      var langs = ST.payload.langs || [];
      if (!langs.some(function (x) { return x.lang === ST.lang && Number(x.content_len) > 0; })) {
        var alt = langs.find(function (x) { return Number(x.content_len) > 0; });
        if (alt) ST.lang = alt.lang;
      }
      ST.payload.notCurrent = ST.payload.isCurrentVersion === false;
      renderBody();
      loadProgress();
    });
  }

  function openDoc(docId) {
    ST.instanceId = null;
    ST.docId = Number(docId);
    ST.readStartAt = 0; ST.readChars = 0;
    ST.payload = null; ST.progress = null;
    ensureDrawer();
    document.getElementById('odrd-body').innerHTML = '<div class="odrd-empty">' + esc(t('loading')) + '</div>';
    req('/api/docs/' + docId).then(function (r) {
      if (!r.ok) {
        document.getElementById('odrd-body').innerHTML =
          '<div class="odrd-empty">' + esc(r.status === 403 ? t('noPerm') : t('fail')) + '</div>';
        return;
      }
      var d = r.json.data || {};
      ST.payload = { doc: d, version: d.current_version, langs: [], attachments: [] };
      renderHead(d, d.current_version);
      renderBody();
      loadProgress();
      // /api/docs/:id 不返回附件清单，单独取一次（查询页抽屉里也要能下载）
      req('/api/docs/' + docId + '/attachments').then(function (a) {
        if (a.ok && a.json && a.json.data && ST.docId === Number(docId)) {
          ST.payload.attachments = a.json.data;
          renderBody();
        }
      });
    });
  }

  // ---------------------------------------------------------------- 流程详情页入口（横幅）
  var BANNER_ID = 'oa-doc-rev-banner';

  /** 「申请内容」卡片：优先用内容匹配找，找不到就退回 main 里第一张卡 */
  function findFormCard() {
    var main = document.querySelector('main.oa-content') || document.querySelector('main');
    if (!main) return null;
    var all = main.querySelectorAll('div');
    for (var i = 0; i < all.length && i < 600; i++) {
      var n = all[i];
      if (n.children.length) continue;
      if ((n.textContent || '').trim() !== '申请内容') continue;
      var c = n;
      while (c && !(c.classList && c.classList.contains('oa-card'))) c = c.parentElement;
      if (c && c.parentNode) return c;
    }
    var first = main.querySelector('.oa-card');
    return first && first.parentNode ? first : null;
  }

  /**
   * 表单卡片正上方的横幅：文件编号 + 名称 + 版本 + 级别 + 「阅读文件正文」。
   * 只靠右下角浮动按钮不够 —— 审批人滚到按钮位置前不会意识到有正文可看
   * （2026-11-04 用户反馈「到评审节点看不到文件正文，如何评审」）。
   */
  function mountFlowBanner(key, p) {
    if (!p || !p.doc) return;
    if (document.getElementById(BANNER_ID)) return;
    var card = findFormCard();
    if (!card) return;
    var doc = p.doc;
    var lvKey = 'lv' + (doc.level || '');
    var lvTxt = t(lvKey) !== lvKey ? t(lvKey) : (doc.level ? 'L' + doc.level : '');

    var el = document.createElement('div');
    el.id = BANNER_ID;
    el.innerHTML =
      '<span class="odb-ico">' +
        '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="#2563eb" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>' +
      '</span>' +
      '<div class="odb-main">' +
        '<div class="odb-t">' + esc(t('fileTitle')) + '：' + esc(doc.code || '') + ' ' + esc(doc.title || '') + '</div>' +
        '<div class="odb-s">' + esc(t('version')) + ' V' + esc(p.version || '') +
          (lvTxt ? ' · ' + esc(lvTxt) : '') +
          (p.isCurrentVersion === false ? ' · ' + esc(t('notCurrent')) : '') +
          '<span class="odb-read"></span></div>' +
        '<div class="odb-warn" style="display:none">' + esc(t('pendingHint')) + '</div>' +
      '</div>' +
      '<button type="button" class="odrd-btn odb-b">' + esc(t('readBody')) + '</button>';
    el.querySelector('.odb-b').onclick = function () { openFlow(key); };
    card.parentNode.insertBefore(el, card);
    el.setAttribute('data-inst', key);
    refreshBannerRead();
  }

  /** 阅读状态的颜色/时间（横幅上直接显示，别让人猜自己算不算"读过"） */
  function fmtReadAt(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    var p2 = function (n) { return (n < 10 ? '0' : '') + n; };
    return p2(d.getMonth() + 1) + '-' + p2(d.getDate()) + ' ' + p2(d.getHours()) + ':' + p2(d.getMinutes());
  }

  function refreshBannerRead() {
    var el = document.getElementById(BANNER_ID);
    if (!el) return;
    var slot = el.querySelector('.odb-read');
    if (!slot) return;
    var st = GATE.status;
    if (st && st.read) {
      slot.textContent = ' · ' + t('readOk') + (st.readAt ? ' ' + fmtReadAt(st.readAt) : '');
      var b = el.querySelector('.odb-b');
      if (b) b.textContent = t('readAgain');
      // 读完了就别再挂"请先阅读再决定"——那句话现在只会误导
      var w = el.querySelector('.odb-warn');
      if (w) w.style.display = 'none';
    } else if (st && st.waived) {
      slot.textContent = ' · ' + t('waivedTip');
      var w2 = el.querySelector('.odb-warn');
      if (w2) w2.style.display = 'none';
    } else {
      slot.textContent = '';
    }
  }

  function markBannerPending(pending) {
    var el = document.getElementById(BANNER_ID);
    if (!el) return;
    if (!pending) return;
    el.classList.add('oa-pending');
    var w = el.querySelector('.odb-warn');
    if (w) w.style.display = '';
    refreshBannerRead();   // 已经读过就别再把"请先阅读"亮出来
  }

  // ---------------------------------------------------------------- 流程详情页入口（浮动按钮）
  // 只在「本单确实关联了体系文件、且当前用户是本单参与人」时才挂按钮：
  // 否则请假、领料等单据上也会冒出一个「受审文件」，点了才发现跟文件无关。
  var FAB = { inst: null, settled: false };

  function mountFlowFab(instanceId) {
    var key = String(instanceId);
    if (FAB.inst === key && FAB.settled) return;
    if (document.getElementById(FAB_ID)) return;

    FAB.inst = key;
    GATE.inst = key;
    GATE.state = 'idle';
    GATE.status = null;
    // 同一个请求既决定"挂不挂按钮"，也决定"点通过时拦不拦"：
    // 阅读状态就在 doc-review 的返回里（readStatus），不为闸门再多打一次接口。
    GATE.promise = req('/api/instances/' + instanceId + '/doc-review').then(function (r) {
      FAB.settled = true;
      if (!r.ok) {
        // 非受控文件单 / 非参与人：没有受审文件，也就无所谓"没读不能批"
        GATE.inst = null; GATE.status = null; GATE.state = 'pass';
        return;
      }
      GATE.status = (r.json && r.json.data && r.json.data.readStatus) || null;
      GATE.state = (!GATE.status || !GATE.status.required || GATE.status.satisfied) ? 'pass' : 'block';
      // 弹层里要显示"哪个文件没读"：抽屉没打开过时 ST.payload 是空的，留一份页面级缓存
      if (r.json && r.json.data) window.OADocLastPayload = r.json.data;
      if (document.getElementById(FAB_ID)) return;
      if (FAB.inst !== key) return;             // 期间已切页

      ensureStyle();                            // ← 原来漏了这句：按钮以浏览器默认样式落在 body 末尾，等于看不见

      var b = document.createElement('button');
      b.id = FAB_ID;
      b.type = 'button';
      b.setAttribute('data-inst', key);
      b.innerHTML = '<span class="oa-dot"></span><span>' + esc(t('fab')) + '</span>';
      b.onclick = function () { openFlow(b.getAttribute('data-inst')); };
      document.body.appendChild(b);
      mountFlowBanner(key, r.json && r.json.data);
      placeFab();
      hookFabPlacement();

      // 当前用户在本单有待办 → 高亮成「待评审文件」，提醒先读完再批
      req('/api/instances/' + instanceId).then(function (v) {
        var d = (v.ok && v.json && v.json.data) || null;
        var cur = document.getElementById(FAB_ID);
        if (!cur || !d || FAB.inst !== key) return;
        if (d.myTask) {
          cur.classList.add('oa-pending');
          cur.querySelector('span:last-child').textContent = t('fabPending');
          markBannerPending(true);
        }
      });
    });
  }

  /**
   * 浮动按钮避让底部操作栏（oa-action-bar，sticky 57px）。
   * 固定 bottom:96px 在 900 高的窗口刚好擦到「通过」按钮的上沿，窗口再矮一点就直接压住
   * —— 审批人点不到最关键的按钮。这里按操作栏实际位置算间距，滚动/缩放时重算。
   */
  function placeFab() {
    var b = document.getElementById(FAB_ID);
    if (!b) return;
    var bar = document.querySelector('.oa-action-bar');
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var bottom = 96;
    if (bar) {
      var r = bar.getBoundingClientRect();
      if (r.top > 0 && r.top < vh) bottom = Math.round(vh - r.top) + 12;
    }
    b.style.bottom = Math.max(20, bottom) + 'px';
  }

  var fabHooked = false;
  function hookFabPlacement() {
    if (fabHooked) return;
    fabHooked = true;
    var raf = 0;
    var kick = function () {
      if (raf) return;
      raf = requestAnimationFrame(function () { raf = 0; placeFab(); });
    };
    window.addEventListener('scroll', kick, true);
    window.addEventListener('resize', kick);
  }

  function unmountFab() {
    var b = document.getElementById(FAB_ID);
    if (b && b.parentNode) b.parentNode.removeChild(b);
    FAB.inst = null; FAB.settled = false;
    GATE.inst = null; GATE.status = null; GATE.state = 'idle'; GATE.promise = null;
  }

  // ---------------------------------------------------------------- 没读不能批
  // ISO 9001 7.5.2：文件发布前的评审，评审人得先看过文件。
  // 前端在点「通过」那一刻查阅读状态（同步，早已随 doc-review 一起取回）：
  //   · 已读 / 本单没有正文 → 直接放行
  //   · 没读 → 拦下点击，弹确认框：要么去读，要么写明原因后确认未读通过
  // 后端 approveTask 里还有同一道闸（doc-review-read.assertDocReviewed），
  // 前端这道只是把拒绝变成可操作的提示，不是唯一防线。
  var GATE = { inst: null, status: null, state: 'idle', promise: null, bypass: false };
  var GATE_MASK_ID = 'oa-doc-gate-mask';
  var GATE_ID = 'oa-doc-gate';
  var APPROVE_WORDS = ['通过', '同意', '批准', 'Phê duyệt', 'Duyệt', 'Đồng ý', 'Approve'];
  var pendingBtn = null;

  /** 只在底部操作栏里找「通过」；「批量通过」等不是本单审批，不拦 */
  function findApproveBtn(node) {
    var bar = node && node.closest ? node.closest('.oa-action-bar') : null;
    if (!bar) return null;
    var btns = bar.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
      var txt = (btns[i].textContent || '').replace(/\s+/g, '');
      if (!txt || txt.indexOf('批量') >= 0) continue;
      for (var j = 0; j < APPROVE_WORDS.length; j++) {
        if (txt === APPROVE_WORDS[j].replace(/\s+/g, '')) return btns[i];
      }
    }
    return null;
  }

  /** 放行一次点击：置 bypass 让本函数下次直接返回，再把点击原样补发 */
  function replayClick(btn) {
    if (!btn) return;
    GATE.bypass = true;
    try { btn.click(); } catch (e) { GATE.bypass = false; }
  }

  function onDocClickCapture(e) {
    if (GATE.bypass) { GATE.bypass = false; return; }
    if (!GATE.inst) return;
    var btn = findApproveBtn(e.target);
    if (!btn) return;
    if (GATE.state === 'pass') return;               // 已读 / 无需校验 → 不打扰
    if (document.getElementById(GATE_ID)) {         // 弹层已开着，别叠第二层
      e.preventDefault(); e.stopPropagation();
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      return;
    }

    // 拦下这次点击（Vue 的 handler 在元素上，捕获阶段掐断就到不了它）
    e.preventDefault();
    e.stopPropagation();
    if (e.stopImmediatePropagation) e.stopImmediatePropagation();

    if (GATE.state === 'block') { openGateModal(btn); return; }
    // 状态还没回来：等它回来再决定，别先放过去让后端 409 糊一个红条
    var p = GATE.promise || Promise.resolve();
    p.then(function () {
      if (GATE.state === 'pass' || !GATE.inst) replayClick(btn);
      else openGateModal(btn);
    }).catch(function () { replayClick(btn); });
  }

  function closeGateModal() {
    [GATE_ID, GATE_MASK_ID].forEach(function (id) {
      var n = document.getElementById(id);
      if (n && n.parentNode) n.parentNode.removeChild(n);
    });
    pendingBtn = null;
  }

  function openGateModal(btn) {
    ensureStyle();                                    // 新增 DOM 必须显式 ensureStyle，否则样式全丢
    closeGateModal();
    pendingBtn = btn || null;
    var st = GATE.status || {};
    var p = ST.payload || (window.OADocLastPayload || null);
    var doc = (p && p.doc) || {};
    var code = doc.code || '';
    var title = doc.title || '';

    var mask = document.createElement('div');
    mask.id = GATE_MASK_ID;
    mask.onclick = closeGateModal;
    document.body.appendChild(mask);

    var d = document.createElement('div');
    d.id = GATE_ID;
    d.setAttribute('role', 'dialog');
    d.innerHTML =
      '<div class="odg-h">' +
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#d97706" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>' +
        '<span>' + esc(t('gateTitle')) + '</span>' +
      '</div>' +
      '<div class="odg-b">' + esc(t('gateBody1')) + '</div>' +
      (code || title
        ? '<div class="odg-file">' + esc(t('gateFile')) + '：<b>' + esc(code) + ' ' + esc(title) + '</b>' +
          (st.version ? '　V' + esc(st.version) : '') + '</div>'
        : '') +
      (st.reason === 'stale_version' && st.staleVersion
        ? '<div class="odg-b">' + esc(String(t('gateOldVersion')).replace('{ver}', st.staleVersion)) + '</div>'
        : '') +
      '<div class="odg-b">' + esc(t('gateBody2')) + '</div>' +
      '<div class="odg-reason" style="display:none"><textarea id="odg-why" maxlength="300" placeholder="' +
        esc(t('gateReasonPh')) + '"></textarea></div>' +
      '<div class="odg-err" id="odg-err"></div>' +
      '<div class="odg-f">' +
        '<button type="button" class="odg-btn ghost" data-a="cancel">' + esc(t('gateCancel')) + '</button>' +
        '<button type="button" class="odg-btn primary" data-a="read">' + esc(t('gateGoRead')) + '</button>' +
        '<button type="button" class="odg-btn warn" data-a="waive">' + esc(t('gateWaive')) + '</button>' +
      '</div>';
    document.body.appendChild(d);

    var why = d.querySelector('#odg-why');
    var errBox = d.querySelector('#odg-err');
    var waiveBtn = d.querySelector('[data-a="waive"]');
    var waived = false;   // 第一次点展开原因框，第二次才真的提交

    function showErr(m) { errBox.textContent = m; errBox.style.display = 'block'; }

    d.querySelector('[data-a="cancel"]').onclick = closeGateModal;
    d.querySelector('[data-a="read"]').onclick = function () {
      var inst = GATE.inst;
      closeGateModal();
      if (inst) openFlow(inst);
    };
    waiveBtn.onclick = function () {
      if (!waived) {
        waived = true;
        d.querySelector('.odg-reason').style.display = 'block';
        waiveBtn.className = 'odg-btn warn solid';
        waiveBtn.textContent = t('gateWaiveSubmit');
        why.focus();
        return;
      }
      var reason = (why.value || '').trim();
      if (reason.length < 2) { showErr(t('gateReasonShort')); why.focus(); return; }
      var tk = token();
      errBox.style.display = 'none';
      waiveBtn.disabled = true;
      fetch('/api/instances/' + GATE.inst + '/doc-read-waiver', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' },
          tk ? { Authorization: 'Bearer ' + tk } : {}),
        body: JSON.stringify({ reason: reason }),
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          waiveBtn.disabled = false;
          if (!res.ok || !res.j || res.j.code !== 0) {
            showErr((res.j && res.j.msg) || t('gateFail'));
            return;
          }
          if (GATE.status) { GATE.status.waived = true; GATE.status.satisfied = true; }
          GATE.state = 'pass';
          var b = pendingBtn;
          closeGateModal();
          refreshBannerRead();
          replayClick(b);
        })
        .catch(function () { waiveBtn.disabled = false; showErr(t('gateFail')); });
    };

    var first = d.querySelector('[data-a="read"]');
    if (first) first.focus();
  }

  document.addEventListener('click', onDocClickCapture, true);

  // ---------------------------------------------------------------- 查询页行内入口
  var MAP = { at: 0, byCode: {} };

  function buildMap() {
    // 只按时间缓存（20s）：即使结果为 0 条也不再每轮都请求，
    // 否则没有任何文件的租户会每秒打一次 /api/docs。
    if (Date.now() - MAP.at < 20000) return Promise.resolve(MAP);
    return req('/api/docs?page=1&size=200').then(function (r) {
      var list = (r.ok && r.json && r.json.data && r.json.data.list) || [];
      var by = {};
      list.forEach(function (d) { if (d.code) by[String(d.code).trim()] = d.id; });
      MAP = { at: Date.now(), byCode: by };
      return MAP;
    }).catch(function () { return MAP; });
  }

  function mountRowButtons() {
    ensureStyle();
    buildMap().then(function (map) {
      var codes = Object.keys(map.byCode);
      if (!codes.length) return;
      document.querySelectorAll('table tbody tr').forEach(function (tr) {
        if (tr.querySelector('.' + ROW_CLS)) return;
        var txt = tr.textContent || '';
        var hit = null;
        for (var i = 0; i < codes.length; i++) {
          if (txt.indexOf(codes[i]) >= 0) { hit = codes[i]; break; }
        }
        if (!hit) return;
        var tds = tr.querySelectorAll('td');
        if (!tds.length) return;
        var host = tds[tds.length - 1];
        var b = document.createElement('span');
        b.className = ROW_CLS;
        b.textContent = t('rowBtn');
        b.title = t('rowTip');
        b.style.marginLeft = '6px';
        b.onclick = function (ev) {
          ev.stopPropagation();
          ev.preventDefault();
          openDoc(map.byCode[hit]);
        };
        host.appendChild(b);
      });
    });
  }

  // ---------------------------------------------------------------- 路由分发
  // 查询类页面（可挂行内「评审」按钮）：路径取自 sys_module.doc.fe_paths，
  // 台账是 /doc-ledger（不是 /docs/ledger），别按直觉猜。
  var LIST_PAGES = /^\/(docs|doc-ledger|doc-issue-record|doc-obsolete|doc-external|doc-borrow)(\/|$)/;

  function run() {
    var p = String(location.pathname || '').replace(/\/+$/, '') || '/';
    var m = p.match(/^\/flow\/detail\/(\d+)$/);
    if (m) {
      mountFlowFab(m[1]);
    } else {
      unmountFab();
    }
    // 评审过程抽屉已打开时，切走就关掉
    if (!m && !LIST_PAGES.test(p) && !/^\/docs\/\d+$/.test(p) && document.getElementById(DRAWER_ID)) closeDrawer();

    // 只在这些「查询列表」页挂行内按钮；文件详情页已有评审进度面板，不重复
    if (LIST_PAGES.test(p) && !/^\/docs\/\d+$/.test(p)) {
      mountRowButtons();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(run, 700); });
  } else {
    setTimeout(run, 700);
  }
  setInterval(run, 900);

  window.OADocReview = { openInstance: openFlow, openDoc: openDoc, close: closeDrawer };
})();
