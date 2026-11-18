
import { pathToFileURL } from "url";
import fs from "fs";

const input = process.argv[2];
const output = process.argv[3];
const distDir = "C:/Users/tianj/Desktop/越南工厂瑞晶/dc/node_modules/dwg2dxf/dist/";
const { default: MainModuleFactory } = await import(pathToFileURL(distDir + "dwg2dxf-wasm.js").href);
const wasmBinary = new Uint8Array(fs.readFileSync(distDir + "dwg2dxf-wasm.wasm"));
const Module = await MainModuleFactory({ wasmBinary, print: (t) => console.log("out:", t), printErr: (t) => console.error("err:", t) });

Module.FS.writeFile("/a.dwg", new Uint8Array(fs.readFileSync(input)));
const rc = Module._dwg2dxf();
console.log("_dwg2dxf rc:", rc);
const listing = Module.FS.readdir("/").join(",");
console.log("FS:", listing);
for (const cand of ["/b.dxf", "/a.dxf", "/out.dxf", "/output.dxf"]) {
  try { const out = Module.FS.readFile(cand); console.log("found", cand, out.length); fs.writeFileSync(output, Buffer.from(out)); process.exit(0); } catch {}
}
process.exit(rc || 1);
