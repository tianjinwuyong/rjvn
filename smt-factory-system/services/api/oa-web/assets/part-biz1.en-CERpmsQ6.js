const e=[{id:"equip",title:"Equipment",sections:[{id:"equip-ledger",title:"Equipment Ledger",body:`<p>The equipment ledger is the master record: it stores the basic data, the maintenance and external-calibration cycles and the inspection frequency, and it feeds inspection template binding, card printing, scan-to-inspect and stocktakes. Entry: menu "Equipment → Equipment Ledger".</p>
<ol>
<li>Add: click <strong>New Equipment</strong> in the top right; fill in at least the asset number and the equipment name, then save.</li>
<li>Bulk import: click <strong>Bulk Import</strong> → <strong>Download Template</strong>, fill in the columns and upload the Excel file; rows are upserted by asset number (updated if present, inserted if not).</li>
<li>Export: exports the whole ledger as Excel using the current filters.</li>
<li>Details: click an asset number to open the drawer with the history timeline, inspection records and calibration records.</li>
</ol>
<table>
<thead><tr><th>Common fields</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Asset No. / Equipment Name</td><td>Required. The asset number is the upsert key for imports and the content of the QR code on the equipment card</td></tr>
<tr><td>Department / Location</td><td>Used to scope a stocktake by department or by location</td></tr>
<tr><td>Maintenance Cycle (days) / External Calibration Cycle (days)</td><td>Drives the next maintenance and next external calibration dates</td></tr>
<tr><td>First External Calibration</td><td>Entered by hand; not included in the automatic calculation</td></tr>
<tr><td>Inspection Frequency / Interval</td><td>Daily / weekly / monthly / quarterly / yearly plus an interval; used to generate inspection tasks</td></tr>
<tr><td>Status</td><td>In Use / Under Repair / Disabled / Scrapped</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> Status is a single value, not an enable/disable switch. Disabled and scrapped equipment is still recognised and logged during scan-to-inspect and stocktakes. Deletion cannot be undone.</blockquote>`},{id:"equip-tpl",title:"Inspection Templates (Excel import + rich text)",body:`<p>Inspection templates are maintained by <strong>importing an Excel file to create the draft and then editing it as rich text</strong> — the draft itself is the template, so there is no structured list of check items to configure. Entry: menu "System Management → Inspection Templates".</p>
<ol>
<li>Click <strong>New Template</strong> and fill in the template number, the template name and the Vietnamese name.</li>
<li>You must select the <strong>equipment</strong>: a template is bound to one piece of equipment (required), and tasks are dispatched per equipment.</li>
<li>Optionally set the <strong>inspection frequency</strong> (daily / weekly / monthly / quarterly / yearly) and the <strong>interval</strong>; without a frequency no tasks are dispatched.</li>
<li>Click <strong>Import Excel</strong> and choose an .xlsx / .xls file. If the workbook has several sheets, pick the one to convert; merged cells become merged header cells.</li>
<li>Fine-tune the draft in the rich text editor (tables / text / images); the archived original Excel can be downloaded for comparison.</li>
<li>Click <strong>Save Template</strong>; you can later enable, disable or delete it from the list.</li>
</ol>
<blockquote><strong>Note:</strong> ① A template must be bound to equipment — it cannot be saved without one. ② Task dispatch uses only the <strong>template-level frequency</strong>; a frequency written inside the Excel draft is just text and does not drive tasks. ③ A template already referenced by inspection records cannot be deleted. ④ Once disabled, the template stops producing tasks and disappears from the template picker on the fill page.</blockquote>`},{id:"equip-task",title:"Inspection Tasks and Filling",body:`<p>Inspection tasks are derived from the equipment and the template frequency, and are carried out on a rich text inspection page. The task list is under menu "Equipment → Maintenance Tasks" (the page title is Inspection Tasks); the fill and record pages are under the Quality menu.</p>
<ol>
<li>The list can be filtered by task status and date range. <strong>Generate Tasks</strong> dispatches tasks by template frequency (equipment management permission required).</li>
<li>For an unfinished task click <strong>Start Inspection</strong>; the inspection page opens with that task's template and equipment already loaded.</li>
<li>Check the equipment on the page and fill in the draft item by item; <strong>Take Photo</strong> inserts a site photo into the table.</li>
<li><strong>Save Draft</strong> lets you continue later; after <strong>Submit</strong> the content is locked.</li>
<li>When something is wrong, tick <strong>Mark Abnormal</strong>, give the reason, then click <strong>Report Equipment Repair</strong>.</li>
</ol>
<table>
<thead><tr><th>Item</th><th>Values</th></tr></thead>
<tbody>
<tr><td>Task status</td><td>Pending / Done / Overdue</td></tr>
<tr><td>Task type</td><td>Inspection / Maintenance / External Calibration / Repair</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> Inspection follows the same rule as line patrol and first article: <strong>if the table contains a SPEC the verdict is automatic</strong> — any NG makes the whole record NG, and empty cells do not block OK (see the SPEC chapter). <strong>Reporting an anomaly stays manual</strong>: the person filling in marks it and raises the equipment repair order in one click; the system does not open one by itself. After submission the body is locked but <strong>photos can still be attached</strong>, which helps when evidence has to be taken on site.</blockquote>`},{id:"equip-calib",title:"Calibration and Alerts",body:`<p>Calibration records the external-calibration plan and certificates of each piece of equipment, and escalates reminders as the due date approaches or passes. The Alert Center can run a scan manually and push notifications by tier.</p>
<p><strong>Calibration Plan</strong> (menu "Equipment → Calibration Plan")</p>
<ol>
<li>Click <strong>New Calibration Plan</strong>, select the equipment and fill in the planned date, the calibration body, the certificate number and so on; save.</li>
<li>The list is graded by days remaining — normal / within 30 days / within 10 days / within 7 days / within 3 days or overdue — with different tags and background colours.</li>
<li>When calibration is done click <strong>Mark Done</strong> and enter the actual date and result; saving writes the result back to the equipment and recalculates the next external calibration date.</li>
</ol>
<p><strong>Alert Center</strong> (menu "Equipment → Alert Center") lists the equipment due within 30 days, the alerts already sent, and a <strong>Scan Now</strong> button.</p>
<table>
<thead><tr><th>Days left</th><th>Notify level</th></tr></thead>
<tbody>
<tr><td>≤ 30 days</td><td>Assignee / department head</td></tr>
<tr><td>≤ 10 days</td><td>Engineering manager</td></tr>
<tr><td>≤ 7 days</td><td>Deputy GM</td></tr>
<tr><td>≤ 3 days / overdue</td><td>General manager</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> The alert chain applies <strong>only to external calibration</strong>, not to equipment inspection, and each equipment is notified once per tier. The alert scan is <strong>triggered manually</strong>.</blockquote>`},{id:"equip-label",title:"Printing Equipment Cards",body:`<p>The equipment card is a 70mm × 50mm thermal label stuck on the equipment. It carries the basic fields plus a QR code (the asset number) and is used for scan-to-inspect on site.</p>
<ol>
<li>Single card: in the Equipment Ledger row actions click <strong>Print Card</strong>; the browser opens the print window.</li>
<li>Batch: tick several rows (left checkbox column) → <strong>Batch Print Cards</strong> in the toolbar → one print window with N pages, one equipment per page.</li>
<li>Choose the label printer in the print dialog and print.</li>
</ol>
<table>
<thead><tr><th>Card field</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Asset No. / Equipment Name / Model</td><td>Taken from the equipment ledger</td></tr>
<tr><td>Department / Purchase Date / First External Calibration</td><td>Dates use a slash format, for printing only</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> ① Dates on the card use a <strong>slash format</strong> (printing scope only) and therefore differ from other pages. ② <strong>Batch printing is capped at 50 labels</strong> per run; beyond that you are asked to split the batch. ③ The browser must allow pop-ups; if it blocks them, allow them and retry. ④ With an empty asset number no QR code is produced and the layout degrades gracefully (the number shows as "—").</blockquote>`},{id:"equip-scan",title:"Scan to Inspect",body:`<p>Scan-to-inspect is meant for the shop floor: scan the QR code on the equipment card with a phone, or type the asset number or read it with a barcode scanner, and go straight to the inspection page.</p>
<ol>
<li>Open the mobile inspection entry in a phone browser (<code>/m/equip</code>, which redirects to the inspection fill page).</li>
<li>The scan panel offers two modes: the <strong>camera</strong>, or <strong>Input / Scanner</strong> for manual entry.</li>
<li>Check the equipment info, pick an available template, fill in the draft and submit.</li>
</ol>
<blockquote><strong>Note:</strong> ① <strong>Camera scanning requires HTTPS (port 8443)</strong>; over plain HTTP, or when no camera is available, the panel falls back to Input / Scanner instead of showing a blank screen. ② Clear messages are shown when the equipment does not exist, is disabled or scrapped, has no usable template, or has no executable task. ③ The exact entry and interaction follow the actual screen.</blockquote>`},{id:"equip-stocktake",title:"Scan-based Stocktake",body:`<p>An equipment stocktake is a project: create the task (name, period, scope), let the general manager approve it twice (publish and closing), then counters scan with their phones while the system reports progress, differences and a report.</p>
<ol>
<li>Menu "Equipment → Equipment Stocktake" → <strong>New Stocktake</strong>: enter the name and period and choose the scope (all equipment / by department / by location); the page shows the estimated equipment count live.</li>
<li>Choose <strong>Save Draft</strong> or <strong>Submit</strong>. After submission the general manager handles it in My Approvals, and the task is published once approved.</li>
<li>Counters open <code>/m/stocktake</code> on their phone (the desktop details page can copy the link), pick the task and start scanning; progress comes from the server, and scanning the same item twice does not inflate the count.</li>
<li>When counting is done click <strong>Submit for Closing</strong> → general manager approves → the difference list is locked once approved.</li>
<li>Click <strong>Export Report</strong> to download the Excel report.</li>
</ol>
<table>
<thead><tr><th>Status</th><th>Difference type</th></tr></thead>
<tbody>
<tr><td>Draft / Pending Approval / In Progress / Closing Approval / Finished / Rejected</td><td>Verified / Not Scanned / Out of Scope / Abnormal Status</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> ① Publishing is <strong>blocked when the estimated count is 0</strong>; adjust the scope first. ② "Not Scanned" is only finalised when the stocktake ends. ③ Phone scanning needs HTTPS (8443) to reach the camera; otherwise it falls back to manual input or a barcode scanner.</blockquote>`}]},{id:"quality",title:"Quality",sections:[{id:"qc-ipqc",title:"IPQC Line Patrol",body:`<p>Line patrol follows one pattern — <strong>Excel template → online rich text draft → fill in rich text → mark anomalies by hand → raise a quality issue report in one click</strong> — the same one used by first article and inspection. Fill page entry: menu "Quality → Report Line Patrol"; records are under Line Patrol Records.</p>
<ol>
<li>Select a patrol template; the system loads that template's rich text draft.</li>
<li>Fill in the draft: edit tables directly, add text, insert site photos into tables.</li>
<li><strong>Save Draft</strong> lets you continue later; after <strong>Submit</strong> the content is locked.</li>
<li>To report an anomaly: tick <strong>Mark Abnormal</strong>, enter the abnormality note, then click <strong>Report Quality Issue</strong>; the list and details then offer Open Issue.</li>
</ol>
<blockquote><strong>Note:</strong> Line patrol and first article also provide SPEC auto-verdict and three-level statistics (see the inspection intelligence chapter). The <strong>pass rate, NG rate and closure rate on the record list are all based on manual reporting</strong> — the closure rate divides by raised quality issue reports, not by item-level verdicts. Tasks are produced by <strong>Generate Today's Tasks</strong>, one per day for each enabled template that has a line, and the notification links straight to the fill page.</blockquote>`},{id:"qc-fai",title:"First Article (FAI)",body:`<p>First article uses the same pattern and screens as line patrol; the differences are the header fields and the statistics basis — patrol keys off the line, first article off the product code and process. Fill page entry: menu "Quality → Report First Article"; records are under FAI Records.</p>
<ol>
<li>Select an FAI template (the header carries the product code and process) to load the draft.</li>
<li>Fill in the table, insert site photos, then save a draft or submit directly.</li>
<li>Tick <strong>Mark Abnormal</strong>, add the note, then click <strong>Report Quality Issue</strong>.</li>
</ol>
<blockquote><strong>Note:</strong> First article and line patrol both raise a <strong>quality issue report</strong>, whereas inspection raises an equipment repair order — the two are different. First article has <strong>no task table</strong>, so the record page does not show the task completion card. SPEC auto-verdict and the three-level statistics apply here as well (see the dedicated chapter).</blockquote>`},{id:"qc-template",title:"Inspection Templates and Custom Fields",body:`<p>Both patrol and FAI templates are maintained by importing Excel and editing the rich text draft; the entries are under menu "System Management → Line Patrol Templates / FAI Templates". The header fields differ: patrol uses line and shift, first article uses product code and process.</p>
<ol>
<li>Click <strong>New Template</strong> and fill in the template number and name; the Vietnamese name and description are optional.</li>
<li>Click <strong>Import Excel</strong>; if the workbook has several sheets, pick the one to convert. Merged cells are kept as merged header cells.</li>
<li>Adjust the draft in the rich text editor and replace the archived original Excel if needed.</li>
<li>Click <strong>Save Template</strong>; you can then enable, disable or delete it.</li>
</ol>
<p><strong>Template custom fields</strong>: menu "System Management → Template Custom Fields" (permission required). Custom horizontal fields (customer, model, work order number and so on) can be added to templates, scoped to inspection, patrol or FAI templates and to their items.</p>
<table>
<thead><tr><th>Setting</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Field key</td><td>Stable English key generated by the system</td></tr>
<tr><td>Label (Chinese) / Label (Vietnamese)</td><td>Bilingual labels</td></tr>
<tr><td>Field type</td><td>Text / number / date / dropdown (dropdowns need bilingual options)</td></tr>
<tr><td>Built-in / Custom</td><td>Built-in fields can be renamed, disabled or reordered but not deleted; key and type cannot be changed</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> ① Inspection templates do not use custom fields (the draft is the template), and a template referenced by records cannot be deleted. ② Item-level custom fields are mainly for configuration; whether values are stored follows the actual screen.</blockquote>`},{id:"qc-record",title:"Records, Anomaly Reporting and Export",body:`<p>Patrol, first article and inspection records are all reviewed here: filtering, read-only rich text details, Word export, PDF printing and statistics cards based on manual reporting. Entry: menu "Quality → Line Patrol Records / FAI Records / Inspection Records".</p>
<ol>
<li>Filter by date range, status (draft / submitted) and an abnormal-only switch; patrol can be filtered by line and inspection by equipment.</li>
<li><strong>View Details</strong> opens a drawer with the read-only body (tables and images as they were filled in).</li>
<li><strong>Word</strong> in the row exports a .doc file; <strong>PDF</strong> goes through the browser print dialog and Save as PDF.</li>
<li>Records already reported show an Issue or a repair-order-number link that opens the workflow form.</li>
</ol>
<table>
<thead><tr><th>Column</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>Template</td><td>Snapshot of the template name (still readable after a rename)</td></tr>
<tr><td>Line / Product Code / Equipment</td><td>Patrol shows the line, first article the product code, inspection the equipment</td></tr>
<tr><td>Filled By / Status / Conclusion</td><td>The conclusion is OK or NG (reported) and is set by manual marking</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> ① Every statistics card (task completion, pass rate, NG rate, closure rate) <strong>is based on manual reporting</strong>. ② PDF export uses the browser print dialog — choose Save as PDF there. ③ After submission the body is locked, but photos can still be added.</blockquote>`}]},{id:"doc",title:"System Documents",sections:[{id:"doc-ledger",title:"Controlled Document Overview",body:`<p>The controlled document overview lists the issued controlled documents and is the shop-floor entry for the documents in force. Entry: menu "System Documents → Controlled Documents"; the page also links to the Public Drive and the Ledger.</p>
<ol>
<li>Filter by keyword, category, level or classification.</li>
<li>Click a row to open the document details: bilingual body, version history, controlled original and related documents.</li>
<li>Click <strong>Ledger</strong> to open the Document Ledger, where you can switch between the seven ledger types and export Excel in the current interface language.</li>
</ol>
<table>
<thead><tr><th>Ledger type</th><th>Content</th></tr></thead>
<tbody>
<tr><td>Controlled Documents</td><td>List of controlled documents (issued ones only by default)</td></tr>
<tr><td>Issue &amp; Return / Obsolete List / Destruction Records</td><td>Process records of issuing and returning, obsoleting and destroying</td></tr>
<tr><td>Borrowing Log / External Documents / Review Records</td><td>Borrowing, external documents and periodic review records</td></tr>
</tbody>
</table>
<blockquote><strong>Note:</strong> ① "Issued" means the document status is Issued, and <strong>this page shows issued documents only</strong> by default. ② Drafts and documents under review are found in the Document Ledger. ③ Documents classified as Secret can only be previewed online (watermarked); <strong>download and printing are blocked</strong> by server-side checks.</blockquote>`},{id:"doc-issue",title:"Document Issue Flow",body:`<p>Controlled issue is the approval flow that formally releases a document to the relevant departments and switches it to Issued. Start it from the document details page (draft state) or from the issue page.</p>
<ol>
<li>Open the document details → <strong>Start Controlled Issue</strong> → choose the first departments to receive it (the issue scope, also used as the training audience).</li>
<li>The chain runs: <strong>format check by the document clerk → countersign by the four departments plus the system engineer (≥4 people) → department head review → conditional approval</strong> (management manual → general manager; product documents → department supervisor; others → management representative) <strong>→ issue execution reply → issue confirmation and closure</strong>.</li>
<li>When the flow finishes the document becomes Issued and appears in the controlled document overview.</li>
<li>The step bar and node timeline can be followed on the document details or on the Controlled Issue page.</li>
</ol>
<blockquote><strong>Note:</strong> ① Issuing and obsoleting are both <strong>approval flows</strong>; you handle the approvals in My Approvals. ② The issue execution reply step asks for the stamp, distribution and registration number; the flow only completes after closure. ③ Level 4 forms may skip review and be issued directly, which is a special case (noted next to the button).</blockquote>`},{id:"doc-obsolete",title:"Document Obsolete Flow",body:`<p>Obsoleting an issued document is no longer a one-click action; it goes through an approval flow built like the issue flow, and the document only becomes Obsoleted once the flow is closed. Start it with <strong>Start Obsolete Request</strong> on an issued document's details page.</p>
<ol>
<li>Open an issued document → <strong>Start Obsolete Request</strong> and <strong>enter the reason</strong> (required); if a replacement exists, enter its document number.</li>
<li>Chain: <strong>verification by the document clerk → countersign by the four departments plus the system engineer → department head review → conditional approval → obsolete execution reply (recall / destruction / registration number) → obsolete confirmation and closure</strong>.</li>
<li>While the flow is in flight the document <strong>still shows as Issued</strong> (the flow instance carries the in-flight state); it becomes Obsoleted only after approval and is recorded in the Obsolete List.</li>
</ol>
<blockquote><strong>Note:</strong> ① A document with a pending obsolete request cannot start another one. ② Obsoleting cannot be undone. ③ The obsolete list is under menu "System Documents → Obsolete List".</blockquote>`},{id:"doc-borrow",title:"Borrowing and Distribution",body:`<p>This chapter covers the issue-and-return and the borrowing records; both are viewed and exported as ledgers.</p>
<p><strong>Issue &amp; Return records</strong>: menu "System Documents → Issue &amp; Return". Columns: record type, document number, version, department, holder, copies, action date, operator, reason.</p>
<p><strong>Borrowing log</strong>: dedicated entry <code>/doc-borrow</code>, or switch the type to Borrowing Log inside the Document Ledger. Columns: document number, version, borrower, purpose, borrow date, due date, return date, status.</p>
<ol>
<li>Open the relevant ledger and filter by date or keyword.</li>
<li>Click <strong>Export Excel</strong> in the top right; the headers follow the current interface language.</li>
</ol>
<blockquote><strong>Note:</strong> ① Borrowing actions require the document borrowing permission. ② This page focuses on <strong>querying and exporting the ledger</strong>; the exact entries for starting a borrow or registering a return follow the actual screen.</blockquote>`}]}];export{e as default};
