import{m as n,p as s}from"./sheetTable-CRcZrJ9k.js";import{a as o}from"./richText-BnnE4cbP.js";
/* 文件解析（导入正文 / 原件预览 共用）
   2026-10-30 改：docx 优先走服务端保真转换 /api/doc-import/docx
   —— 原实现是 mammoth.convertToHtml 默认参数，只保留语义，字号/字体/颜色/
      对齐/缩进/行距/单元格边框全丢，121 页手册导入后变成一堆同样大小的黑字。
   失败（离线/接口异常/格式异常）自动退回 mammoth，行为与改造前一致，不会阻断导入。 */
function c(e){const t=String(e||"").toLowerCase().match(/\.([a-z0-9]+)(\?|$)/);return t?t[1]:""}
function u(e){return e==="docx"?"docx":["xlsx","xlsm","csv"].includes(e)?"excel":e==="pdf"?"pdf":["png","jpg","jpeg","gif","webp","bmp"].includes(e)?"image":["txt","md","log","json"].includes(e)?"text":"unsupported"}
function tk(){try{return localStorage.getItem("oa_token")||""}catch(_){return""}}
async function k(e){const r=await fetch("/api/doc-import/docx",{method:"POST",headers:{"Content-Type":"application/octet-stream","Authorization":"Bearer "+tk()},body:e});if(!r.ok)throw new Error("HTTP "+r.status);const t=await r.json();if(!t||t.code!==0||!t.data||!t.data.html)throw new Error(t&&t.msg||"转换失败");return t.data.html}
async function f(e,r){if(r==="docx"){try{const t=await k(e);if(t)return{html:o(t)}}catch(_){}const t=await n.convertToHtml({arrayBuffer:e});return{html:o(t.value||"")}}return r==="excel"?{sheets:s(e)}:r==="text"?{text:new TextDecoder().decode(e)}:{}}
export{c as e,u as k,f as p};
