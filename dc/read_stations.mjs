import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const path = "C:/Users/tianj/Desktop/越南工厂瑞晶/dc/stations.xlsx";
const input = await FileBlob.load(path);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheets = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 3000,
});
console.log("SHEETS");
console.log(sheets.ndjson);
const overview = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 12000,
  tableMaxRows: 40,
  tableMaxCols: 20,
  tableMaxCellChars: 120,
});
console.log("OVERVIEW");
console.log(overview.ndjson);
