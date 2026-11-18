import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs/promises";

const source = "C:/Users/tianj/Desktop/越南工厂瑞晶/dc/MES流程(1).xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const sheets = await workbook.inspect({kind:"sheet",include:"id,name",maxChars:12000});
console.log("SHEETS\n"+sheets.ndjson);
const overview = await workbook.inspect({kind:"workbook,table,region",maxChars:40000,tableMaxRows:80,tableMaxCols:24,tableMaxCellChars:300});
console.log("OVERVIEW\n"+overview.ndjson);
for (const name of ["手动线","自动线"]) {
  const sheet=workbook.worksheets.getItem(name);
  const used=sheet.getUsedRange();
  console.log(`SHEET:${name}\n${JSON.stringify(used.values)}`);
  const drawings=await workbook.inspect({kind:"drawing",sheetId:name,maxChars:100000});
  console.log(`DRAWINGS:${name}\n${drawings.ndjson}`);
  const image=await workbook.render({sheetName:name,autoCrop:"all",scale:1.5,format:"png"});
  await fs.writeFile(`route-${name}.png`,new Uint8Array(await image.arrayBuffer()));
}
