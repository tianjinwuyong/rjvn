import { useEffect, useRef, useState } from "react";
import { AlertCircle, CheckCircle, ScanBarcode, Truck } from "lucide-react";
import { t } from "../i18n";
import type { Locale } from "../../../../packages/shared-types/src/factory";
import { wmsApi } from "../api";
import type { ReceivingLot } from "../api";

const COPY = {
  "zh-CN": { format: "扫码格式：批次号 入库单号 物料编码 数量 供应商编码", qty: "收货数量必须大于 0", received: "已收货", hint: "必须使用已批准的入库单；系统自动核销单据数量" },
  "vi-VN": { format: "Định dạng: Số lô Số phiếu nhập Mã vật liệu Số lượng Mã NCC", qty: "Số lượng nhận phải lớn hơn 0", received: "Đã nhận", hint: "Phải dùng phiếu nhập đã duyệt; hệ thống tự đối trừ số lượng" },
  "en-US": { format: "Scan format: Lot Inbound-order Material Quantity Supplier", qty: "Received quantity must be greater than 0", received: "Received", hint: "An approved inbound order is required; quantities are reconciled automatically" },
} as const;

export function WmsReceiving({ locale }: { locale: Locale }) {
  const copy = COPY[locale];
  const [scanInput, setScanInput] = useState("");
  const [queue, setQueue] = useState<ReceivingLot[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);
  const [imageStorageKey, setImageStorageKey] = useState("");
  const [imageFileName, setImageFileName] = useState("");
  const [imageChecksum, setImageChecksum] = useState("");
  const [imageSizeBytes, setImageSizeBytes] = useState("");
  const scanRef = useRef<HTMLInputElement>(null);

  const refreshQueue = async () => {
    setLoading(true);
    try { setQueue((await wmsApi.getReceivingQueue()).items); }
    catch (error) { setQueue([]); setFeedback({ ok: false, msg: error instanceof Error ? error.message : String(error) }); }
    finally { setLoading(false); }
  };

  useEffect(() => { void refreshQueue(); scanRef.current?.focus(); }, []);

  const handleReceive = async () => {
    const parts = scanInput.trim().split(/[\s,]+/).filter(Boolean);
    if (parts.length < 5) { setFeedback({ ok: false, msg: copy.format }); return; }
    const [lotNo, inboundOrderNo, materialCode, qtyText, supplierCode] = parts;
    const qty = Number(qtyText);
    if (!Number.isFinite(qty) || qty <= 0) { setFeedback({ ok: false, msg: copy.qty }); return; }
    const hasImage = Boolean(imageStorageKey.trim());
    const imageSize = Number(imageSizeBytes);
    if (hasImage && (!imageFileName.trim() || !/^[a-f0-9]{64}$/i.test(imageChecksum.trim()) ||
        !Number.isInteger(imageSize) || imageSize < 1 || imageSize > 10 * 1024 * 1024)) {
      setFeedback({ ok: false, msg: "Image name, SHA-256 checksum and size (1-10 MB) are required" }); return;
    }
    setBusy(true); setFeedback(null);
    try {
      const receipt = await wmsApi.postReceive({ lot_no: lotNo, inbound_order_no: inboundOrderNo, material_code: materialCode,
        supplier_code: supplierCode, received_qty: qty, received_at: new Date().toISOString() });
      // Images are uploaded by the managed storage service first. Only the
      // resulting opaque key and verified metadata are linked to the lot here.
      const lotId = Number(receipt?.data?.id ?? receipt?.id);
      if (hasImage && lotId) {
        await wmsApi.registerReceivingImage(lotId, {
          storageKey: imageStorageKey.trim(), fileName: imageFileName.trim(),
          mimeType: "image/jpeg", sizeBytes: imageSize, checksum: imageChecksum.trim(),
          capturedBy: "MATERIAL_RECEIVER",
        });
      }
      await refreshQueue();
      setFeedback({ ok: true, msg: `${lotNo} — ${copy.received}` });
      setScanInput("");
      setImageStorageKey(""); setImageFileName(""); setImageChecksum(""); setImageSizeBytes("");
    } catch (error) { setFeedback({ ok: false, msg: error instanceof Error ? error.message : String(error) }); }
    finally { setBusy(false); scanRef.current?.focus(); }
  };

  const pendingCount = queue.filter((row) => row.iqc_status === "pending").length;
  return <div className="screen-stack">
    <section className="surface-panel">
      <div className="section-header"><div><h2>{t("wms.scanToReceive", locale)}</h2><p>{copy.hint}</p></div>
        <span className="badge badge-warning">{pendingCount} {t("iqc.pending", locale)}</span></div>
      <div className="scan-input"><ScanBarcode size={24}/><input ref={scanRef} value={scanInput}
        onChange={(event) => setScanInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && !busy && void handleReceive()}
        placeholder={copy.format} title={t("ui.scanInput", locale)} disabled={busy}/>
        <button className="action-button" type="button" disabled={busy || !scanInput.trim()} onClick={() => void handleReceive()}>
          <Truck size={16}/>{t("wms.confirmReceive", locale)}</button></div>
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr 0.7fr", gap: 8, marginTop: 10 }}>
        <input value={imageStorageKey} onChange={(e) => setImageStorageKey(e.target.value)}
          placeholder="Supplier inspection image storage key (optional)" aria-label="Image storage key" />
        <input value={imageFileName} onChange={(e) => setImageFileName(e.target.value)}
          placeholder="File name" aria-label="Image file name" />
        <input value={imageChecksum} onChange={(e) => setImageChecksum(e.target.value)}
          placeholder="SHA-256 checksum" aria-label="Image checksum" />
        <input value={imageSizeBytes} onChange={(e) => setImageSizeBytes(e.target.value)}
          placeholder="Bytes" inputMode="numeric" aria-label="Image size in bytes" />
      </div>
      <small style={{ display: "block", marginTop: 4, opacity: .7 }}>
        Upload the photo through managed storage, then paste its key and SHA-256 here; data URLs and local paths are not accepted.
      </small>
      {feedback && <div style={{ marginTop:8,padding:"6px 12px",borderRadius:6,background:feedback.ok?"var(--ok-bg)":"var(--danger-bg)",color:feedback.ok?"var(--ok)":"var(--danger)",display:"flex",gap:6,alignItems:"center" }}>
        {feedback.ok?<CheckCircle size={14}/>:<AlertCircle size={14}/>} {feedback.msg}</div>}
    </section>
    <section className="surface-panel"><div className="section-header"><div><h2>{t("wms.receivingQueue", locale)}</h2><p>{t("section.queue", locale)}</p></div></div>
      <div className="table-shell"><table><thead><tr><th>{t("wms.poNumber",locale)}</th><th>{t("common.material",locale)}</th><th>{t("common.supplier",locale)}</th><th>{t("common.qty",locale)}</th><th>{t("common.location",locale)}</th><th>{t("common.receiver",locale)}</th><th>{t("common.time",locale)}</th><th>{t("table.status",locale)}</th></tr></thead>
      <tbody>{loading?<tr><td colSpan={8}>{t("common.loading",locale)}</td></tr>:queue.length===0?<tr><td colSpan={8}>{t("common.noData",locale)}</td></tr>:queue.map((row)=><tr key={row.id}>
        <td><strong>{row.po_no}</strong><br/><code>{row.lot_no}</code></td><td><strong>{row.material_code}</strong><small style={{display:"block"}}>{row.material_name_zh}</small></td>
        <td>{row.supplier_name_zh??row.supplier_code}</td><td>{row.received_qty.toLocaleString()}</td><td><code>{row.location_code}</code></td><td>{row.receiver_name}</td><td>{new Date(row.received_at).toLocaleString()}</td>
        <td><span className={`badge badge-${row.has_open_issues?"danger":row.iqc_status==="pending"?"warning":"ok"}`}>{row.has_open_issues?t("wms.hasIssues",locale):t(row.iqc_status==="pending"?"iqc.pending":"iqc.released",locale)}</span></td></tr>)}</tbody></table></div>
    </section>
  </div>;
}
