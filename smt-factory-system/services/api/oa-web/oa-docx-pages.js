/* ============================================================
 * 体系文件正文「按 Word 分页」呈现（2026-10-30）
 * ------------------------------------------------------------
 * 背景：docx 导入后正文是连续流，用户要求「严格对照 Word 分页」。
 *   服务端 docx-import.js 已把 Word 的 lastRenderedPageBreak 快照落成分页锚点：
 *     <hr style="...;page-break-after:always">
 *   实测 DT-MM-001：切出 98 页，与 docProps/app.xml 的 <Pages>98</Pages> 一致，
 *   浏览器打印成 PDF 也是 98 页。
 *
 * 本脚本负责屏幕呈现：把分页锚点之间的内容包成一张 A4 纸。
 *   · 宽屏（容器 ≥ 820px）才包纸，窄屏保持流式 —— 手机上固定 210mm 会横向溢出
 *   · contenteditable / 编辑器内不处理，否则会破坏光标与输入
 *   · 幂等：已包过的容器打 data 标记，MutationObserver 只在发现新锚点时重跑
 *
 * 不改动任何 chunk，纯 DOM 后处理 —— dist 压缩包无 sourcemap，改 bundle 风险更高。
 * ============================================================ */
(function () {
  'use strict';

  var STYLE_ID = 'oa-docx-pages-style';
  var DONE = 'oaPaged';
  var MIN_W = 720;          // 正文容器窄于此就不包纸（手机上固定 210mm 会横向溢出）
  var PT_W = 794;           // A4 210mm 对应的 CSS 像素宽
  var PAD_MM = 20;          // A4 页边距：本厂体系文件统一 20mm

  var CSS = [
    /* 正文宿主垫一层浅灰，纸页才看得出是「一张张纸」；否则白纸贴白底会糊成一片 */
    '.oa-paged-host{background:#eef1f5 !important;padding:16px 10px !important;border-radius:10px}',
    '.oa-sheet{',
    '  position:relative;box-sizing:border-box;',
    '  width:210mm;min-height:297mm;padding:' + PAD_MM + 'mm;',
    '  margin:0 auto 16px;background:#fff;',
    '  box-shadow:0 2px 10px rgba(16,32,60,.13),0 0 0 1px rgba(16,32,60,.05);',
    '  overflow:hidden;',
    '  zoom:var(--oa-paper-zoom,1);',   /* 容器放不下整张 A4 时等比缩小，保证「一页纸」完整可见 */
    '}',
    '.oa-sheet:last-child{margin-bottom:0}',
    '.oa-sheet > p:first-child,.oa-sheet > table:first-child{margin-top:0}',
    '.oa-sheet .oa-pgno{',
    '  position:absolute;right:8mm;bottom:5mm;',
    '  font:10px/1 system-ui,sans-serif;color:#b9c2ce;letter-spacing:.4px;',
    '}',
    '.oa-docx-flow{border:0;border-top:1px dashed #c8cfd8;margin:14px 0}',
    '@media (max-width:860px){',
    '  .oa-paged-host{background:transparent !important;padding:0 !important;border-radius:0}',
    '  .oa-sheet{width:100%;min-height:0;padding:12px;box-shadow:none;border-bottom:1px dashed #ccd3dd;margin-bottom:0}',
    '  .oa-sheet .oa-pgno{display:none}',
    '}',
    '@media print{',
    '  .oa-paged-host{background:#fff !important;padding:0 !important;border-radius:0}',
    '  .oa-sheet{width:auto;min-height:0;padding:0;margin:0;box-shadow:none;break-after:page;page-break-after:always}',
    '  .oa-sheet:last-child{break-after:auto;page-break-after:auto}',
    '  .oa-sheet .oa-pgno{display:none}',
    '}'
  ].join('');

  function addStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /** 编辑器/可编辑区域内一律不动 */
  function isEditable(el) {
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (n.isContentEditable) return true;
      var cn = (n.className && typeof n.className === 'string') ? n.className : '';
      if (/(^|\s)(ql-editor|ProseMirror|tox-tinymce|wangEditor|edui-body)/.test(cn)) return true;
      if (n.getAttribute && n.getAttribute('contenteditable') === 'true') return true;
    }
    return false;
  }

  /** 是不是分页锚点 */
  function isBreaker(el) {
    if (!el || el.tagName !== 'HR') return false;
    var st = el.getAttribute('style') || '';
    return /page-break-after\s*:\s*always/i.test(st) || el.hasAttribute('data-oa-pagebreak');
  }

  /** 父容器里的子元素是否都是「文章块」，是才敢整体重组 */
  function isArticleHost(parent) {
    if (!parent || parent.nodeType !== 1) return false;
    if (parent.classList.contains('oa-sheet')) return false;
    var ALLOW = { P: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, TABLE: 1, UL: 1, OL: 1, BLOCKQUOTE: 1, HR: 1, DIV: 1, IMG: 1, PRE: 1, SPAN: 1, SECTION: 1, FIGURE: 1 };
    var seen = 0;
    for (var i = 0; i < parent.childNodes.length; i++) {
      var n = parent.childNodes[i];
      if (n.nodeType === 3) { if (n.nodeValue.trim()) return false; continue; }
      if (n.nodeType !== 1) continue;
      if (!ALLOW[n.tagName]) return false;
      seen++;
    }
    return seen > 1;
  }

  /** 把一个容器按分页锚点重组成若干 A4 纸 */
  function pageUp(host) {
    // 量高度前先把缩放归一成 1。Chromium 128+ 的 offsetTop/offsetHeight/scrollHeight 不随
    // CSS zoom 缩放（2026-11-04 实测：zoom .7 时 1651→1651，只有 rect 变 1155.8），老版 Chromium
    // 则会缩放 —— 归一化后两代浏览器、以及 mmPx(297) 用的 rect 口径才一致。
    host.style.setProperty('--oa-paper-zoom', '1');
    var kids = Array.prototype.slice.call(host.childNodes);
    var groups = [];
    var cur = [];
    for (var i = 0; i < kids.length; i++) {
      var n = kids[i];
      if (n.nodeType === 1 && isBreaker(n)) {
        groups.push(cur);
        cur = [];
        continue;
      }
      cur.push(n);
    }
    groups.push(cur);
    // 没有锚点时 groups 只有 1 组 —— 以前直接返回 false（整篇不切纸）；
    // 现在照样包成一张纸，再由 balance() 按 A4 高度切分（>=1 组都进入包纸流程）
    if (groups.length < 1) return false;

    // 纯空白组一律丢弃：Word 里的分节符 + 紧随的空段落会被转成两个分页锚点，
    // 中间夹一个空组，若不丢就会出现 Word 里不存在的空白页（实测 SIP-QA-011 封面后即如此）。
    var isEmpty = function (g) {
      return !g.some(function (n) {
        if (n.nodeType === 3) return n.nodeValue.trim().length > 0;
        if (n.nodeType !== 1) return false;
        if (n.tagName === 'BR') return false;
        if (n.tagName === 'IMG' || n.tagName === 'TABLE') return true;
        return (n.textContent || '').trim().length > 0;
      });
    };
    groups = groups.filter(function (g) { return !isEmpty(g); });
    if (groups.length < 1) return false;

    var frag = document.createDocumentFragment();
    var seq = 0;                              // 文档原始序号：溢出的块无论被谁先搬走，最后都按它归位
    groups.forEach(function (g, idx) {
      var sheet = document.createElement('div');
      sheet.className = 'oa-sheet';
      g.forEach(function (n) { if (n.nodeType === 1) n.__oaSeq = seq++; else if (n.nodeType === 3) n.__oaSeq = seq++; sheet.appendChild(n); });
      var no = document.createElement('div');
      no.className = 'oa-pgno';
      no.textContent = (idx + 1) + ' / ' + groups.length;
      sheet.appendChild(no);
      frag.appendChild(sheet);
    });
    while (host.firstChild) host.removeChild(host.firstChild);
    host.appendChild(frag);
    // Word 的 lastRenderedPageBreak 是保存时的排版快照，表格内部常常没有记录，
    // 会留下「一页塞 3 页内容」的超长页。这里按 A4 实际可容纳高度再切一次，保证每张纸都装得下。
    try {
      balance(host);
    } catch (e) {
      // 切不动就保持原样（至少不丢内容），但把原因留下来，免得静默失败
      window.__oaPagedErr = String((e && e.stack) || e);
      if (window.console) console.warn('[oa-docx-pages] 分页失败：', e);
    }
    host.setAttribute('data-' + DONE.toLowerCase(), '1');
    return true;
  }

  /** 毫米 → 布局像素（body 未缩放，得到的是布局值，与 scrollHeight 同口径） */
  function mmPx(mm) {
    var d = document.createElement('div');
    d.style.cssText = 'position:absolute;left:-99999px;top:0;width:1px;height:' + mm + 'mm;visibility:hidden;pointer-events:none';
    document.body.appendChild(d);
    var h = d.getBoundingClientRect().height;
    document.body.removeChild(d);
    return h;
  }

  function padOf(el) {
    var cs = getComputedStyle(el);
    return (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  }

  /** 这页纸实际需要的内容高度 / 一页纸能装的内容高度 */
  function contentH(sheet) { return sheet.scrollHeight - padOf(sheet); }
  function maxContentH(sheet) { return mmPx(297) - padOf(sheet); }

  function isPgno(n) {
    return n.nodeType === 1 && n.classList && n.classList.contains('oa-pgno');
  }

  function setPgno(sheet, idx, total) {
    var no = null;
    for (var i = 0; i < sheet.children.length; i++) {
      if (isPgno(sheet.children[i])) { no = sheet.children[i]; break; }
    }
    if (!no) { no = document.createElement('div'); no.className = 'oa-pgno'; sheet.appendChild(no); }
    no.textContent = idx + ' / ' + total;
  }

  /** 整页只有一个超大表格时，按行从尾部搬到新表（Word 也只在行边界分页） */
  function splitTableTail(table, max, sheet) {
    var body = table.tBodies && table.tBodies[0];
    if (!body || body.rows.length < 2) return null;
    var clone = table.cloneNode(false);
    // 残片必须排在同一张原表**之后**、它后面的块**之前**：给一个略大于原表的序号
    clone.__oaSeq = (typeof table.__oaSeq === 'number' ? table.__oaSeq : 0) + 1e-6;
    var cg = table.querySelector('colgroup');
    if (cg) clone.appendChild(cg.cloneNode(true));
    var cbody = document.createElement('tbody');
    clone.appendChild(cbody);
    while (contentH(sheet) > max + 1 && body.rows.length > 1) {
      cbody.insertBefore(body.rows[body.rows.length - 1], cbody.firstChild);
    }
    if (!cbody.rows.length) return null;
    return clone;
  }

  /**
   * 把一页装不下的内容从尾部切出来，返回「必须排到下一页页首」的节点（保持文档顺序）。
   *
   * 2026-11-04 重写（用户反馈「上传后第 22 页只有一行、整页空白」）：
   *   旧实现是「溢出就把尾部块塞进一张新建的纸」，但从不把下一张纸的头部内容往回填 ——
   *   某页只溢出 1 段时，就会生成一张「一段 + 整页空白」的孤儿页（DT-MM-001 即此形态）。
   *   而且旧实现每挪一块就调一次 contentH（每次强制重排），一百多块的一页要重排上千次。
   *   现在改成：一次布局量出所有块的底边再一次性切，溢出内容由 balance() 顺延到下一页页首。
   */
  function splitSheet(sheet, max) {
    var moved = [];
    var guard = 0;
    while (guard++ < 300) {
      var blocks = [];
      for (var i = 0; i < sheet.childNodes.length; i++) {
        var n = sheet.childNodes[i];
        if (isPgno(n)) continue;
        if (n.nodeType === 3 && !n.nodeValue.trim()) continue;
        blocks.push(n);
      }
      if (!blocks.length) break;

      // 一次布局量出每个块的底边（offsetTop/offsetHeight 是同一份布局结果，逐块读不会反复重排）
      var padTop = parseFloat(getComputedStyle(sheet).paddingTop) || 0;
      var cut = -1;
      for (var k = 0; k < blocks.length; k++) {
        var b = blocks[k];
        if (b.nodeType !== 1) continue;                       // 纯文本块没有 offsetTop，跳过
        if (b.offsetTop + b.offsetHeight - padTop > max + 1) { cut = k; break; }
      }
      if (cut < 0) {                                          // 块底边都在页内
        // 但末块的 margin-bottom 会把 scrollHeight 顶出纸外（实测 DT-MM-001 有 3 张 +7px，
        // 打印时多吐一行到下一张物理纸）→ 退掉末块再量
        if (contentH(sheet) > max + 1 && blocks.length > 1) { cut = blocks.length - 1; }
        else break;
      }

      // 溢出块是表格：按行续排（Word 也只在行边界分页），本页留下装得下的行。
      // 注意顺序：表格后面若还有块，它们同样装不下，必须先搬到 moved、再把表格剩下的行
      // 续排到 moved 的**前面** —— 否则续排的表会排到那些块后面，整篇顺序就乱了
      // （2026-11-04 QA 实测：附录 A 条款对照表后面还有块，导致 4 块逆序）。
      var culprit = blocks[cut];
      if (culprit.nodeType === 1 && culprit.tagName === 'TABLE') {
        for (var m2 = blocks.length - 1; m2 > cut; m2--) {
          sheet.removeChild(blocks[m2]);
          moved.push(blocks[m2]);
        }
        var tailTable = splitTableTail(culprit, max, sheet);
        if (tailTable) { moved.push(tailTable); continue; }
        // 拆不动（只有一行/没有 tbody）→ 整表搬到下一页，现在它已是本页最后一块
        sheet.removeChild(culprit);
        moved.push(culprit);
        continue;
      }
      // 第一块就超页（超大图片 / 只有一行的表格）：放弃切分，让这张纸自己长高，宁可长一页也不截断内容
      if (cut === 0) { sheet.classList.add('oa-sheet-oversize'); break; }

      for (var m = blocks.length - 1; m >= cut; m--) {
        sheet.removeChild(blocks[m]);
        moved.push(blocks[m]);
      }
    }
    // 一律按文档原始序号排序返回 —— 顺序不再依赖「谁先被 unshift」，以后加分支也不会退化
    moved.sort(function (a, b) {
      var x = typeof a.__oaSeq === 'number' ? a.__oaSeq : 1e12;
      var y = typeof b.__oaSeq === 'number' ? b.__oaSeq : 1e12;
      return x - y;
    });
    return moved;
  }

  /**
   * 把上一页溢出的内容插到**页首**（页码元素本来就是最后 append 的，插在 firstChild 之前即可）。
   *
   * 2026-11-04 修正：原来拿 `.oa-pgno` 当锚点 —— 它是最后一个子节点，
   * `insertBefore(node, pgno)` 实际插到的是**页尾**，于是溢出内容被排到本页末尾、
   * 下次又最先被溢出，一路往后漂，整篇段落顺序错乱（QA 实测 548/2893 段错位）。
   * 现在用固定的 firstChild 当锚点，按顺序插，顺序与原文一致。
   */
  function prependTo(sheet, nodes) {
    var anchor = sheet.firstChild;                  // 固定锚点，逐条插在它前面 → 保持原顺序
    for (var k = 0; k < nodes.length; k++) sheet.insertBefore(nodes[k], anchor);
  }

  /**
   * 全局重排（2026-11-04 重写）：
   *   ① 逐页往下走，本页溢出的内容顺延到**下一页的页首**，合并后再判断是否溢出，一路级联；
   *      走到最后一页还有内容没处放，就续一张新纸接着排。
   *      → 除最后一页外不会再有「一行 + 整页空白」，也没有内容被留在纸外。
   */
  function balance(host) {
    var sheets = Array.prototype.slice.call(host.querySelectorAll('.oa-sheet'));
    if (!sheets.length) return;
    var max = maxContentH(sheets[0]);
    if (!(max > 0)) return;

    var carry = [];
    var guard = 0;
    for (var i = 0; i < sheets.length && guard++ < 4000; i++) {
      var sh = sheets[i];
      if (carry.length) { prependTo(sh, carry); carry = []; }

      var moved = splitSheet(sh, max);
      if (!moved.length) continue;
      carry = moved;
      if (i === sheets.length - 1) {          // 最后一页也装不下 → 续排新纸
        var next = document.createElement('div');
        next.className = 'oa-sheet';
        host.appendChild(next);
        sheets.push(next);
      }
    }

    for (var j = 0; j < sheets.length; j++) setPgno(sheets[j], j + 1, sheets.length);
  }

  /** 按容器宽度等比缩放纸页，保证整张 A4 横向完整可见（小屏也不横向滚动） */
  function fitZoom(host) {
    // ≤860px 时 @media 已把 .oa-sheet 改成 width:100% / min-height:0，再按 794 缩放会变成双重缩小
    if (window.matchMedia && window.matchMedia('(max-width:860px)').matches) {
      host.style.setProperty('--oa-paper-zoom', '1');
      return;
    }
    var avail = host.clientWidth - 20;      // 扣掉 .oa-paged-host 左右各 10px 内边距
    var k = Math.min(1, avail / PT_W);
    if (k < 0.55) k = 0.55;
    host.style.setProperty('--oa-paper-zoom', k.toFixed(3));
  }

  function run() {
    var t0 = (window.performance && performance.now()) || 0;
    addStyle();
    // 找出所有未处理的分页锚点的父容器
    var hrs = document.querySelectorAll('hr[style*="page-break-after"],hr[data-oa-pagebreak]');
    var hosts = [];
    for (var i = 0; i < hrs.length; i++) {
      var h = hrs[i];
      if (h.closest && h.closest('.oa-sheet')) continue;
      var p = h.parentElement;
      if (!p || hosts.indexOf(p) >= 0) continue;
      if (!isArticleHost(p)) continue;
      // 太窄就只美化成一条分页线，不做纸页
      if (p.getBoundingClientRect().width < MIN_W) {
        h.classList.add('oa-docx-flow');
        continue;
      }
      hosts.push(p);
    }
    // 兜底：正文容器里**一个分页锚点都没有**时（Word 没存过排版快照 / 程序生成的文档），
    // 上面这段永远命中不了，正文会退化成一条连续长流且没有任何报错（2026-11-04 调查员实测：
    // 无 <hr> 的输入页数恒为 1）。这里直接认专门的正文容器，交给 pageUp 按 A4 高度切。
    var stocks = document.querySelectorAll('#oa-paged-view,[data-oa-paged-host]');
    for (var s2 = 0; s2 < stocks.length; s2++) {
      var sp = stocks[s2];
      if (sp.hasAttribute('data-' + DONE.toLowerCase())) continue;
      if (hosts.indexOf(sp) >= 0) continue;
      if (!isArticleHost(sp)) continue;
      if (sp.getBoundingClientRect().width < MIN_W) continue;
      hosts.push(sp);
    }
    var ok = 0;
    for (var k = 0; k < hosts.length; k++) {
      if (isEditable(hosts[k])) continue;
      try {
        if (pageUp(hosts[k])) {
          hosts[k].classList.add('oa-paged-host');
          fitZoom(hosts[k]);
          ok++;
        }
      } catch (e) { /* 单篇失败不影响其它 */ }
    }
    if (t0) window.__oaPagedMs = Math.round(performance.now() - t0);
    return ok;
  }

  var queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () {
      queued = false;
      run();
    });
  }

  function boot() {
    addStyle();
    schedule();
    // SPA 路由切换 / 正文异步到达：监听新增节点再处理
    var mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var added = muts[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var n = added[j];
          if (n.nodeType === 1 && (n.tagName === 'HR' || n.id === 'oa-paged-view'
              || (n.querySelector && n.querySelector('hr, #oa-paged-view')))) { schedule(); return; }
        }
      }
    });
    mo.observe(document.body, { childList: true, subtree: true });
    // 窗口跨过断点时重算（纸页 ↔ 流式）：整页重载最稳，避免已包纸的 DOM 半新半旧
    // 无锚点文档不会触发上面的 MutationObserver（内容里没有 hr），靠有限次重试把首批正文等出来
    var tries = 0;
    var kick = setInterval(function () {
      if (++tries > 8) { clearInterval(kick); return; }
      schedule();
    }, 800);
    var lastNarrow = window.innerWidth < MIN_W;
    window.addEventListener('resize', function () {
      var narrow = window.innerWidth < MIN_W;
      if (narrow !== lastNarrow) { lastNarrow = narrow; location.reload(); return; }
      // 断点内只调缩放，不重建纸页
      var hs = document.querySelectorAll('.oa-paged-host');
      for (var i = 0; i < hs.length; i++) fitZoom(hs[i]);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
