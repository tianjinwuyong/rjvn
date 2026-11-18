/* ============================================================
 * 体系文件受控水印（2026-11-05）
 * ------------------------------------------------------------
 * 需求：一级（手册）/二级（程序）/三级（作业）文件在线预览时叠加受控水印，
 *   四级表单不加（表单是要打印填写的记录，水印会挡书写）。
 *   水印文案与文件封面口径一致（受控文件 / 未经批准不得复制），中越双语，
 *   并带「查看人 · 工号 · 时间」，纸张流出后可回溯到人。
 *
 * 实现约束：
 *   · 前端只有 dist 构建产物，无 Vue 源码 → 走运行期补丁，不改打包产物
 *   · 水印只挂在 oa-docx-pages.js 生成的 .oa-sheet 上（该元素已是
 *     position:relative + overflow:hidden，天然是水印容器）
 *   · 编辑态绝不加水印（会和 Tiptap 光标、选字打架）
 *   · 屏幕水印挂在 .oa-sheet 上
 *   · 打印稿（2026-11-07）：「导出PDF / 打印」原本走 body.doc-print-mode 下的
 *     .doc-print-only 连续流，纸页整体 visibility:hidden，所以打印稿带不上水印。
 *     实测在这条通道上加什么都白搭——canvas 底图、固定覆盖层、DOM 文字，
 *     Chrome 只会画到第 1 页，第 2 页起全部丢失；SVG 底图虽然能重复，
 *     但 90 多页的手册会把渲染进程直接打崩。
 *     最终做法：一二三级改成「打印已经分好页的 A4 纸页」——每张纸是普通块，
 *     水印层跟着自己那张纸走，页页都在，顺带让打印页数等于 Word 页数。
 *     四级表单不加印，仍走原来的连续流。
 *
 * 幂等：按「文档 + 版本 + 状态 + 查看人 + 日期」做签名，签名没变不重绘。
 * ============================================================ */
(function () {
  'use strict';

  var STYLE_ID = 'oa-wm-style';
  var WM_CLASS = 'oa-wm-layer';
  var metaCache = {};     // docId -> { code, level, status, version }
  var meCache = null;     // { name, no }
  var tileCache = {};     // sig -> dataURL
  var fetching = {};

  function tok() { return localStorage.getItem('oa_token') || ''; }

  function detailId() {
    var m = /^\/docs\/(\d+)\/?$/.exec(location.pathname);
    return m ? m[1] : null;
  }

  function isEditing() {
    var ed = document.querySelector('.rt-editor');
    if (!ed) return false;
    if (!ed.classList.contains('rt-readonly')) return true;
    var ce = ed.querySelector('[contenteditable]');
    return !!(ce && ce.getAttribute('contenteditable') === 'true');
  }

  function apiGet(path) {
    return fetch(path, { headers: { Authorization: 'Bearer ' + tok() } })
      .then(function (r) { return r.json(); })
      .then(function (j) { return j && j.code === 0 ? j.data : null; })
      .catch(function () { return null; });
  }

  function today() {
    var d = new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }
  function clock() {
    var d = new Date();
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /** 生成一张平铺水印图（canvas，中文/越南语都不会丢字）
   *  注意：canvas 按 dpr 放大绘制，返回时必须同时给出 CSS 尺寸，
   *  否则浏览器按位图原始像素平铺，水印之间会出现大片空白、文字被切断。
   *  mul：透明度倍率。屏幕上 1；打印纸上纸张不吸墨，用 1.6 提亮到看得见。 */
  function makeTile(lines, mul) {
    var W = 430, H = 300, dpr = 2;
    var c = document.createElement('canvas');
    c.width = W * dpr;
    c.height = H * dpr;
    var g = c.getContext('2d');
    g.scale(dpr, dpr);
    g.translate(W / 2, H / 2);
    g.rotate(-Math.PI / 6);
    g.textAlign = 'center';
    g.textBaseline = 'middle';

    var lh = 30;
    var start = -((lines.length - 1) * lh) / 2;
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i];
      var a = Math.min(0.9, ln.a * (mul || 1));
      g.font = (ln.w || 500) + ' ' + (ln.s || 12.5) + 'px "Microsoft YaHei","PingFang SC","Noto Sans",system-ui,sans-serif';
      g.fillStyle = 'rgba(' + ln.rgb + ',' + a.toFixed(3) + ')';
      g.fillText(ln.t, 0, start + i * lh);
    }
    return { url: c.toDataURL('image/png'), w: W, h: H };
  }

  /** 依「层级 + 状态 + 查看人」决定水印文案（屏幕图与打印层共用同一套文案） */
  function linesFor(meta, me) {
    var who = (me && me.name ? me.name : '') +
      (me && me.no ? ' · ' + me.no : '') +
      ' · ' + today() + ' ' + clock();

    var NAVY = '31,57,100', RED = '163,45,45', GREY = '107,114,128';
    var lines;
    if (meta.status === 'obsolete') {
      lines = [
        { t: '作废 · HẾT HIỆU LỰC', rgb: RED, a: 0.24, s: 16 },
        { t: who, rgb: RED, a: 0.17, s: 11.5 }
      ];
    } else if (meta.status === 'draft') {
      lines = [
        { t: '草稿 · BẢN NHÁP', rgb: GREY, a: 0.22, s: 15 },
        { t: who, rgb: GREY, a: 0.15, s: 11.5 }
      ];
    } else if (meta.level === 1) {
      lines = [
        { t: '受控文件 · 未经批准不得复制', rgb: NAVY, a: 0.13, s: 17 },
        { t: 'TÀI LIỆU KIỂM SOÁT · KHÔNG SAO CHÉP', rgb: NAVY, a: 0.115, s: 15 },
        { t: who, rgb: RED, a: 0.15, w: 400, s: 13.5 }
      ];
    } else if (meta.level === 2) {
      lines = [
        { t: '受控文件 · CONTROLLED COPY', rgb: NAVY, a: 0.13, s: 17 },
        { t: 'TÀI LIỆU KIỂM SOÁT', rgb: NAVY, a: 0.115, s: 15 },
        { t: who, rgb: RED, a: 0.15, w: 400, s: 13.5 }
      ];
    } else {
      /* 三级：车间要看着做，少一行、字号略收，保证可读 */
      lines = [
        { t: '受控文件 · CONTROLLED COPY', rgb: NAVY, a: 0.125, s: 16 },
        { t: who, rgb: RED, a: 0.15, w: 400, s: 13.5 }
      ];
    }

    return lines;
  }

  /** 画到 canvas：屏幕纸页用 */
  function buildTile(meta, me, mul) {
    var who = (me && me.name ? me.name : '') +
      (me && me.no ? ' · ' + me.no : '') +
      ' · ' + today() + ' ' + clock();
    var sig = [meta.id, meta.version, meta.status, who, mul].join('|');
    if (tileCache[sig]) return tileCache[sig];
    var tile = makeTile(linesFor(meta, me), mul);
    tileCache[sig] = tile;
    return tile;
  }
  function addStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = [
      /* 水印是「盖在纸上」的，因此压在最上层；透明度已压到 10%~13%，不影响阅读。
         不去改正文元素的 position —— .oa-pgno 等本来就是绝对定位，碰了会跑位。 */
      '.' + WM_CLASS + '{position:absolute;inset:0;z-index:3;pointer-events:none;',
      'background-repeat:repeat;background-position:center top;',
      '-webkit-print-color-adjust:exact;print-color-adjust:exact}',
      /* 页码与编号要压在水印之上才看得清 */
      '.oa-sheet .oa-pgno{position:absolute;z-index:4}',
      /* 角落的编号版本：比页码更靠左，不抢页码位置 */
      '.oa-wm-mark{position:absolute;left:8mm;bottom:5mm;font:10px/1 system-ui,sans-serif;',
      'color:rgba(31,57,100,.46);letter-spacing:.3px;pointer-events:none;z-index:4}',
      '@media print{.oa-wm-layer{display:block !important}}',
      /* 打印稿（2026-11-07）：不再打印 .doc-print-only 的连续流，改为打印已经分好页的
         A4 纸页（.oa-sheet）。原因：连续流那条通道在 Chrome 里，跨页元素的水印底图/覆盖层
         只有第 1 页画得出来，后面全空白；纸页是「一页一个普通块」，水印层跟着自己那张纸走，
         页页都在。四级表单不加水印，也就不切通道，仍走原来的连续流。
         版面换算：纸页按屏幕原寸打印（210×297mm，内边距 20mm，正文 170mm），
         @page 边距归零，纸页贴边铺满 —— 缩放过一次会把正文挤窄。 */
      'body.oa-wm-print-sheets.doc-print-mode .doc-print-only{display:none !important}',
      'body.oa-wm-print-sheets .oa-paged-host{visibility:visible !important;position:absolute !important;',
      'left:0 !important;top:0 !important;width:210mm !important;background:#fff !important;',
      'padding:0 !important;border-radius:0 !important}',
      'body.oa-wm-print-sheets .oa-sheet{visibility:visible !important;width:210mm !important;',
      'height:297mm !important;min-height:0 !important;padding:20mm !important;margin:0 !important;',
      'box-shadow:none !important;zoom:1 !important;overflow:hidden !important;',
      'break-after:page;page-break-after:always}',
      'body.oa-wm-print-sheets .oa-sheet:last-child{break-after:auto;page-break-after:auto}',
      'body.oa-wm-print-sheets .oa-sheet .oa-pgno{display:block}'
    ].join('');
    document.head.appendChild(s);
  }

  var PAGE_ID = 'oa-print-page';

  /** 打印通道切换：有水印的等级（一~三级）走 A4 纸页打印，纸页自带水印层；
   *  四级表单保持原连续流通道（不加印）。 */
  function paintPrint(meta) {
    addStyle();
    var on = meta.level !== 4 && !!document.querySelector('.oa-sheet');
    document.body.classList.toggle('oa-wm-print-sheets', on);
    /* @page 只在「打印纸页」时挂上，且用完即撤：
       它是个全局规则，挂着会影响四级表单、质检单等其它打印的页边距。 */
    var pg = document.getElementById(PAGE_ID);
    if (on && !pg) {
      pg = document.createElement('style');
      pg.id = PAGE_ID;
      pg.textContent = '@page{size:A4;margin:0}';
      document.head.appendChild(pg);
    } else if (!on && pg) {
      pg.parentNode.removeChild(pg);
    }
  }

  function clearPrint() {
    document.body.classList.remove('oa-wm-print-sheets');
    var pg = document.getElementById(PAGE_ID);
    if (pg) pg.parentNode.removeChild(pg);
  }

  function paint(docId, tile, code, version) {
    var sheets = document.querySelectorAll('.oa-sheet');
    if (!sheets.length) return;
    addStyle();
    var mark = code ? code + '  Rev.' + (version || '') : '';
    for (var i = 0; i < sheets.length; i++) {
      var sh = sheets[i];
      var layer = sh.querySelector(':scope > .' + WM_CLASS);
      if (!layer) {
        layer = document.createElement('div');
        layer.className = WM_CLASS;
        sh.insertBefore(layer, sh.firstChild);
      }
      layer.style.backgroundImage = 'url(' + tile.url + ')';
      layer.style.backgroundSize = tile.w + 'px ' + tile.h + 'px';
      var mk = sh.querySelector(':scope > .oa-wm-mark');
      if (mark) {
        if (!mk) {
          mk = document.createElement('div');
          mk.className = 'oa-wm-mark';
          sh.appendChild(mk);
        }
        mk.textContent = mark;
      } else if (mk) {
        mk.parentNode.removeChild(mk);
      }
    }
  }

  function clear() {
    var ls = document.querySelectorAll('.' + WM_CLASS);
    for (var i = 0; i < ls.length; i++) ls[i].parentNode.removeChild(ls[i]);
    var ms = document.querySelectorAll('.oa-wm-mark');
    for (var j = 0; j < ms.length; j++) ms[j].parentNode.removeChild(ms[j]);
    clearPrint();
  }

  function tick() {
    var id = detailId();
    if (!id) { clear(); return; }
    if (isEditing()) { clear(); return; }
    /* 纸页还没生成时先不画屏幕水印；但打印层不依赖纸页（打印走 .doc-print-only），
       所以只要正文容器在，就继续往下走。 */
    if (!document.querySelector('.oa-sheet') && !document.querySelector('.doc-print-only')) return;

    var run = function () {
      var meta = metaCache[id];
      if (!meta) return;
      if (meta.level === 4) { clear(); return; }        // 四级表单不加
      paint(id, buildTile(meta, meCache, 1), meta.code, meta.version);
      paintPrint(meta);
    };

    if (metaCache[id] && meCache) { run(); return; }

    if (!fetching[id]) {
      fetching[id] = true;
      apiGet('/api/docs/' + id).then(function (d) {
        if (d) {
          metaCache[id] = {
            id: id, code: d.code, level: Number(d.level),
            status: d.status, version: d.current_version
          };
        }
        fetching[id] = false;
        if (!meCache) {
          return apiGet('/api/auth/profile').then(function (p) {
            meCache = p ? { name: p.real_name || p.username, no: p.employee_no || p.username } : { name: '', no: '' };
            run();
          });
        }
        run();
      }).catch(function () { fetching[id] = false; });
    }
  }

  /* 纸页由 oa-docx-pages.js 异步生成，用定时器 + 观察器双保险收敛 */
  var timer = setInterval(tick, 900);

  var mo = new MutationObserver(function () {
    if (mo._t) return;
    mo._t = setTimeout(function () { mo._t = null; tick(); }, 250);
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(function () {
        mo.observe(document.body, { childList: true, subtree: true });
        setTimeout(tick, 600);
      }, 300);
    });
  } else {
    mo.observe(document.body, { childList: true, subtree: true });
    setTimeout(tick, 600);
  }

  window.addEventListener('popstate', function () { setTimeout(tick, 120); });
  window.__oaWatermarkOff = function () {
    clearInterval(timer);
    mo.disconnect();
    clear();
  };
})();
