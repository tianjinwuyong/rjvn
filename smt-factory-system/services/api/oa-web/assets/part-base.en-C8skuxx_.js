const e=[{id:"start",title:"Getting Started",sections:[{id:"start-login",title:"Signing In and Changing the Initial Password",body:`<p>You must sign in before using the system. If this is the first sign-in for the account, the system requires you to change the initial password first.</p>
<ol>
  <li>Open the system address (the HTTP port on desktop; the exact address is announced by your administrator).</li>
  <li>Enter the <strong>username</strong> and <strong>password</strong>, then click <strong>Sign In</strong>.</li>
  <li>If this is your first sign-in, the page switches to "First Sign-in · Change Password". Fill in the <strong>initial password</strong>, the <strong>new password</strong> and the <strong>confirmation</strong> in order, then click <strong>Change and Continue</strong>.</li>
</ol>
<p>The new password must be at least <strong>8 characters</strong> long; mixing letters and digits is recommended, and the two entries must match.</p>
<blockquote><strong>Note:</strong> Until the initial password is changed, every page redirects back to the change-password page. If you forget your password, ask the administrator to reset it under "Org &amp; Position Management".</blockquote>`},{id:"start-nav",title:"Navigating the Interface and the Top Bar",body:`<p>After signing in you land on the main screen: the grouped menu is on the left, the top bar runs along the top right, and a breadcrumb under the page title shows where you are.</p>
<h4>Left menu</h4>
<ul>
  <li>Group cards expand and collapse; click a group title to toggle it. The number on the right of a group is how many menu items it contains.</li>
  <li>A <strong>Search menu</strong> box sits above the menu; typing filters items in the current language.</li>
  <li>When a group has many items, only the first few show while collapsed, with <strong>Show N more</strong> underneath.</li>
  <li>Opening a page expands its group automatically and highlights the current item.</li>
</ul>
<h4>Top bar (left to right)</h4>
<table>
  <thead><tr><th>Element</th><th>Purpose</th></tr></thead>
  <tbody>
    <tr><td>Collapse / expand</td><td>Hides or shows the left menu</td></tr>
    <tr><td>Home</td><td>Returns to "My Workspace"</td></tr>
    <tr><td>Language button (中 / VI / EN)</td><td>Switches between Chinese, Vietnamese and English</td></tr>
    <tr><td>Refresh to-dos</td><td>Manually refreshes the to-do count and notifications</td></tr>
    <tr><td>Notification bell</td><td>Shows message notifications; a red dot marks unread items</td></tr>
    <tr><td>User menu</td><td>My Settings, Sign out</td></tr>
  </tbody>
</table>`},{id:"start-lang",title:"Switching the Interface Language",body:`<p>The system provides three interface languages: <strong>Chinese</strong>, <strong>Vietnamese</strong> and <strong>English</strong>.</p>
<ol>
  <li>Click the language button in the top bar (it shows "中", "VI" or "EN").</li>
  <li>Pick "中文", "Tiếng Việt" or "English" from the dropdown; the interface switches immediately, without a page reload.</li>
</ol>
<ul>
  <li>The sign-in page and the first sign-in page also have a language switch in the top right. Before signing in the choice is stored on this device only; after signing in it is saved to your account.</li>
  <li>"My Settings" offers the same switch.</li>
  <li>The language preference is stored on your account and synced between desktop and mobile.</li>
</ul>
<blockquote><strong>Note:</strong> Interface text (menus, buttons, form labels) follows the selected language, and the built-in business dictionaries (leave types, punch anomaly types and so on) are available in Chinese and Vietnamese.</blockquote>`},{id:"start-mobile",title:"Using a Phone or Tablet",body:`<p>Open the same system address in a phone or tablet browser; below roughly 768px wide the layout adapts automatically.</p>
<ul>
  <li>On narrow screens the left menu becomes a drawer; open it with the button in the top left and it closes as soon as you pick an item.</li>
  <li>Tables and forms resize to the screen; wide tables scroll horizontally.</li>
</ul>
<p>Phones and tablets mainly cover these four tasks (the actual screens may differ slightly):</p>
<ol>
  <li>Submitting workflow forms (start a form, fill it in and submit)</li>
  <li>Approvals (working through to-dos, approving / rejecting and so on)</li>
  <li>Equipment inspection (viewing tasks, filling items one by one, scanning to inspect)</li>
  <li>IPQC line patrol (filling the template and submitting a patrol record)</li>
</ol>
<blockquote><strong>Note:</strong> <strong>Camera scanning on a phone requires HTTPS.</strong> The system offers HTTPS on port 8443 with a self-signed certificate; the browser warns that the connection is not private the first time — continue to the site. Over plain HTTP the camera is unavailable, so use a barcode scanner or type the number manually.</blockquote>`}]},{id:"common",title:"Common Operations",sections:[{id:"common-list",title:"Filtering, Paging and Searching Lists",body:`<p>Every list page (to-dos, forms, ledgers, attendance, equipment and so on) follows the same pattern, so learning one covers them all.</p>
<ol>
  <li>Set the conditions at the top: keyword, date range, dropdown values and so on.</li>
  <li>Click <strong>Search</strong> to run the query; click <strong>Reset</strong> to clear the conditions and re-query.</li>
  <li>Pressing Enter inside the keyword box also runs the search.</li>
  <li>The bottom shows <strong>N records in total</strong>; when the count exceeds one page, <strong>Previous / page numbers / Next</strong> appear (a few lists only show paging after you click Search).</li>
  <li>On many lists a click anywhere on the row opens the details; the action column also has View Details.</li>
</ol>
<blockquote><strong>Note:</strong> Changing a filter sends you back to page 1, and an empty list shows "No data".</blockquote>`},{id:"common-colwidth",title:"Dragging Column Widths",body:`<p>Column widths on every list can be dragged, which helps with long content.</p>
<ol>
  <li>Move the pointer onto the divider between two headers; the cursor changes to a left-right arrow.</li>
  <li>Press and drag left or right to resize the column on the left.</li>
</ol>
<ul>
  <li><strong>The last column can be dragged too.</strong></li>
  <li>Resizing relies on the table borders, which the system lists have by default.</li>
  <li>Some columns have a minimum width and stop shrinking at that point.</li>
</ul>
<blockquote><strong>Note:</strong> Width changes are temporary; refreshing or reopening the page may restore the defaults (the actual behaviour prevails).</blockquote>`},{id:"common-form",title:"Filling Forms and Validation Messages",body:`<p>Form pages (workflow forms, templates, equipment, attendance and so on) share one form component and the same validation rules.</p>
<ul>
  <li>Required fields carry a red <strong>*</strong> before the label.</li>
  <li>The action bar at the bottom updates as you type: "To fill: field names…" while something is missing, "All filled" once complete.</li>
  <li>Clicking <strong>Submit</strong> with a required field empty lists the missing fields and does not submit.</li>
  <li><strong>Save Draft</strong> skips required-field validation, so you can save now and continue later.</li>
</ul>
<h4>Detail tables</h4>
<ul>
  <li>Click <strong>+ Add row</strong> to add a row; use Delete at the end of a row to remove it.</li>
  <li>Blank rows are dropped on submit — only rows with content count.</li>
  <li>When the columns include quantity and unit price, the system calculates the row subtotal and the grand total.</li>
</ul>
<p>Attachments: a single file must not exceed 100MB. If an upload fails you get a message; please upload again.</p>`},{id:"common-notify",title:"Notifications and To-do Reminders",body:`<p>To-dos and notifications are two different things: to-dos are forms that need your approval or action; notifications are system messages.</p>
<ul>
  <li>The <strong>bell</strong> in the top bar shows a red dot when messages are unread. Open it to see recent messages; unread ones are bold with a red dot. Clicking one marks it read and opens the related form.</li>
  <li><strong>Mark all read</strong> in the top right of the panel clears every unread message at once.</li>
  <li>The <strong>Refresh</strong> button in the top bar manually refreshes the to-do count and notifications.</li>
  <li>The system also refreshes to-dos and notifications silently every 2 minutes, so just leave the page open.</li>
  <li>The to-do count also appears in the left menu and on the home page; the list itself is under "My Workspace → My Approvals".</li>
</ul>
<blockquote><strong>Note:</strong> If new to-dos do not appear for a long time, click Refresh in the top bar first; if nothing changes, check your network connection.</blockquote>`}]},{id:"hr",title:"HR & Attendance",sections:[{id:"hr-punch",title:"Attendance Punching",body:`<p>Punch data comes from the factory time clocks; the system itself <strong>has no "punch now" button</strong>. HR or a clerk imports the clock records, and the system calculates working hours and overtime from them.</p>
<p>The Attendance page has three tabs: <strong>Summary</strong>, <strong>Punch Import</strong> and <strong>Raw Punches</strong>.</p>
<h4>Importing punch records</h4>
<ol>
  <li>Open "Attendance → Punch Import".</li>
  <li>Click <strong>Download Template</strong> and fill in the columns: Emp. No. / Date / Check-in / Check-out (Chinese and Vietnamese headers are both recognized).</li>
  <li>Click <strong>Select File</strong> to upload (.xlsx / .xls / .csv are supported).</li>
  <li>Check the import result: inserted / skipped / failed, with the failures listed by <strong>row / field / error</strong>.</li>
</ol>
<h4>Raw punches</h4>
<p>Query the raw punch records by date range; the view is read-only and the data is <strong>insert-only</strong>. Corrections must go through the punch correction flow (see "Punch Anomalies and One-click Correction").</p>
<h4>Attendance summary</h4>
<ul>
  <li>Pick a date range (and optionally an employee) and query. Columns include day type, shift, normal hours, weekday / weekend / holiday overtime, late and early-leave minutes, absence and leave type.</li>
  <li>Click <strong>Generate Summary</strong> to recalculate the selected range; records already locked or reviewed are not affected.</li>
  <li>Rows with a grey background are locked or reviewed and cannot be edited.</li>
  <li><strong>Export</strong> in the top right writes an Excel file.</li>
</ul>
<blockquote><strong>Note:</strong> Punch data can only be appended, never edited in place. If a punch is missing or wrong, raise a Punch Correction Request and let the approval decide.</blockquote>`},{id:"hr-schedule",title:"Shift Scheduling",body:`<p>"Shift Scheduling &amp; Anomaly Detection" keeps each employee's shift per day and detects anomalies from it; write actions need the appropriate permission.</p>
<p>The page has four tabs: <strong>Roster Calendar</strong>, <strong>Roster Import</strong>, <strong>Anomaly Detection</strong> and <strong>Shift Settings</strong>.</p>
<h4>Roster calendar</h4>
<ul>
  <li>Pick a month (and optionally a department) to see shifts as coloured blocks per employee and day; the colours come from the shift settings.</li>
  <li>Click a cell to change the shift: choose one and save — it takes effect immediately and recalculates that day's hours with the new shift.</li>
  <li>Right-click or long-press a cell to clear it, which means the day has no shift.</li>
  <li><strong>Bulk Assign</strong> at the top sets the same shift for several employees over a date range at once.</li>
  <li>The month's roster can be exported.</li>
</ul>
<h4>Roster import</h4>
<ul>
  <li>Template columns: Emp. No. / Date / Shift Code / Remarks (Chinese and Vietnamese headers are both recognized).</li>
  <li>Rosters <strong>may be overwritten</strong>: for the same employee and day the last import wins (unlike punches, which are insert-only).</li>
  <li>Leave the shift code empty or enter rest for a rest day.</li>
</ul>
<h4>Shift settings</h4>
<p>Maintain each shift's start and end time (cross-day shifts such as 20:00 → 05:00 next day are supported), flex minutes, daily and hourly allowance, overtime multiplier, colour and enabled state. "Rest" is built in and needs no configuration here. After changing shift windows or pay rules, run Anomaly Detection and Generate Summary again before the data is used in payroll.</p>`},{id:"hr-leave",title:"Leave and Overtime",body:`<h4>Leave</h4>
<p>Leave goes through the <strong>Leave Request</strong> form (New e-flow → Leave Request).</p>
<ol>
  <li>Choose the leave type: annual / personal / sick / marriage / maternity.</li>
  <li>Fill in the start and end time, the number of days, the handover person and the reason; supporting documents can be attached.</li>
  <li>Submit to start the approval.</li>
</ol>
<p>Approval chain: handover person confirms → direct manager approves → department manager approves → (long leave) Deputy GM / General Manager approves → HR files the record. Whether the deputy GM or the general manager is involved depends on a day-count threshold controlled by a system parameter.</p>
<h4>Overtime</h4>
<p>There is no separate overtime request form. Overtime is derived from <strong>punch records plus the roster</strong> and appears in the weekday / weekend / holiday overtime columns of "Attendance → Summary". The corresponding pay is calculated when you run "Payroll → Generate Payroll", using the overtime rates in the salary structure and the shift pay rules.</p>
<blockquote><strong>Note:</strong> Overtime lost to a missing punch should be handled with a Punch Correction Request; do not edit the attendance summary directly.</blockquote>`},{id:"hr-comp",title:"Owed Shifts and Comp Days",body:`<p>Handles "rest on a workday, work on a rest day": the two dates for the same person are offset hour by hour and <strong>no overtime pay is generated</strong>. It works for individuals and for a whole department.</p>
<p>Go through the <strong>Comp Leave / Owed Shift Request</strong> form (New e-flow → Comp Leave / Owed Shift Request).</p>
<ol>
  <li>Choose the type: owe / repay pair, rest on workday (owed) or work on rest day (repayment).</li>
  <li>Fill in the owed date and hours, the repayment date and hours, and the repayment shift (day / night / regular day / regular night).</li>
  <li>Add a reason, attach files if needed, then submit for approval.</li>
</ol>
<p>Approval chain: direct manager approves → HR files the record. Once approved the system logs the day-type override, adjusts the roster and settles the owed-shift balance, <strong>without generating overtime pay</strong>.</p>
<table>
  <thead><tr><th>Rule</th><th>Details</th></tr></thead>
  <tbody>
    <tr><td>Granularity</td><td>Hours, minimum 0.5 hour</td></tr>
    <tr><td>Offsetting</td><td>Owed and repaid hours for the same person cancel out; no overtime after offsetting</td></tr>
    <tr><td>Owed-shift balance</td><td>Open / settled / cancelled</td></tr>
  </tbody>
</table>
<blockquote><strong>Note:</strong> After approval the system handles everything automatically — do not edit the roster or punches again by hand. An owed shift that is never repaid, or approved leave where the person still worked, produces a corresponding anomaly (see "Punch Anomalies and One-click Correction").</blockquote>`},{id:"hr-anomaly",title:"Punch Anomalies and One-click Correction",body:`<p>"Anomaly Detection" compares punch records and hours against the <strong>scheduled shifts</strong> to find violations automatically; records already closed by hand are never reopened.</p>
<ol>
  <li>Open "Shift Scheduling → Anomaly Detection", pick a date range, click <strong>Detect Anomalies</strong> and confirm.</li>
  <li>Review the results in the anomaly list; filter by date, anomaly type or open/closed state, and export if needed.</li>
  <li>For an anomaly, click <strong>Close</strong> and add a note to mark it handled; <strong>Reopen</strong> undoes that.</li>
</ol>
<h4>The seven anomaly types</h4>
<table>
  <thead><tr><th>Type</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td>Absent (no punch)</td><td>Scheduled, but no punch at all that day</td></tr>
    <tr><td>Worked on rest day</td><td>Punched in on a rest day or public holiday</td></tr>
    <tr><td>Missing night-shift punch</td><td>A required night-shift punch is missing</td></tr>
    <tr><td>Shift mismatch</td><td>The actual punches do not match the scheduled shift</td></tr>
    <tr><td>Consecutive cross-shift work</td><td>Worked across consecutive shift windows</td></tr>
    <tr><td>Late / early leave (by shift)</td><td>Late or left early according to the shift window</td></tr>
    <tr><td>Work without schedule</td><td>Punched in although no shift was scheduled</td></tr>
  </tbody>
</table>
<h4>One-click correction</h4>
<ol>
  <li>In the action column of the anomaly list, click <strong>Request Correction</strong> (permission required).</li>
  <li>The dialog pre-fills the suggested punch slot and reason; you can change them.</li>
  <li>Choose the <strong>punch slot</strong> (check-in / check-out, night check-in / check-out, OT check-in / check-out) and the <strong>reason for the missed punch</strong>, then fill in the <strong>statement</strong> (required). A witness is optional.</li>
  <li>Choose <strong>Submit for Approval</strong> or <strong>Save as Draft Only</strong> and submit.</li>
</ol>
<p>The system creates a Punch Correction Request whose approval chain follows the <strong>corrected person's</strong> line. <strong>Once approved, the punch record is written for that person and the anomaly is closed automatically.</strong> If the anomaly already has a pending correction request, it is reused instead of creating a second one.</p>
<blockquote><strong>Note:</strong> If a correction request is rejected or cancelled, use "Cancel Correction" on the anomaly to remove the link (the request itself is unaffected). Comp-day handling can also produce the anomalies "owed shift overdue" and "approved comp leave not repaid".</blockquote>`},{id:"hr-salary",title:"Payroll",body:`<p>"Payroll" has two tabs: <strong>Salary Records</strong> and <strong>Salary Structures</strong>; write actions need the appropriate permission.</p>
<h4>Salary structures</h4>
<ul>
  <li>Maintained per employee: base salary, position allowance, overtime rates (weekday / weekend / holiday), whether the shift allowance applies, and the salary items (allowance and deduction lines with Chinese and Vietnamese names).</li>
  <li>Lifecycle: <strong>Draft → Approved → Published</strong>. After approval the version is archived and cannot be edited; to change something click <strong>New Version</strong>, which copies the current version into a new draft.</li>
</ul>
<h4>Generating payroll</h4>
<p>Pick a pay period and the employees (or all employees) and click <strong>Generate Payroll</strong>. The system combines the latest approved structure with that month's attendance summary to produce salary records.</p>
<h4>Salary records</h4>
<p>Filter by period or employee. Columns include gross pay, net pay, total allowances, total deductions, overtime pay and shift allowance; the result can be exported.</p>
<h4>Shift pay</h4>
<p>The shift allowance (which can be switched on or off per employee) and the overtime bonus are broken down by <strong>scheduled shift</strong>. Shift windows and pay rules are maintained under "Shift Scheduling → Shift Settings". When both the shift allowance and the multiplier are 0, no shift pay is produced.</p>
<blockquote><strong>Note:</strong> Generate the month's attendance summary first, otherwise the calculation cannot reflect all hours and overtime.</blockquote>`},{id:"hr-handover",title:"Work Handover",body:`<p>Used for resignation, job transfer or long leave: the outgoing person starts it, the incoming person confirms, then the manager and HR sign off. Once approved the system transfers pending to-dos and replaces future flow handlers automatically.</p>
<ol>
  <li>Open "Handover" and, under New Handover, choose the type (resignation / transfer / long leave / other) and the effective date.</li>
  <li>Select the <strong>outgoing</strong> and <strong>incoming</strong> person (they cannot be the same).</li>
  <li>After picking the outgoing person the system collects their handover items (pending to-dos / CC items / equipment maintenance tasks / system documents / shared drive folders / training plans / meeting actions).</li>
  <li>Tick the items to transfer; use "Add Other Item" for anything the system does not know about, such as a door access key.</li>
  <li>Add handover notes and submit.</li>
</ol>
<p>Two switches: <strong>Transfer Pending To-dos</strong> (on approval, the outgoing person's to-dos at the current step move to the incoming person) and <strong>Replace Routing to the Incoming Person</strong> (rewrites reporting lines, department heads and handlers hard-coded in flow definitions).</p>
<p>The Handovers list below shows past handover forms with a View action; the status is Draft / In Progress / Completed / Rejected / Canceled.</p>
<blockquote><strong>Note:</strong> If the outgoing person still has pending to-dos or an unfinished handover, you are warned when starting a new one. An employee with pending to-dos also cannot be deactivated until the handover is completed.</blockquote>`}]},{id:"flow",title:"Workflows",sections:[{id:"flow-apply",title:"Starting a Form",body:`<p>Every business form is started from "New e-flow".</p>
<ol>
  <li>Open the entry: the shortcut on the home page, or <strong>New e-flow</strong> in the top right of the My Approvals page.</li>
  <li>Pick the flow in the "Select Flow Type" dropdown; the page then previews the <strong>approval flow</strong> steps.</li>
  <li>Fill in the form under "Fill Content" (required fields carry a red *).</li>
  <li>Click <strong>Save Draft</strong> to keep it for later, or <strong>Submit</strong> to send it into approval.</li>
</ol>
<ul>
  <li>If a required field is empty the missing fields are listed and the form is not submitted; blank rows in detail tables are dropped automatically.</li>
  <li>A single attachment must not exceed 100MB; after submitting you are taken to the form details.</li>
  <li>A draft can be submitted later from its details page.</li>
</ul>
<blockquote><strong>Note:</strong> "Controlled issue" and "Obsolete" for system documents do not appear on the general form page — start them from the document's details page.</blockquote>`},{id:"flow-todo",title:"My To-dos and Completed Items",body:`<p>The My Workspace group holds four form lists:</p>
<table>
  <thead><tr><th>List</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td>My Approvals</td><td>Forms waiting for your action</td></tr>
    <tr><td>My Requests</td><td>Forms you started</td></tr>
    <tr><td>CC to Me</td><td>Forms sent to you for information</td></tr>
    <tr><td>Completed</td><td>Forms you have already handled</td></tr>
  </tbody>
</table>
<ul>
  <li>Search by keyword (form number or title) at the top; My Requests and All Forms can also be filtered by status — click <strong>Reset</strong> to clear the conditions.</li>
  <li>Columns: form number, title, flow type, applicant, status, submitted at.</li>
  <li>Click a row or View Details to open the form; on My Approvals the action column shows Approve, which opens the form for handling.</li>
  <li>Clicking a flow in the home page's volume chart opens all forms of that flow, already filtered.</li>
</ul>`},{id:"flow-approve",title:"Approving and Countersigning",body:`<p>In a form's details page the action bar at the bottom shows the actions available to you at the current step.</p>
<table>
  <thead><tr><th>Action</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td>Approve</td><td>An approval comment is optional; submitting moves the form to the next step</td></tr>
    <tr><td>Reject</td><td>A reason is required (at least 2 characters)</td></tr>
    <tr><td>Send Back</td><td>The form returns to draft so the applicant can revise and resubmit</td></tr>
    <tr><td>Transfer</td><td>Hands the current to-do to someone else</td></tr>
    <tr><td>Remind</td><td>Nudges the current handler</td></tr>
    <tr><td>Countersign</td><td>Adds a temporary confirmer before or after you</td></tr>
    <tr><td>Terminate</td><td>Dangerous: ends the whole flow</td></tr>
  </tbody>
</table>
<ul>
  <li><strong>Countersigning:</strong> when a step requires several approvers, approving shows "Approved; N more countersign(s) needed" and the form moves on only once the full count is reached.</li>
  <li><strong>Execution reply / verification:</strong> steps that show "Submit Reply" or "Verify &amp; Close" need a structured reply; a form that is not closed cannot be archived.</li>
  <li>If a step has no available approver the form is suspended and a notice is shown; an administrator can take it over with "Assign Approver".</li>
  <li>After approving, the system reports whether the flow finished, moved to the next step, or is suspended.</li>
</ul>`},{id:"flow-status",title:"Form Statuses",body:`<p>A form has one of seven statuses, shown in the form header and in list status columns:</p>
<table>
  <thead><tr><th>Status</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td>Draft</td><td>Saved but not submitted</td></tr>
    <tr><td>In Progress</td><td>Submitted and moving through approval</td></tr>
    <tr><td>Rejected</td><td>Rejected by an approver</td></tr>
    <tr><td>Withdrawn</td><td>Withdrawn by the applicant</td></tr>
    <tr><td>Completed</td><td>All approval steps are done</td></tr>
    <tr><td>Archived</td><td>Completed and archived</td></tr>
    <tr><td>Terminated</td><td>Terminated; the flow ends here</td></tr>
  </tbody>
</table>
<ul>
  <li>Approving through the last step makes the form Completed. Flows that require closure (with execution or verification steps) must finish the execution reply and verification before they can be archived.</li>
  <li>The applicant can use "Withdraw Form" on an unfinished form; it then returns to Draft.</li>
  <li>The form header also shows a Closed / Not Closed marker, but only for flows that require closure.</li>
</ul>`},{id:"flow-design",title:"Flow Designer and Versioning",body:`<p>"Workflow Design" (under System Management, administrators only) maintains flow definitions in the browser; "Flow Versions" manages the versions.</p>
<h4>Workflow design</h4>
<ul>
  <li>Pick a flow on the left; the right side has three tabs: <strong>Approval Steps</strong>, <strong>Form Fields</strong> and <strong>Advanced</strong>.</li>
  <li><strong>New Flow</strong>: the code must start with a lowercase letter and contain only lowercase letters, digits and underscores (it cannot be changed afterwards); also fill in the Chinese name, Vietnamese name, category, icon and description.</li>
  <li>Steps can be Approval, CC, Execution or Verification. An approval step defines the approver source (department head, direct manager, deputy GM, general manager, chosen by the initiator, by role, or a custom expression), the countersign count, whether ad-hoc countersign is allowed, and an optional condition branch (a field, an operator and either a fixed value or a system parameter reference).</li>
  <li>Form fields can be text, number, date, date and time, long text, rich text, dropdown, attachment, detail table, person or multiple people. Dropdown options and detail-table columns can be edited.</li>
  <li>Advanced: whether closure is required, and the ledger columns (column key, Chinese label, Vietnamese label).</li>
  <li><strong>Save Config</strong> asks for confirmation. When the definition differs from the current release a new version is created automatically; forms started afterwards use the new configuration, while forms already in flight keep running on the version they started with.</li>
  <li>Disabling a flow removes it from the New e-flow page; in-flight and historical forms are unaffected.</li>
</ul>
<h4>Flow versions</h4>
<ul>
  <li>Version states: Draft / Testing / Released / Archived.</li>
  <li><strong>Release</strong> makes a version the current release (the previous release is archived automatically); <strong>Roll Back</strong> makes an older version the release again; <strong>Save as New Draft</strong> creates a new draft from the current definition.</li>
  <li>Releasing or rolling back only switches the release pointer and <strong>does not affect in-flight forms</strong>.</li>
</ul>
<blockquote><strong>Note:</strong> Changing a flow configuration affects forms started from then on, so proceed carefully; click Reload to confirm the current content before saving.</blockquote>`},{id:"flow-ledger",title:"Workflow Ledger",body:`<p>"Workflow Ledger" (under System Management) gathers forms by flow type for querying and export.</p>
<ol>
  <li>Pick the flow type in the dropdown at the top left.</li>
  <li>Filter by start date, end date, department, status or keyword and click <strong>Search</strong>.</li>
  <li>The table shows the form number, title, applicant, department, the flow's custom ledger columns, status and created time; click a form number to open it.</li>
  <li><strong>Export Excel</strong> in the top right exports the current filter result, up to 200 rows.</li>
</ol>
<p>List pages such as My Approvals also have a Workflow Ledger button in the top right for quick access.</p>`}]}];export{e as default};
