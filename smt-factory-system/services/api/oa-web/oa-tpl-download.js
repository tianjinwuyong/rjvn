// ============================================================
// 导入模板下载器 —— 从服务端取「带下拉选」的 .xlsx
// ------------------------------------------------------------
// 为什么要有这个文件：
//   这几份导入模板原来是浏览器端用 SheetJS 现拼的（列定义写死在压缩产物里），
//   SheetJS 社区版**不能写数据有效性**，所以下载到的模板是纯空表，班次/频率/状态
//   全靠人肉打字。改成服务端生成后（/api/xxx/template.xlsx），前端只负责把 blob 存下来。
//
// 为什么要单独一个文件而不是改各页面：
//   dist 是压缩产物、没有源码。页面里只把「存盘那一行」换成本函数调用，
//   下载逻辑集中在这里一处，以后再改（比如加下载进度）不用再反编译 4 个 chunk。
//
// 约定：
//   · 成功**不弹提示**（各页面本来就有「模板已下载」的 toast，重复弹两次很吵）；
//   · 失败一定弹出来 —— 否则用户点了没反应，只会以为系统坏了。
// ============================================================
(function () {
  'use strict';

  function readLS(key) {
    try { return localStorage.getItem(key) || ''; } catch (e) { return ''; }
  }

  function token() {
    return readLS('oa_token');
  }

  function lang() {
    var v = readLS('oa_lang') || readLS('oa-locale') || 'zh';
    return /^(zh|vi|en)$/.test(v) ? v : 'zh';
  }

  /* ---------------- 轻量提示条（不依赖 Element Plus） ---------------- */
  function ensureStyle() {
    if (document.getElementById('oa-tpl-dl-style')) return;
    var css = ''
      + '#oa-tpl-dl-toast{position:fixed;left:50%;top:22px;transform:translateX(-50%);'
      + 'z-index:2147483000;padding:10px 18px;border-radius:8px;font-size:14px;line-height:1.5;'
      + 'max-width:70vw;box-shadow:0 6px 24px rgba(0,0,0,.18);display:none}'
      + '#oa-tpl-dl-toast.is-err{background:#fef0f0;color:#c45656;border:1px solid #fbc4c4}'
      + '#oa-tpl-dl-toast.is-ok{background:#f0f9eb;color:#529b2e;border:1px solid #c2e7b0}';
    var el = document.createElement('style');
    el.id = 'oa-tpl-dl-style';
    el.textContent = css;
    document.head.appendChild(el);
  }

  function toast(msg, kind) {
    try {
      ensureStyle();
      var el = document.getElementById('oa-tpl-dl-toast');
      if (!el) {
        el = document.createElement('div');
        el.id = 'oa-tpl-dl-toast';
        document.body.appendChild(el);
      }
      el.className = kind === 'ok' ? 'is-ok' : 'is-err';
      el.textContent = String(msg || '');
      el.style.display = 'block';
      clearTimeout(el._t);
      el._t = setTimeout(function () { el.style.display = 'none'; }, 4200);
    } catch (e) { /* 提示失败不影响下载 */ }
  }

  function pickMsg(zh, vi, en) {
    var l = lang();
    return l === 'vi' ? vi : (l === 'en' ? en : zh);
  }

  /**
   * 下载服务端模板。
   * @param {string} url      例：/api/attendance/schedule/template.xlsx
   * @param {string} filename 例：schedule-import-template.xlsx
   */
  window.oaTplDownload = function (url, filename) {
    var headers = { 'X-OA-Lang': lang() };
    var tk = token();
    if (tk) headers.Authorization = 'Bearer ' + tk;

    return fetch(url, { headers: headers, credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) {
          // 401/403 最常见：登录过期或没权限；把状态码带上，别让人猜
          return res.text().then(function (body) {
            var msg = '';
            try { msg = JSON.parse(body).msg || ''; } catch (e) { /* 非 json */ }
            throw new Error(msg || ('HTTP ' + res.status));
          });
        }
        return res.blob();
      })
      .then(function (blob) {
        var a = document.createElement('a');
        var href = URL.createObjectURL(blob);
        a.href = href;
        a.download = filename || 'template.xlsx';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(href); if (a.parentNode) a.parentNode.removeChild(a); }, 1500);
        return true;
      })
      .catch(function (e) {
        toast(pickMsg('模板下载失败：', 'Tải mẫu thất bại: ', 'Template download failed: ') + (e && e.message ? e.message : ''), 'err');
        return false;
      });
  };
})();
