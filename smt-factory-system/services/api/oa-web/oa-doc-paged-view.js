/* ============================================================
 * 体系文件详情页：正文按 A4 纸页呈现（2026-11-01）
 * ------------------------------------------------------------
 * 背景：详情页原本把正文交给 Tiptap 只读编辑器渲染（.dcs-body > .rt-editor）。
 *   ProseMirror 会重建文档模型，Word 分页锚点（<hr page-break-after>）在这条路径上丢失，
 *   用户在屏幕上永远只能看到连续流。而带锚点的原始 HTML 一直存在 .doc-print-only
 *   （display:none，只给打印用）。
 *
 * 本脚本把那条原始 HTML 复制到一个可见容器里，交给 oa-docx-pages.js 包成 A4 纸页：
 *   · 只在 /docs/:id 生效
 *   · 只读态才接管；一旦进入编辑（.rt-editor 去掉 rt-readonly / contenteditable=true）立刻还原，
 *     免得挡住用户编辑
 *   · 原始 .doc-print-only 原样保留 —— 打印走它，屏幕走纸页，互不干扰
 *     （@media print 里 body.doc-print-mode{visibility:hidden} 已把本容器隐藏）
 *   · 幂等：按来源长度+开头做指纹，内容没变就不重建
 *   · Excel 表单正文（服务端 xlsx-import.js 产出）的宽表额外套一层横向滚动容器：
 *     存库 HTML 里的 <div> 会被详情页清洗器剥掉（只剩 table/tbody/tr/td），
 *     只有本脚本创建的 div 才留得住（2026-11-06）
 * ============================================================ */
(function () {
  'use strict';

  var ID = 'oa-paged-view';
  var STYLE_ID = 'oa-paged-view-style';
  var lastSig = '';

  var CSS = [
    /* 纸张外层：灰底衬出「一页页纸」 */
    '#' + ID + '{background:#eef1f5;border-radius:10px;padding:16px 10px;margin:12px 0 0}',
    /* 正文本体：一律沿用原文 inline 样式（docx 转换时已写入 font-size / line-height），
       这里只补颜色与断词 —— 任何字号/行高的"统一美化"都会把内容撑出 A4，破坏分页 */
    '#' + ID + ' .oa-sheet{color:#000;word-wrap:break-word}',
    '#' + ID + ' .oa-sheet p{margin:0}',
    /* 表格不加边框/内边距：原文 docx 已逐格写入 border / padding，加了反而变高、走形 */
    '#' + ID + ' table{border-collapse:collapse}',
    '#' + ID + ' img{max-width:100%;height:auto}',
    '#' + ID + ' mark{background:#fff3b0}',
    /* 纸页右上角的「第 N 页 / 共 M 页」由 oa-docx-pages.js 负责 */
    /* ---- Excel 正文的宽表：按原表列宽排开，正文区横向滚动（2026-11-06） ----
       服务端 xlsx-import.js 给宽表写了 min-width = 各列自然宽之和，这里负责给它一个
       能横向滚动的宿主。存库 HTML 里的 <div> 会被详情页清洗器剥掉（只剩 table/tbody/tr/td），
       所以滚动容器只能由本脚本在渲染后创建。 */
    '#' + ID + ' .oa-xlsx-scroll{overflow-x:auto;overflow-y:hidden;max-width:100%;' +
      'margin:0 0 12px;padding-bottom:4px;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}',
    '#' + ID + ' .oa-xlsx-scroll::-webkit-scrollbar{height:10px}',
    '#' + ID + ' .oa-xlsx-scroll::-webkit-scrollbar-thumb{background:#c6ced9;border-radius:5px}',
    '#' + ID + ' .oa-xlsx-scroll::-webkit-scrollbar-thumb:hover{background:#a9b4c3}',
    '#' + ID + ' .oa-xlsx-scroll::-webkit-scrollbar-track{background:#eef1f6;border-radius:5px}',
    /* 宽表的"随身滚动条"：贴在屏幕底部，滚动页面时始终在手边。
       63 行 × 4000px 高的表格，原生滚动条在表格最底部 —— 要拖一次得先滚几屏，
       跟 Excel 的窗口滚动条完全不是一个体验。这条是它的替身，和表格双向同步。 */
    '#oa-xlsx-mirror{position:fixed;left:0;right:0;bottom:0;z-index:9999;overflow-x:auto;' +
      'overflow-y:hidden;height:14px;padding:2px 0;background:rgba(255,255,255,.94);' +
      'box-shadow:0 -1px 0 #e3e8ef;display:none}',
    '#oa-xlsx-mirror.on{display:block}',
    '#oa-xlsx-mirror::-webkit-scrollbar{height:10px}',
    '#oa-xlsx-mirror::-webkit-scrollbar-thumb{background:#c6ced9;border-radius:5px}',
    '#oa-xlsx-mirror::-webkit-scrollbar-thumb:hover{background:#a9b4c3}',
    '#oa-xlsx-mirror::-webkit-scrollbar-track{background:#f3f6fa;border-radius:5px}',
    '#oa-xlsx-mirror .oa-xlsx-mirror-in{height:1px}',
    '@media (max-width:860px){#' + ID + '{background:transparent;padding:0;border-radius:0}}',
    /* 直接 Ctrl+P 时按纸页打印：去灰底、去缩放，一张纸一页 */
    '@media print{',
    '  #' + ID + '{background:#fff;padding:0;margin:0;border-radius:0}',
    '  #' + ID + ' .oa-sheet{zoom:1}',
    /* 打印/PDF 没有"横向滚动"这回事：宽表退回按纸宽压排，否则右侧列会被裁掉 */
    '  #' + ID + ' .oa-xlsx-scroll{overflow:visible;margin:0}',
    '  #' + ID + ' .oa-xlsx-scroll > table{min-width:0 !important;width:100% !important}',
    '  #oa-xlsx-mirror{display:none !important}',
    '}'
  ].join('');

  function addStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function isDetail() {
    return /^\/docs\/\d+\/?$/.test(location.pathname);
  }

  /** 是否处于编辑态（此时必须交还给 Tiptap） */
  function isEditing() {
    var ed = document.querySelector('.rt-editor');
    if (!ed) return false;
    if (!ed.classList.contains('rt-readonly')) return true;
    var ce = ed.querySelector('[contenteditable]');
    return !!(ce && ce.getAttribute('contenteditable') === 'true');
  }

  function teardown() {
    var box = document.getElementById(ID);
    if (box && box.parentNode) box.parentNode.removeChild(box);
    var sw = document.querySelector('.doc-content-switch');
    if (sw && sw.style.display === 'none') sw.style.display = '';
    if (mirror) { mirror.classList.remove('on'); mirrorWrap = null; }
    lastSig = '';
  }

  /**
   * 给「宽表」套一个横向滚动容器（2026-11-06）
   *
   * 判据：table 的内联样式里带 min-width（只有服务端 xlsx-import.js 会写这个，docx 正文不会有）。
   * 只包一层 div、不动表格本身，所以不会影响分页（div 是合法文章块）与打印。
   * 幂等：已经包过的跳过（sync 会整体重建 innerHTML，重建后自然重新包）。
   */
  function wrapWideTables(root) {
    var tables = root.querySelectorAll('table');
    var n = 0;
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var parent = t.parentNode;
      if (parent && parent.classList && parent.classList.contains('oa-xlsx-scroll')) continue;
      if (!/min-width\s*:\s*\d+px/i.test(t.getAttribute('style') || '')) continue;
      var wrap = document.createElement('div');
      wrap.className = 'oa-xlsx-scroll';
      parent.insertBefore(wrap, t);
      wrap.appendChild(t);
      n++;
    }
    return n;
  }

  /**
   * 宽表的「随身横向滚动条」（2026-11-06）
   *
   * 原生滚动条在表格最底部：63 行 × 4000px 高的表，要横向拖一次得先往下滚几屏。
   * 这里在 body 上挂一条 position:fixed 的镜像滚动条，滚动页面时始终贴在屏幕底部，
   * 宽度/位置对齐当前正在看的这张宽表，与表格双向同步 scrollLeft。
   */
  var mirror = null, mirrorInner = null, mirrorWrap = null;
  var insetCache = { v: 0, t: 0 };

  function ensureMirror() {
    if (mirror && document.body.contains(mirror)) return mirror;
    mirror = document.createElement('div');
    mirror.id = 'oa-xlsx-mirror';
    mirrorInner = document.createElement('div');
    mirrorInner.className = 'oa-xlsx-mirror-in';
    mirror.appendChild(mirrorInner);
    document.body.appendChild(mirror);
    mirror.addEventListener('scroll', function () {
      // 镜像条被拖动（或点轨道）→ 回写当前宽表。
      // 这里不做 mirrorLock 判断：两侧值收敛即停，防止"当前表还没定下来"时把拖动丢掉。
      var w = mirrorWrap || pickWrap();
      if (!w) return;
      mirrorWrap = w;
      if (Math.abs(w.scrollLeft - mirror.scrollLeft) > 1) w.scrollLeft = mirror.scrollLeft;
    });
    return mirror;
  }

  /** 底部固定操作栏（开始编辑/发起废版…）会盖住滚动条，量出它的高度 */
  function bottomInset() {
    var now = Date.now();
    if (now - insetCache.t < 1500) return insetCache.v;
    var v = 0;
    // 详情页的按钮条是 .oa-action-bar（position:sticky，底部还留 20px 空隙），
    // 光按"贴着屏幕底"判断会漏掉它 → 这里认类名，并统一用 innerHeight - top 当偏移。
    var bars = document.querySelectorAll('.oa-action-bar,.el-affix--fixed,footer');
    for (var i = 0; i < bars.length; i++) {
      var el = bars[i];
      if (el === mirror || el.id === ID) continue;
      var st = getComputedStyle(el);
      if (st.position !== 'fixed' && st.position !== 'sticky') continue;
      if (st.display === 'none' || st.visibility === 'hidden') continue;
      var r = el.getBoundingClientRect();
      if (r.height < 20 || r.height > 180) continue;
      if (r.bottom < innerHeight - 60) continue;             // 必须在视口底部区域
      if (r.top > innerHeight - 20) continue;
      var h = innerHeight - r.top;
      if (h > v) v = h;
    }
    insetCache.v = v; insetCache.t = now;
    return v;
  }

  function wideWraps() {
    var host = document.getElementById(ID);
    if (!host) return [];
    return Array.prototype.slice.call(host.querySelectorAll('.oa-xlsx-scroll'))
      .filter(function (w) { return w.scrollWidth > w.clientWidth + 2; });
  }

  /** 取"当前视口里占面积最大"的那张宽表 */
  function pickWrap() {
    var list = wideWraps(), best = null, bestH = 0;
    for (var i = 0; i < list.length; i++) {
      var r = list[i].getBoundingClientRect();
      var h = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
      if (h > bestH) { bestH = h; best = list[i]; }
    }
    return bestH > 60 ? best : null;
  }

  var mirrorQueued = false;
  function updateMirror() {
    if (mirrorQueued) return;
    mirrorQueued = true;
    requestAnimationFrame(function () {
      mirrorQueued = false;
      if (!isDetail()) { if (mirror) mirror.classList.remove('on'); return; }
      var w = pickWrap();
      if (!w) { if (mirror) { mirror.classList.remove('on'); mirrorWrap = null; } return; }
      ensureMirror();
      var r = w.getBoundingClientRect();
      mirror.style.left = Math.round(r.left) + 'px';
      mirror.style.width = Math.round(r.width) + 'px';
      mirror.style.bottom = Math.round(bottomInset()) + 'px';
      if (mirrorInner.style.width !== w.scrollWidth + 'px') mirrorInner.style.width = w.scrollWidth + 'px';
      if (mirrorWrap !== w) { mirrorWrap = w; mirror.scrollLeft = w.scrollLeft; }
      mirror.classList.add('on');
    });
  }

  window.addEventListener('scroll', updateMirror, true);
  window.addEventListener('resize', function () { insetCache.t = 0; updateMirror(); });
  // 表体本身横向滚动时，回写镜像条
  document.addEventListener('scroll', function (e) {
    var t = e.target;
    if (!t || !t.classList || !t.classList.contains('oa-xlsx-scroll')) return;
    if (!mirror || !mirror.classList.contains('on') || t !== mirrorWrap) return;
    if (Math.abs(mirror.scrollLeft - t.scrollLeft) > 1) mirror.scrollLeft = t.scrollLeft;
  }, true);

  function sync() {
    if (!isDetail()) { teardown(); return; }

    var po = document.querySelector('.doc-print-only');
    if (!po || !po.innerHTML || po.innerHTML.length < 200) return;   // 正文还没到
    if (isEditing()) { teardown(); return; }

    var html = po.innerHTML;
    var sw = document.querySelector('.doc-content-switch');
    var sig = html.length + ':' + html.slice(0, 120);

    var box = document.getElementById(ID);
    if (box && sig === lastSig) {
      if (sw && sw.style.display !== 'none') sw.style.display = 'none';
      return;
    }
    if (!box) {
      box = document.createElement('div');
      box.id = ID;
      po.parentNode.insertBefore(box, po);
    }
    addStyle();
    box.innerHTML = html;             // 含 <hr> 锚点 → oa-docx-pages.js 的 MutationObserver 会包纸
    wrapWideTables(box);              // Excel 宽表 → 横向滚动容器（必须在分页之前，div 属于合法文章块）
    lastSig = sig;
    if (sw) sw.style.display = 'none';
    setTimeout(updateMirror, 60);     // 内容刚进 DOM，等一帧再量宽度
  }

  // 定时兜底：SPA 路由切换、异步加载、语言/版本切换都靠它收敛。
  // 主路径是下面的 MutationObserver；这里间隔放长，避免反复序列化大段 innerHTML 拖慢页面。
  var timer = setInterval(sync, 1500);

  // 更快的响应：正文容器或编辑器状态一变就同步
  var mo = new MutationObserver(function () { sync(); });
  function observe() {
    var po = document.querySelector('.doc-print-only');
    var ed = document.querySelector('.rt-editor');
    if (po) mo.observe(po, { childList: true, characterData: true, subtree: true });
    if (ed) mo.observe(ed, { attributes: true, attributeFilter: ['class'] });
  }
  var obTimer = setInterval(function () {
    observe();
    if (document.querySelector('.doc-print-only')) clearInterval(obTimer);
  }, 600);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(sync, 400); });
  } else {
    setTimeout(sync, 400);
  }

  // 离开详情页时清理，避免纸页残留在其它页面
  window.addEventListener('popstate', function () { setTimeout(sync, 50); });
  window.__oaPagedViewOff = function () { clearInterval(timer); clearInterval(obTimer); mo.disconnect(); teardown(); };
})();
