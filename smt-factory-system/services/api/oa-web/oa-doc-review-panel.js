/* ==========================================================================
   体系文件 · 评审环节面板（oa-doc-review-panel.js）
   --------------------------------------------------------------------------
   解决两个问题（用户 2026-10-27 反馈）：
     ① 新建/详情页看不到「提交以后要经过哪些评审节点」；
     ② 节点写死在流程定义里，发起人不能选；而且第 2 步「四部门会签」与
        第 3 步「部门负责人审核」审批人是同一批人，重复审批。

   行为：
     · /docs/new         → 只读预览（创建后才谈得上选择）
     · /docs/<id> 草稿   → 「评审环节」可编辑：逐环节勾选/跳过、逐人移出/加人、
                           一键去重、恢复默认；选择随提交一起发给后端，
                           由后端固化成 flow_instance.nodes_override（迁移 104）。
     · /docs/<id> 已提交 → 真实逐节点进度（状态/审批人/意见/时间）+ 提交时被跳过的环节

   实现：纯 DOM 注入，不改前端 bundle（dist 里是压缩后的 Vue chunk）。
        数据来自 /api/docs/review-chain?docId=、/api/docs/:id/review-nodes。
        选择通过「提交受控发行」请求体注入（窄范围拦截 XHR/fetch），
        拦截失败也不影响提交（退回流程定义默认链）。
   卸载：删除本文件 + 移除 index.html 中 <script> 即可，无副作用。
   ========================================================================== */
(function () {
  'use strict';

  var PANEL_ID = 'oa-doc-review-panel';
  var STYLE_ID = 'oa-doc-review-style';
  var LS_PREFIX = 'oa_doc_rev_sel_v1_';

  var T = {
    zh: {
      titleNew: '评审流程',
      titleSelect: '评审环节',
      titleDetail: '评审进度',
      subNew: '提交评审后依次经过 {n} 个节点（其中 {m} 个本次适用）',
      subSelect: '共 {n} 个环节，本次选中 {m} 个',
      subDetail: '单据 {no} · 共 {n} 个节点',
      approvers: '审批人',
      none: '未匹配到审批人（需管理员指派）',
      expectApprovers: '预计审批人',
      joint: '会签：需 {n} 人通过',
      jointAll: '全员通过才流转（审批时可加签陪签人）',
      autoSkipSelf: '发起人本人即本节点审批人，提交后自动跳过',
      footNew: '创建后进入文件详情，点「提交受控发行」时可选/跳过评审环节。',
      footSelect: '选择只影响本次提交；提交后按所选环节流转，可在「流程详情」查看。',
      footDetail: '节点与审批人由流程引擎实时解析，与「流程详情」页一致。',
      notSubmitted: '尚未提交评审',
      viewFlow: '流程详情',
      refresh: '刷新',
      loading: '加载中…',
      error: '评审链路加载失败',
      retry: '重试',
      approved: '已通过',
      processing: '处理中',
      pending: '待处理',
      skipped: '已跳过',
      rejected: '已驳回',
      applicable: '适用',
      by: '由',
      empty: '暂无流程节点',
      comments: '意见',
      hintSelect: '勾选＝本次走这个环节；取消＝跳过。点审批人可把他移出/加回本环节。',
      dupTip: '第 {i} 步「{name}」的审批人已在第 {j} 步出现：{people}',
      dupTipFull: '第 {i} 步「{name}」与第 {j} 步审批人完全相同，建议跳过',
      dedupe: '一键去重',
      reset: '恢复默认',
      dupTag: '重复',
      dupTagTip: '已在第 {i} 步审批',
      addApprover: '添加审批人',
      searchPh: '姓名 / 工号',
      noResult: '无匹配人员',
      addedTag: '新增',
      removeTip: '点击移出本环节',
      restoreTip: '点击加回本环节',
      noPerson: '该环节无人可审，提交时会自动跳过',
      selEmpty: '请至少保留一个环节',
      notApplicable: '条件不适用，本次跳过',
      removedByChoice: '提交时已跳过：{names}',
      customized: '按自定义环节',
      saved: '选择已保存',
      back: '收起'
    },
    vi: {
      titleNew: 'Quy trình đánh giá',
      titleSelect: 'Bước đánh giá',
      titleDetail: 'Tiến độ đánh giá',
      subNew: 'Sau khi gửi, hồ sơ đi qua {n} bước (lần này áp dụng {m} bước)',
      subSelect: 'Tổng {n} bước, lần này chọn {m} bước',
      subDetail: 'Phiếu {no} · {n} bước',
      approvers: 'Người duyệt',
      none: 'Chưa tìm thấy người duyệt (cần quản trị chỉ định)',
      expectApprovers: 'Người duyệt dự kiến',
      joint: 'Đồng ký: cần {n} người duyệt',
      jointAll: 'Tất cả phải duyệt mới chuyển bước (có thể thêm người đồng ký khi duyệt)',
      autoSkipSelf: 'Người gửi chính là người duyệt bước này, sẽ tự động bỏ qua sau khi gửi',
      footNew: 'Sau khi tạo, vào chi tiết và bấm "Gửi phát hành có kiểm soát" để chọn bước đánh giá.',
      footSelect: 'Lựa chọn chỉ áp dụng cho lần gửi này; xem lại ở trang chi tiết quy trình.',
      footDetail: 'Các bước và người duyệt do hệ thống phân giải thời gian thực.',
      notSubmitted: 'Chưa gửi đánh giá',
      viewFlow: 'Chi tiết quy trình',
      refresh: 'Làm mới',
      loading: 'Đang tải…',
      error: 'Không tải được quy trình đánh giá',
      retry: 'Thử lại',
      approved: 'Đã duyệt',
      processing: 'Đang xử lý',
      pending: 'Chờ xử lý',
      skipped: 'Bỏ qua',
      rejected: 'Bị từ chối',
      applicable: 'Áp dụng',
      by: 'bởi',
      empty: 'Không có bước nào',
      comments: 'Ý kiến',
      hintSelect: 'Tích = lần này đi bước này; bỏ tích = bỏ qua. Bấm vào người duyệt để bỏ/thêm khỏi bước.',
      dupTip: 'Người duyệt của bước {i} "{name}" đã xuất hiện ở bước {j}: {people}',
      dupTipFull: 'Bước {i} "{name}" trùng hoàn toàn với bước {j}, nên bỏ qua',
      dedupe: 'Tự động bỏ trùng',
      reset: 'Khôi phục mặc định',
      dupTag: 'Trùng',
      dupTagTip: 'Đã duyệt ở bước {i}',
      addApprover: 'Thêm người duyệt',
      searchPh: 'Họ tên / mã NV',
      noResult: 'Không có kết quả',
      addedTag: 'Thêm',
      removeTip: 'Bấm để bỏ khỏi bước này',
      restoreTip: 'Bấm để thêm lại',
      noPerson: 'Bước này không có người duyệt, sẽ tự bỏ qua khi gửi',
      selEmpty: 'Giữ lại ít nhất một bước',
      notApplicable: 'Điều kiện không áp dụng, bỏ qua lần này',
      removedByChoice: 'Đã bỏ qua khi gửi: {names}',
      customized: 'Bước tùy chỉnh',
      saved: 'Đã lưu lựa chọn',
      back: 'Thu gọn'
    },
    en: {
      titleNew: 'Review flow',
      titleSelect: 'Review steps',
      titleDetail: 'Review progress',
      subNew: 'After submission the document passes {n} steps ({m} applicable this time)',
      subSelect: '{n} steps in total, {m} selected this time',
      subDetail: 'Instance {no} · {n} steps',
      approvers: 'Approvers',
      none: 'No approver resolved (admin must assign)',
      expectApprovers: 'Expected approvers',
      joint: 'Joint sign: {n} approvals required',
      jointAll: 'All approvers must sign before it moves on (add co-signers while approving)',
      autoSkipSelf: 'Applicant is the approver of this step; it is skipped automatically after submission',
      footNew: 'After creating, open the document and click "Submit for controlled issue" to pick review steps.',
      footSelect: 'The choice applies to this submission only; follow it up in the flow detail page.',
      footDetail: 'Steps and approvers are resolved live by the flow engine.',
      notSubmitted: 'Not submitted yet',
      viewFlow: 'Flow detail',
      refresh: 'Refresh',
      loading: 'Loading…',
      error: 'Failed to load review flow',
      retry: 'Retry',
      approved: 'Approved',
      processing: 'In progress',
      pending: 'Pending',
      skipped: 'Skipped',
      rejected: 'Rejected',
      applicable: 'Applicable',
      by: 'by',
      empty: 'No steps',
      comments: 'Comment',
      hintSelect: 'Tick = run this step; untick = skip. Click an approver to remove/add them for this step.',
      dupTip: 'Approvers of step {i} "{name}" already appeared in step {j}: {people}',
      dupTipFull: 'Step {i} "{name}" fully duplicates step {j}; consider skipping it',
      dedupe: 'Remove duplicates',
      reset: 'Reset to default',
      dupTag: 'Dup',
      dupTagTip: 'Already approved in step {i}',
      addApprover: 'Add approver',
      searchPh: 'Name / employee no.',
      noResult: 'No match',
      addedTag: 'Added',
      removeTip: 'Click to remove from this step',
      restoreTip: 'Click to add back',
      noPerson: 'No approver for this step; it will be skipped on submit',
      selEmpty: 'Keep at least one step',
      notApplicable: 'Condition not met, skipped this time',
      removedByChoice: 'Skipped on submit: {names}',
      customized: 'Custom steps',
      saved: 'Selection saved',
      back: 'Collapse'
    }
  };

  function lang() {
    var l = 'zh';
    try {
      l = (localStorage.getItem('oa_lang') || localStorage.getItem('oa-lang') ||
        document.documentElement.getAttribute('lang') || 'zh');
    } catch (e) { }
    l = String(l || 'zh').toLowerCase();
    if (l.indexOf('vi') === 0) return 'vi';
    if (l.indexOf('en') === 0) return 'en';
    return 'zh';
  }

  function t(key, vars) {
    var d = T[lang()] || T.zh;
    var s = d[key] !== undefined ? d[key] : (T.zh[key] !== undefined ? T.zh[key] : key);
    if (vars) {
      Object.keys(vars).forEach(function (k) {
        s = s.split('{' + k + '}').join(String(vars[k]));
      });
    }
    return s;
  }

  function nodeName(n) {
    if (lang() === 'vi' && n.nameVi) return n.nameVi;
    return n.name || '';
  }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function token() {
    try { return localStorage.getItem('oa_token') || ''; } catch (e) { return ''; }
  }

  function req(path, opts) {
    var o = opts || {};
    var headers = {
      'Authorization': 'Bearer ' + token(),
      'X-OA-Lang': lang(),
      'Accept': 'application/json'
    };
    if (o.body !== undefined) headers['Content-Type'] = 'application/json';
    return fetch(path, {
      method: o.method || 'GET',
      headers: headers,
      body: o.body === undefined ? undefined : JSON.stringify(o.body)
    }).then(function (r) {
      return r.json().catch(function () { return null; });
    }).then(function (b) {
      if (!b || b.code !== 0) throw new Error((b && b.msg) || 'HTTP');
      return b.data;
    });
  }

  function api(path) { return req(path); }

  // ---------------------------------------------------------------- 样式
  var CSS = [
    '#' + PANEL_ID + '{background:var(--oa-card);border:1px solid var(--oa-border);border-radius:var(--oa-radius,8px);',
    'box-shadow:var(--oa-shadow);margin-bottom:12px;overflow:hidden;font-size:13px;color:var(--oa-text)}',
    '#' + PANEL_ID + ' .odrp-head{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 14px;',
    'border-bottom:1px solid var(--oa-border);background:var(--oa-table-head)}',
    '#' + PANEL_ID + ' .odrp-title{font-weight:600;font-size:14px}',
    '#' + PANEL_ID + ' .odrp-sub{color:var(--oa-text-light);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-spacer{flex:1 1 auto}',
    '#' + PANEL_ID + ' .odrp-badge{font-size:12px;padding:1px 8px;border-radius:10px;border:1px solid var(--oa-border);',
    'color:var(--oa-text-sub);background:var(--oa-bg)}',
    '#' + PANEL_ID + ' .odrp-badge.is-run{color:var(--oa-primary);border-color:var(--oa-primary);background:transparent}',
    '#' + PANEL_ID + ' .odrp-badge.is-done{color:var(--oa-success);border-color:var(--oa-success);background:transparent}',
    '#' + PANEL_ID + ' .odrp-badge.is-bad{color:var(--oa-danger);border-color:var(--oa-danger);background:transparent}',
    '#' + PANEL_ID + ' .odrp-badge.is-warn{color:var(--oa-warning);border-color:var(--oa-warning);background:transparent}',
    '#' + PANEL_ID + ' .odrp-btn{border:1px solid var(--oa-border);background:var(--oa-card);color:var(--oa-text-sub);',
    'border-radius:var(--oa-radius-sm,4px);padding:2px 10px;font-size:12px;cursor:pointer;line-height:18px}',
    '#' + PANEL_ID + ' .odrp-btn:hover{border-color:var(--oa-primary);color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-btn.is-primary{border-color:var(--oa-primary);color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-body{padding:12px 14px 4px}',
    '#' + PANEL_ID + ' .odrp-hint{padding:8px 14px;color:var(--oa-text-light);font-size:12px;border-bottom:1px dashed var(--oa-border)}',
    '#' + PANEL_ID + ' .odrp-tip{margin:10px 14px 0;padding:8px 10px;border-radius:4px;font-size:12px;line-height:1.7;',
    'color:var(--oa-warning-text,var(--oa-text));background:var(--oa-warning-bg,rgba(230,162,60,.10));',
    'border:1px solid var(--oa-warning-border,rgba(230,162,60,.35))}',
    '#' + PANEL_ID + ' .odrp-tip b{font-weight:600}',
    '#' + PANEL_ID + ' .odrp-tip .odrp-btn{margin-left:6px;background:transparent}',
    '#' + PANEL_ID + ' .odrp-node{display:flex;gap:10px;position:relative;padding-bottom:12px}',
    '#' + PANEL_ID + ' .odrp-node:last-child{padding-bottom:4px}',
    '#' + PANEL_ID + ' .odrp-rail{width:22px;flex:0 0 22px;display:flex;flex-direction:column;align-items:center}',
    '#' + PANEL_ID + ' .odrp-dot{width:22px;height:22px;border-radius:50%;border:1px solid var(--oa-border);',
    'background:var(--oa-bg);color:var(--oa-text-light);font-size:12px;line-height:20px;text-align:center;flex:0 0 22px}',
    '#' + PANEL_ID + ' .odrp-node:not(:last-child) .odrp-rail:after{content:"";flex:1 1 auto;width:1px;',
    'background:var(--oa-border);margin-top:2px}',
    '#' + PANEL_ID + ' .odrp-main{flex:1 1 auto;min-width:0;padding-top:1px}',
    '#' + PANEL_ID + ' .odrp-line{display:flex;align-items:center;flex-wrap:wrap;gap:8px}',
    '#' + PANEL_ID + ' .odrp-name{font-weight:500}',
    '#' + PANEL_ID + ' .odrp-vi{color:var(--oa-text-light);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-people{margin-top:4px;color:var(--oa-text-sub);font-size:12px;line-height:1.9}',
    '#' + PANEL_ID + ' .odrp-person{display:inline-block;margin:0 6px 2px 0;padding:0 7px;border-radius:10px;',
    'background:var(--oa-table-head);color:var(--oa-text);border:1px solid transparent}',
    '#' + PANEL_ID + ' .odrp-person.odrp-chip{cursor:pointer;user-select:none}',
    '#' + PANEL_ID + ' .odrp-person.odrp-chip:hover{border-color:var(--oa-border)}',
    '#' + PANEL_ID + ' .odrp-person.is-off{opacity:.55;text-decoration:line-through;background:transparent;',
    'border-style:dashed;border-color:var(--oa-border)}',
    '#' + PANEL_ID + ' .odrp-person.is-added{background:transparent;border-color:var(--oa-primary);color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-person.is-dup{border-color:var(--oa-warning-border,rgba(230,162,60,.5))}',
    '#' + PANEL_ID + ' .odrp-x{font-style:normal;margin-left:2px;opacity:.65;font-size:11px}',
    '#' + PANEL_ID + ' .odrp-meta{margin-top:3px;color:var(--oa-text-light);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-tag{font-size:11px;padding:0 6px;border-radius:9px;border:1px solid currentColor;line-height:16px}',
    '#' + PANEL_ID + ' .odrp-tag.is-approved{color:var(--oa-success)}',
    '#' + PANEL_ID + ' .odrp-tag.is-processing{color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-tag.is-pending{color:var(--oa-text-light)}',
    '#' + PANEL_ID + ' .odrp-tag.is-skipped{color:var(--oa-text-light);border-style:dashed}',
    '#' + PANEL_ID + ' .odrp-tag.is-rejected{color:var(--oa-danger)}',
    '#' + PANEL_ID + ' .odrp-tag.is-dup{color:var(--oa-warning);border-style:solid}',
    '#' + PANEL_ID + ' .odrp-tag.is-added{color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-tag.is-off{color:var(--oa-text-light);border-style:dashed}',
    '#' + PANEL_ID + ' .odrp-cond{font-size:11px;color:var(--oa-warning);border:1px dashed var(--oa-warning-border,rgba(230,162,60,.5));',
    'padding:0 6px;border-radius:9px;line-height:16px}',
    '#' + PANEL_ID + ' .odrp-joint{font-size:11px;color:var(--oa-info);border:1px solid var(--oa-info);',
    'padding:0 6px;border-radius:9px;line-height:16px}',
    '#' + PANEL_ID + ' .is-approved .odrp-dot{background:var(--oa-success);border-color:var(--oa-success);color:#fff}',
    '#' + PANEL_ID + ' .is-processing .odrp-dot{background:var(--oa-primary);border-color:var(--oa-primary);color:#fff}',
    '#' + PANEL_ID + ' .is-rejected .odrp-dot{background:var(--oa-danger);border-color:var(--oa-danger);color:#fff}',
    '#' + PANEL_ID + ' .is-skipped{opacity:.55}',
    '#' + PANEL_ID + ' .is-skipped .odrp-dot{border-style:dashed}',
    '#' + PANEL_ID + ' .is-current .odrp-name{color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .is-off .odrp-dot{border-style:dashed}',
    '#' + PANEL_ID + ' .is-off .odrp-name{color:var(--oa-text-light)}',
    '#' + PANEL_ID + ' .odrp-node.is-off .odrp-people{opacity:.55}',
    /* 勾选框 */
    '#' + PANEL_ID + ' .odrp-chk{display:inline-flex;align-items:center;cursor:pointer;position:relative}',
    '#' + PANEL_ID + ' .odrp-chk input{position:absolute;opacity:0;width:0;height:0}',
    '#' + PANEL_ID + ' .odrp-box{width:14px;height:14px;border:1px solid var(--oa-border);border-radius:3px;',
    'background:var(--oa-card);display:inline-block;position:relative;transition:background .15s}',
    '#' + PANEL_ID + ' .odrp-chk input:checked + .odrp-box{background:var(--oa-primary);border-color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-chk input:checked + .odrp-box:after{content:"";position:absolute;left:4px;top:0;',
    'width:4px;height:8px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(42deg)}',
    '#' + PANEL_ID + ' .odrp-chk input:disabled + .odrp-box{background:var(--oa-bg);opacity:.45;cursor:not-allowed}',
    /* 加大/删除人 */
    '#' + PANEL_ID + ' .odrp-nodeops{margin-top:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}',
    '#' + PANEL_ID + ' .odrp-mini{border:none;background:transparent;color:var(--oa-primary);font-size:12px;',
    'cursor:pointer;padding:0}',
    '#' + PANEL_ID + ' .odrp-mini:hover{text-decoration:underline}',
    '#' + PANEL_ID + ' .odrp-warn{color:var(--oa-danger);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-picker{margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}',
    '#' + PANEL_ID + ' .odrp-picker input{height:26px;padding:0 8px;font-size:12px;border:1px solid var(--oa-border);',
    'border-radius:4px;background:var(--oa-card);color:var(--oa-text);outline:none;width:170px}',
    '#' + PANEL_ID + ' .odrp-picker input:focus{border-color:var(--oa-primary)}',
    '#' + PANEL_ID + ' .odrp-result{display:flex;flex-wrap:wrap;gap:6px}',
    '#' + PANEL_ID + ' .odrp-result .odrp-person{cursor:pointer}',
    '#' + PANEL_ID + ' .odrp-foot{padding:8px 14px;border-top:1px dashed var(--oa-border);color:var(--oa-text-light);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-msg{padding:14px;color:var(--oa-text-light);font-size:12px}',
    '#' + PANEL_ID + ' .odrp-link{color:var(--oa-primary);text-decoration:none}',
    '#' + PANEL_ID + ' .odrp-link:hover{text-decoration:underline}',
    '@media print{#' + PANEL_ID + '{display:none!important}}'
  ].join('');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var st = document.createElement('style');
    st.id = STYLE_ID;
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // ---------------------------------------------------------------- 选择状态
  var ST = {
    docId: null,
    data: null,      // review-chain 返回
    sel: {},         // index -> bool
    removed: {},     // index -> [uid]
    added: {},       // index -> [uid]
    addedInfo: {},   // uid -> {id,name,dept,position}
    picker: null,    // 展开「添加审批人」的节点下标
    query: '',       // 搜索关键字
    results: [],     // 搜索结果
    lock: false
  };

  function lsKey(id) { return LS_PREFIX + id; }

  function loadSel(id) {
    try {
      var raw = localStorage.getItem(lsKey(id));
      if (!raw) return null;
      var o = JSON.parse(raw);
      if (!o || typeof o !== 'object') return null;
      return o;
    } catch (e) { return null; }
  }

  function saveSel() {
    if (!ST.docId) return;
    try {
      localStorage.setItem(lsKey(ST.docId), JSON.stringify({
        sel: ST.sel, removed: ST.removed, added: ST.added, addedInfo: ST.addedInfo
      }));
    } catch (e) { }
  }

  function resetSel(keepData) {
    ST.sel = {}; ST.removed = {}; ST.added = {}; ST.addedInfo = {};
    ST.picker = null; ST.query = ''; ST.results = [];
    if (ST.data) {
      (ST.data.nodes || []).forEach(function (n) { ST.sel[n.index] = n.applies !== false; });
    }
    if (!keepData) saveSel();
  }

  function applySaved(saved) {
    if (!saved) return;
    if (saved.sel && typeof saved.sel === 'object') ST.sel = saved.sel;
    if (saved.removed && typeof saved.removed === 'object') ST.removed = saved.removed;
    if (saved.added && typeof saved.added === 'object') ST.added = saved.added;
    if (saved.addedInfo && typeof saved.addedInfo === 'object') ST.addedInfo = saved.addedInfo;
  }

  function removedOf(i) { return (ST.removed[i] || []).map(Number); }
  function addedOf(i) { return (ST.added[i] || []).map(Number); }

  function baseIds(n) { return (n.assignees || []).map(function (p) { return Number(p.id); }); }

  /** 本环节最终审批人（已考虑移出/新增） */
  function activeIds(n) {
    if (!ST.sel[n.index]) return [];
    var ids = baseIds(n).filter(function (id) { return removedOf(n.index).indexOf(id) === -1; });
    addedOf(n.index).forEach(function (id) { if (ids.indexOf(id) === -1) ids.push(id); });
    return ids;
  }

  function personOf(n, id) {
    var p = (n.assignees || []).filter(function (x) { return Number(x.id) === Number(id); })[0];
    if (p) return p;
    return ST.addedInfo[String(id)] || { id: Number(id), name: '#' + id };
  }

  // ---------------------------------------------------------------- 渲染
  function headHtml(o) {
    var badge = '';
    if (o.badge) badge = '<span class="odrp-badge ' + (o.badgeClass || '') + '">' + esc(o.badge) + '</span>';
    return '<div class="odrp-head">' +
      '<span class="odrp-title">' + esc(o.title) + '</span>' +
      badge +
      '<span class="odrp-spacer"></span>' +
      (o.sub ? '<span class="odrp-sub">' + esc(o.sub) + '</span>' : '') +
      (o.showRefresh ? '<button type="button" class="odrp-btn" data-odrp="refresh">' + esc(t('refresh')) + '</button>' : '') +
      '</div>';
  }

  function peopleHtml(node, progressMode) {
    if (node.applies === false) return '';
    var labels = (node.assignLabels || []).map(function (x) { return x[lang()] || x.zh; });
    // 发起人本人即该节点唯一审批人：提交后由引擎自动跳过，不能显示成「未匹配到审批人」
    if (node.autoSkipSelf && !(node.approvers || []).length) {
      return '<div class="odrp-people"><span class="odrp-vi">' + esc(t('autoSkipSelf')) + '</span></div>';
    }
    if (progressMode) {
      var parts = [];
      (node.approvers || []).forEach(function (p) {
        var st = p.status === 'approved' ? t('approved') : p.status === 'rejected' ? t('rejected') : t('pending');
        var meta = [];
        if (p.dept) meta.push(p.dept);
        if (p.position) meta.push(p.position);
        parts.push('<span class="odrp-person">' + esc(p.name) +
          (meta.length ? '<span class="odrp-vi">（' + esc(meta.join(' / ')) + '）</span>' : '') +
          ' · ' + esc(st) + '</span>' +
          (p.comment ? '<span class="odrp-meta">' + esc(t('comments')) + '：' + esc(p.comment) + '</span>' : ''));
      });
      if (parts.length) return '<div class="odrp-people">' + esc(t('approvers')) + '：' + parts.join('') + '</div>';
      if (node.status === 'pending' && labels.length) {
        return '<div class="odrp-people">' + esc(t('expectApprovers')) + '：<span class="odrp-vi">' +
          esc(labels.join(' / ')) + '</span></div>';
      }
      return '<div class="odrp-people">' + esc(t('approvers')) + '：<span class="odrp-vi">' + esc(t('none')) + '</span></div>';
    }

    // 选择态：可点的人名胶囊
    if (ST.data && ST.docId && node.applies !== false) {
      var chips = [];
      var removed = removedOf(node.index);
      (node.assignees || []).forEach(function (p) {
        var off = removed.indexOf(Number(p.id)) > -1;
        var dup = (node.dupIds || []).indexOf(Number(p.id)) > -1;
        var dupAt = dup ? ((node.coveredBy || [])[0] + 1) : null;
        var tip = off ? t('restoreTip') : (dup ? t('dupTagTip', { i: dupAt }) : t('removeTip'));
        chips.push('<span class="odrp-person odrp-chip' + (off ? ' is-off' : '') + (dup && !off ? ' is-dup' : '') + '"' +
          ' data-odrp="person" data-i="' + node.index + '" data-uid="' + p.id + '" title="' + esc(tip) + '">' +
          esc(p.name) + '<i class="odrp-x">' + (off ? '＋' : '×') + '</i></span>');
      });
      addedOf(node.index).forEach(function (id) {
        var p = personOf(node, id);
        chips.push('<span class="odrp-person odrp-chip is-added" data-odrp="person" data-i="' + node.index +
          '" data-uid="' + id + '" data-added="1" title="' + esc(t('removeTip')) + '">' +
          esc(p.name) + '<i class="odrp-x">×</i></span>');
      });
      if (!chips.length) {
        return '<div class="odrp-people">' + esc(t('approvers')) + '：<span class="odrp-vi">' +
          esc(labels.length ? labels.join(' / ') + ' · ' + t('none') : t('none')) + '</span></div>';
      }
      return '<div class="odrp-people">' + esc(t('approvers')) + '：' + chips.join('') +
        (labels.length ? '<span class="odrp-vi">· ' + esc(labels.join(' / ')) + '</span>' : '') + '</div>';
    }

    var pl = (node.assignees || []).map(function (p) {
      var meta = [];
      if (p.dept) meta.push(p.dept);
      if (p.position) meta.push(p.position);
      return '<span class="odrp-person">' + esc(p.name) +
        (meta.length ? '<span class="odrp-vi">（' + esc(meta.join(' / ')) + '）</span>' : '') + '</span>';
    });
    if (!pl.length) {
      return '<div class="odrp-people">' + esc(t('approvers')) + '：<span class="odrp-vi">' +
        esc(labels.length ? labels.join(' / ') + ' · ' + t('none') : t('none')) + '</span></div>';
    }
    return '<div class="odrp-people">' + esc(t('approvers')) + '：' + pl.join('') +
      (labels.length ? '<span class="odrp-vi">· ' + esc(labels.join(' / ')) + '</span>' : '') + '</div>';
  }

  function pickerHtml(node) {
    if (ST.picker !== node.index) return '';
    var res = (ST.results || []).filter(function (u) {
      return activeIds(node).indexOf(Number(u.id)) === -1;
    }).slice(0, 8).map(function (u) {
      return '<span class="odrp-person odrp-chip" data-odrp="pick" data-i="' + node.index + '" data-uid="' + u.id + '">' +
        esc(u.real_name || u.name) +
        (u.dept_name || u.dept ? '<span class="odrp-vi">（' + esc(u.dept_name || u.dept) + '）</span>' : '') + '</span>';
    });
    if (!res.length && ST.query) res = ['<span class="odrp-vi">' + esc(t('noResult')) + '</span>'];
    return '<div class="odrp-picker">' +
      '<input type="text" data-odrp="q" data-i="' + node.index + '" placeholder="' + esc(t('searchPh')) +
      '" value="' + esc(ST.query) + '">' +
      '<span class="odrp-result">' + res.join('') + '</span>' +
      '<button type="button" class="odrp-mini" data-odrp="closePick">' + esc(t('back')) + '</button>' +
      '</div>';
  }

  function nodeHtml(node, i, progressMode) {
    var cls = 'odrp-node';
    if (progressMode) {
      cls += ' is-' + node.status;
      if (node.isCurrent) cls += ' is-current';
    } else if (node.applies === false) {
      cls += ' is-skipped';
    } else if (ST.data && !ST.sel[node.index]) {
      cls += ' is-off';
    }

    var tags = [];
    if (progressMode) {
      tags.push('<span class="odrp-tag is-' + node.status + '">' + esc(t(node.status)) + '</span>');
    } else if (node.applies === false) {
      tags.push('<span class="odrp-tag is-skipped">' + esc(t('skipped')) + '</span>');
    } else if (ST.data && !ST.sel[node.index]) {
      tags.push('<span class="odrp-tag is-off" data-odrp="toggle" data-i="' + node.index + '">' + esc(t('skipped')) + '</span>');
    }
    if (node.conditional && node.conditionLabel) {
      tags.push('<span class="odrp-cond">' + esc(node.conditionLabel[lang()] || node.conditionLabel.zh) + '</span>');
    }
    if (node.minApprovals) {
      var cap = ST.data ? Math.min(node.minApprovals, Math.max(activeIds(node).length, 0)) : node.minApprovals;
      if (cap > 0) tags.push('<span class="odrp-joint">' + esc(t('joint', { n: cap })) + '</span>');
    }
    if (node.requireAllApprovals && node.applies !== false) {
      tags.push('<span class="odrp-joint">' + esc(t('jointAll')) + '</span>');
    }

    var chk = '';
    if (ST.data) {
      chk = '<label class="odrp-chk" title="' + esc(node.applies === false ? t('notApplicable') : t('hintSelect')) + '">' +
        '<input type="checkbox" data-odrp="node" data-i="' + node.index + '"' +
        (ST.sel[node.index] ? ' checked' : '') + (node.applies === false ? ' disabled' : '') + '>' +
        '<span class="odrp-box"></span></label>';
    }

    var ops = '';
    if (ST.data) {
      if (node.applies !== false && ST.sel[node.index]) {
        var empty = activeIds(node).length === 0;
        ops = '<div class="odrp-nodeops">' +
          '<button type="button" class="odrp-mini" data-odrp="add" data-i="' + node.index + '">＋ ' + esc(t('addApprover')) + '</button>' +
          (empty ? '<span class="odrp-warn">' + esc(t('noPerson')) + '</span>' : '') +
          '</div>';
      }
      // 条件不适用 / 被跳过：给一句原因，避免误以为是漏配

    }

    return '<div class="' + cls + '">' +
      '<div class="odrp-rail"><span class="odrp-dot">' + (i + 1) + '</span></div>' +
      '<div class="odrp-main">' +
      '<div class="odrp-line">' + chk +
      '<span class="odrp-name">' + esc(nodeName(node)) + '</span>' +
      (lang() !== 'vi' && node.nameVi ? '<span class="odrp-vi">' + esc(node.nameVi) + '</span>' : '') +
      tags.join('') + '</div>' +
      peopleHtml(node, progressMode) +
      ops + pickerHtml(node) +
      '</div></div>';
  }

  function dupTipHtml() {
    if (!ST.data || !ST.data.nodes) return '';
    // 只看「当前仍然留在本环节」的重复人：去重或手动移出后提示应自动消失
    function dupNow(n) {
      var act = activeIds(n);
      return (n.dupIds || []).filter(function (id) { return act.indexOf(Number(id)) > -1; });
    }
    var items = ST.data.nodes.filter(function (n) {
      return n.applies !== false && ST.sel[n.index] && dupNow(n).length;
    });
    if (!items.length) return '';
    var parts = items.map(function (n) {
      var dupIds = dupNow(n);
      var people = (n.assignees || [])
        .filter(function (p) { return dupIds.indexOf(Number(p.id)) > -1; })
        .map(function (p) { return p.name; }).join('、');
      var at = (n.coveredBy || [])[0] + 1;
      var key = dupIds.length === activeIds(n).length ? 'dupTipFull' : 'dupTip';
      return esc(t(key, { i: n.index + 1, name: nodeName(n), j: at, people: people }));
    });
    return '<div class="odrp-tip">' + parts.join('<br>') +
      '<button type="button" class="odrp-btn is-primary" data-odrp="dedupe">' + esc(t('dedupe')) + '</button>' +
      '<button type="button" class="odrp-btn" data-odrp="reset">' + esc(t('reset')) + '</button></div>';
  }

  function build(o) {
    var el = document.getElementById(PANEL_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = PANEL_ID;
      el.setAttribute('data-odrp-kind', o.kind);
    }
    var body;
    if (o.error) {
      body = '<div class="odrp-msg">' + esc(t('error')) + ' · <a href="javascript:void(0)" data-odrp="refresh">' + esc(t('retry')) + '</a></div>';
    } else if (!o.nodes || !o.nodes.length) {
      body = '<div class="odrp-msg">' + esc(o.loading ? t('loading') : t('empty')) + '</div>';
    } else {
      body = '<div class="odrp-body">' + o.nodes.map(function (n, i) { return nodeHtml(n, i, o.progressMode); }).join('') + '</div>';
    }
    var foot = '';
    if (o.footHtml) foot = '<div class="odrp-foot">' + o.footHtml + '</div>';
    else if (o.foot) foot = '<div class="odrp-foot">' + esc(o.foot) + '</div>';
    el.setAttribute('data-odrp-state', (o.progressMode && o.nodes && o.nodes.length) ? 'ready' : (o.error ? 'error' : 'preview'));
    el.setAttribute('data-odrp-mode', o.selectable ? 'select' : 'read');
    el.innerHTML = headHtml(o) + (o.selectable ? '<div class="odrp-hint">' + esc(t('hintSelect')) + '</div>' : '') +
      (o.selectable ? dupTipHtml() : '') + body + foot;
    return el;
  }

  // ---------------------------------------------------------------- 挂载
  function anchor() {
    var head = document.querySelector('.oa-page-head') || document.querySelector('.oa-page-header');
    if (head && head.parentNode) return { parent: head.parentNode, after: head };
    var card = document.querySelector('.oa-card');
    if (card && card.parentNode) return { parent: card.parentNode, after: null, before: card };
    var bar = document.querySelector('.oa-action-bar');
    if (bar && bar.parentNode) return { parent: bar.parentNode, before: bar };
    return null;
  }

  function place(el) {
    var a = anchor();
    if (!a) return false;
    if (el.parentNode === a.parent && el.previousSibling === a.after) return true;
    if (a.after) a.parent.insertBefore(el, a.after.nextSibling);
    else a.parent.insertBefore(el, a.before);
    return true;
  }

  function isNewPage(path) {
    return /^\/docs\/new\/?$/.test(path);
  }

  function detailId(path) {
    var m = /^\/docs\/(\d+)\/?$/.exec(path);
    return m ? m[1] : null;
  }

  function readLevel() {
    var boxes = document.querySelectorAll('.el-radio-button');
    for (var i = 0; i < boxes.length; i++) {
      var b = boxes[i];
      if (!/(^|\s)is-active(\s|$)/.test(b.className)) continue;
      var txt = (b.textContent || '').trim();
      if (txt.indexOf('一级') > -1) return 1;
      if (txt.indexOf('二级') > -1) return 2;
      if (txt.indexOf('三级') > -1) return 3;
      if (txt.indexOf('四级') > -1) return 4;
    }
    return null;
  }

  var reqSeq = 0;

  function replacePanel(el) {
    var old = document.getElementById(PANEL_ID);
    if (old && old.parentNode && old !== el) old.parentNode.replaceChild(el, old);
    else place(el);
  }

  function renderNew(container) {
    var seq = ++reqSeq;
    var lv = readLevel();
    var q = '/api/docs/review-chain' + (lv ? '?level=' + lv : '');
    place(build({
      kind: 'new', title: t('titleNew'), sub: '', showRefresh: true,
      loading: true, nodes: null, foot: t('footNew')
    }));
    api(q).then(function (d) {
      if (seq !== reqSeq) return;
      if (!d || !d.nodes) return;
      replacePanel(build({
        kind: 'new',
        title: t('titleNew'),
        sub: t('subNew', { n: d.total, m: d.applicableCount }),
        showRefresh: true,
        nodes: d.nodes,
        foot: t('footNew')
      }));
    }).catch(function () {
      if (seq !== reqSeq) return;
      replacePanel(build({ kind: 'new', title: t('titleNew'), error: true, showRefresh: true, nodes: null }));
    });
  }

  function statusBadge(p) {
    if (!p) return { text: t('notSubmitted'), cls: '' };
    var s = String(p.status || '');
    if (s === 'completed' || s === 'approved') return { text: t('approved'), cls: 'is-done' };
    if (s === 'rejected') return { text: t('rejected'), cls: 'is-bad' };
    if (s === 'terminated' || s === 'withdrawn') return { text: s === 'withdrawn' ? t('skipped') : t('rejected'), cls: '' };
    return { text: t('processing'), cls: 'is-run' };
  }

  function renderProgress(p) {
    var b = statusBadge(p);
    var removed = (p.removedNodes || []).map(function (n) {
      return lang() === 'vi' && n.nameVi ? n.nameVi : n.name;
    });
    var foot = esc(t('footDetail')) + ' <a class="odrp-link" href="/flow/detail/' + p.instanceId + '">' +
      esc(t('viewFlow')) + ' →</a>';
    if (removed.length) foot += '<br>' + esc(t('removedByChoice', { names: removed.join('、') }));
    replacePanel(build({
      kind: 'detail',
      title: t('titleDetail'),
      sub: t('subDetail', { no: p.instanceNo || p.instanceId, n: p.total }),
      badge: b.text, badgeClass: b.cls,
      showRefresh: true,
      nodes: p.nodes,
      progressMode: true,
      footHtml: foot
    }));
  }

  function renderSelect(d, doc) {
    ST.docId = Number(d.docId || (doc && doc.id)) || ST.docId;
    ST.data = d;
    var saved = loadSel(ST.docId);
    resetSel(true);            // 先按默认（全部适用环节）
    applySaved(saved);         // 再叠加用户上次的选择
    // 兜底：已经把文件提交了（实例在跑）就不能再改
    var selectedCount = (d.nodes || []).filter(function (n) { return ST.sel[n.index]; }).length;
    replacePanel(build({
      kind: 'detail',
      title: t('titleSelect'),
      sub: t('subSelect', { n: d.applicableCount, m: selectedCount }),
      badge: t('notSubmitted'),
      showRefresh: true,
      selectable: true,
      nodes: d.nodes,
      foot: t('footSelect')
    }));
  }

  function renderDetail(docId) {
    var seq = ++reqSeq;
    place(build({
      kind: 'detail', title: t('titleDetail'), showRefresh: true,
      loading: true, nodes: null, foot: t('footDetail')
    }));
    api('/api/docs/' + docId + '/review-nodes').then(function (p) {
      if (seq !== reqSeq) return null;
      if (p && p.nodes && p.nodes.length) {
        // 已有实例 → 只读进度；顺手清掉本地残留选择（下次发起重新选）
        try { localStorage.removeItem(lsKey(docId)); } catch (e) { }
        ST.data = null; ST.docId = null;
        renderProgress(p);
        return null;
      }
      // 无实例 → 预览；草稿态可编辑选择
      return Promise.all([
        api('/api/docs/' + docId),
        api('/api/docs/review-chain?docId=' + docId)
      ]).then(function (arr) {
        if (seq !== reqSeq) return;
        var doc = arr[0], d = arr[1];
        if (!d || !d.nodes) return;
        ST.docId = Number(docId);
        if (doc && doc.status === 'draft') {
          renderSelect(d, doc);
        } else {
          ST.data = null;
          replacePanel(build({
            kind: 'detail',
            title: t('titleNew'),
            sub: t('subNew', { n: d.total, m: d.applicableCount }),
            badge: t('notSubmitted'),
            showRefresh: true,
            nodes: d.nodes,
            foot: t('footNew')
          }));
        }
      });
    }).catch(function () {
      if (seq !== reqSeq) return;
      replacePanel(build({ kind: 'detail', title: t('titleDetail'), error: true, showRefresh: true, nodes: null }));
    });
  }

  /** 选择变化 → 就地重绘（不重新请求，避免丢焦点） */
  function rerender() {
    if (!ST.data) return;
    var nodes = ST.data.nodes || [];
    var selectedCount = nodes.filter(function (n) { return ST.sel[n.index]; }).length;
    var el = build({
      kind: 'detail',
      title: t('titleSelect'),
      sub: t('subSelect', { n: ST.data.applicableCount, m: selectedCount }),
      badge: t('notSubmitted'),
      showRefresh: true,
      selectable: true,
      nodes: nodes,
      foot: t('footSelect')
    });
    replacePanel(el);
    // 搜索框保持焦点
    if (ST.picker !== null) {
      var input = document.querySelector('#' + PANEL_ID + ' [data-odrp="q"]');
      if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
    }
  }

  // ---------------------------------------------------------------- 交互
  function toggleNode(i, on) {
    var n = (ST.data.nodes || []).filter(function (x) { return x.index === i; })[0];
    if (!n || n.applies === false) return;
    var cur = (ST.data.nodes || []).filter(function (x) { return ST.sel[x.index] && x.applies !== false; });
    if (!on && cur.length <= 1) return;   // 至少留一个
    ST.sel[i] = !!on;
    saveSel();
    rerender();
  }

  function togglePerson(i, uid, isAdded) {
    var n = (ST.data.nodes || []).filter(function (x) { return x.index === i; })[0];
    if (!n) return;
    if (isAdded) {
      ST.added[i] = addedOf(i).filter(function (x) { return x !== uid; });
      delete ST.addedInfo[String(uid)];
    } else {
      var rm = removedOf(i);
      if (rm.indexOf(uid) > -1) {
        ST.removed[i] = rm.filter(function (x) { return x !== uid; });
      } else {
        rm.push(uid);
        // 不允许把本环节清空（清空＝该环节无人可审，应直接跳过整个环节）
        var left = baseIds(n).filter(function (x) { return rm.indexOf(x) === -1; }).concat(addedOf(i));
        if (!left.length) { toggleNode(i, false); return; }
        ST.removed[i] = rm;
      }
    }
    saveSel();
    rerender();
  }

  function autoDedupe() {
    var seen = {};
    (ST.data.nodes || []).forEach(function (n) {
      if (n.applies === false) return;
      // 只处理「审批」环节：发行执行/确认闭环是同一个人要做的动作，不是重复审批
      if ((n.type || 'approval') !== 'approval') return;
      if (!ST.sel[n.index]) return;              // 已跳过的不参与
      var ids = baseIds(n).filter(function (id) { return removedOf(n.index).indexOf(id) === -1; });
      var dup = ids.filter(function (id) { return seen[id] !== undefined; });
      if (dup.length === ids.length && dup.length) {
        ST.sel[n.index] = false;                 // 全重复 → 整个环节跳过
        return;
      }
      if (dup.length) {
        ST.removed[n.index] = removedOf(n.index).concat(dup);
      }
      ids.filter(function (id) { return seen[id] === undefined; }).forEach(function (id) { seen[id] = n.index; });
    });
    // 兜底：至少留一个
    var left = (ST.data.nodes || []).filter(function (n) { return ST.sel[n.index] && n.applies !== false; });
    if (!left.length) ST.sel[(ST.data.nodes || [])[0].index] = true;
    saveSel();
    rerender();
  }

  function searchUsers(i, kw) {
    ST.query = kw || '';
    if (!ST.query) { ST.results = []; rerender(); return; }
    var seq = ++reqSeq;
    req('/api/users?keyword=' + encodeURIComponent(ST.query)).then(function (list) {
      if (seq !== reqSeq) return;
      ST.results = Array.isArray(list) ? list : [];
      rerender();
    }).catch(function () { ST.results = []; rerender(); });
  }

  var qTimer = null;

  function onClick(e) {
    var panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    var hit = e.target && e.target.closest ? e.target.closest('[data-odrp]') : null;
    if (!hit || !panel.contains(hit)) return;
    var act = hit.getAttribute('data-odrp');
    var i = Number(hit.getAttribute('data-i'));

    if (act === 'refresh') {
      e.preventDefault();
      var path0 = location.pathname || '';
      if (isNewPage(path0)) renderNew();
      else { var id0 = detailId(path0); if (id0) renderDetail(id0); }
      return;
    }
    if (!ST.data) return;

    if (act === 'dedupe') { e.preventDefault(); autoDedupe(); return; }
    if (act === 'reset') { e.preventDefault(); resetSel(); rerender(); return; }
    if (act === 'toggle') { e.preventDefault(); toggleNode(i, !ST.sel[i]); return; }
    if (act === 'person') {
      e.preventDefault();
      togglePerson(i, Number(hit.getAttribute('data-uid')), hit.getAttribute('data-added') === '1');
      return;
    }
    if (act === 'add') {
      e.preventDefault();
      ST.picker = ST.picker === i ? null : i;
      ST.query = ''; ST.results = [];
      rerender();
      return;
    }
    if (act === 'closePick') { e.preventDefault(); ST.picker = null; ST.query = ''; ST.results = []; rerender(); return; }
    if (act === 'pick') {
      e.preventDefault();
      var uid = Number(hit.getAttribute('data-uid'));
      var name = (hit.textContent || '').split('（')[0].trim();
      ST.added[i] = addedOf(i).concat([uid]).filter(function (v, k, a) { return a.indexOf(v) === k; });
      ST.addedInfo[String(uid)] = { id: uid, name: name };
      saveSel();
      rerender();
      return;
    }
  }

  function onInput(e) {
    var el = e.target;
    if (!el || !el.getAttribute || el.getAttribute('data-odrp') !== 'q') return;
    var i = Number(el.getAttribute('data-i'));
    var v = el.value || '';
    ST.query = v;
    if (qTimer) clearTimeout(qTimer);
    qTimer = setTimeout(function () { searchUsers(i, v); }, 260);
  }

  function onChange(e) {
    var el = e.target;
    if (!el || !el.getAttribute || el.getAttribute('data-odrp') !== 'node') return;
    toggleNode(Number(el.getAttribute('data-i')), !!el.checked);
  }

  // ---------------------------------------------------------------- 提交注入
  // 「提交受控发行」按钮在压缩后的 Vue chunk 里，拿不到它的 payload。
  // 窄范围拦截：只对 POST /docs/<id>/submit-issue 追加 reviewNodes，
  // 其它请求原样放行；拦截异常一律吞掉（退回流程定义默认链，不阻断提交）。
  function submitPayload() {
    if (!ST.data || !ST.docId) return null;
    var selected = [];
    var removed = {};
    var added = {};
    (ST.data.nodes || []).forEach(function (n) {
      if (!ST.sel[n.index]) return;
      selected.push(n.index);
      if (removedOf(n.index).length) removed[n.index] = removedOf(n.index);
      if (addedOf(n.index).length) added[n.index] = addedOf(n.index);
    });
    if (!selected.length) return null;
    return { selected: selected, removed: removed, added: added };
  }

  function injectInto(body, url) {
    if (typeof body !== 'string' || !body) return body;
    if (!/\/docs\/\d+\/submit-issue(\?|$)/.test(String(url || ''))) return body;
    var p = submitPayload();
    if (!p) return body;
    try {
      var o = JSON.parse(body);
      if (o && typeof o === 'object' && !o.reviewNodes) {
        o.reviewNodes = p;
        return JSON.stringify(o);
      }
    } catch (e) { /* 非 JSON → 不处理 */ }
    return body;
  }

  function patchTransport() {
    try {
      if (window.XMLHttpRequest && !window.__odrpXhrPatched) {
        window.__odrpXhrPatched = true;
        var X = window.XMLHttpRequest;
        var open = X.prototype.open;
        var send = X.prototype.send;
        X.prototype.open = function (m, u) {
          try { this.__odrpUrl = u; } catch (e) { }
          return open.apply(this, arguments);
        };
        X.prototype.send = function (body) {
          try { body = injectInto(body, this.__odrpUrl); } catch (e) { }
          return send.call(this, body);
        };
      }
      if (window.fetch && !window.__odrpFetchPatched) {
        window.__odrpFetchPatched = true;
        var of = window.fetch;
        window.fetch = function (input, init) {
          try {
            var url = typeof input === 'string' ? input : (input && input.url) || '';
            if (init && init.body && typeof init.body === 'string' &&
              /\/docs\/\d+\/submit-issue(\?|$)/.test(url)) {
              init = Object.assign({}, init, { body: injectInto(init.body, url) });
            }
          } catch (e) { }
          return of.call(this, input, init);
        };
      }
    } catch (e) { }
  }

  // ---------------------------------------------------------------- 生命周期
  var currentKey = '';
  var lastLevel = null;
  var lastLang = null;

  function cleanup() {
    var el = document.getElementById(PANEL_ID);
    if (el && el.parentNode) el.parentNode.removeChild(el);
    toggleLegacy(false);
    ST.data = null; ST.docId = null; ST.picker = null; ST.results = []; ST.query = '';
  }

  /* 详情页原有一张「评审进度」卡片（6 个抽象步骤）。本面板给的是流程引擎的
     真实节点（含审批人/意见/被跳过的环节），数据 ready 后折叠旧卡避免重复；
     加载失败则保持旧卡可见，不擅自拿走用户已有信息。 */
  function legacyProgress() {
    var cards = document.querySelectorAll('.oa-card');
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      if (c.id === PANEL_ID) continue;
      if (!c.querySelector('.el-steps')) continue;
      var head = c.querySelector('.oa-card-head');
      var txt = (head ? head.textContent : c.textContent) || '';
      if (/废除|hủy|obsolete/i.test(txt)) continue;
      return c;
    }
    return null;
  }

  function toggleLegacy(hide) {
    var c = legacyProgress();
    if (!c) return;
    if (hide) {
      if (c.style.display !== 'none') c.style.display = 'none';
    } else if (c.style.display === 'none') {
      c.style.display = '';
    }
  }

  function sync() {
    var path = location.pathname || '';
    var key, kind = null, id = null;
    // 2026-10-30 用户要求：新建文件页不再展示「评审流程」预览（只在这里关，
    // 详情页仍保留：草稿可选环节、已提交可看真实进度）。
    if (isNewPage(path)) {
      if (currentKey) { cleanup(); currentKey = ''; }
      return;
    }
    if ((id = detailId(path))) { kind = 'detail'; key = 'doc:' + id; }
    if (!kind) {
      if (currentKey) { cleanup(); currentKey = ''; }
      return;
    }
    if (key !== currentKey || lang() !== lastLang) {
      currentKey = key;
      lastLang = lang();
      cleanup();
      ensureStyle();
      if (kind === 'new') { lastLevel = readLevel(); renderNew(); }
      else renderDetail(id);
      return;
    }
    // 同页：面板被 Vue 重渲染冲掉 → 重新挂载
    var el = document.getElementById(PANEL_ID);
    if (!el) {
      ensureStyle();
      if (kind === 'new') renderNew(); else renderDetail(id);
      return;
    }
    if (!el.isConnected) place(el);
    if (kind === 'detail') {
      // 进度就绪（真实节点）或选择态（草稿）都折叠旧的 6 步抽象卡，避免同一信息两遍
      var state = el.getAttribute('data-odrp-state');
      var mode = el.getAttribute('data-odrp-mode');
      if (state === 'ready' || mode === 'select') toggleLegacy(true);
    }
    if (kind === 'new') {
      var lv = readLevel();
      if (lv && lv !== lastLevel) { lastLevel = lv; renderNew(); }
    }
  }

  function boot() {
    patchTransport();
    document.addEventListener('click', onClick, true);
    document.addEventListener('input', onInput, true);
    document.addEventListener('change', onChange, true);

    ['pushState', 'replaceState'].forEach(function (m) {
      var orig = history[m];
      if (typeof orig !== 'function') return;
      history[m] = function () {
        var r = orig.apply(this, arguments);
        setTimeout(sync, 0);
        setTimeout(sync, 120);
        return r;
      };
    });
    window.addEventListener('popstate', function () { setTimeout(sync, 0); });

    var timer = null;
    var mo = new MutationObserver(function () {
      if (timer) return;
      timer = setTimeout(function () { timer = null; sync(); }, 260);
    });
    try { mo.observe(document.body, { childList: true, subtree: true }); } catch (e) { }
    setInterval(sync, 1200);
    setTimeout(sync, 600);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
