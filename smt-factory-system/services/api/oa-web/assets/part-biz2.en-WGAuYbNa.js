const e=[{id:"collab",title:"Collaboration & Knowledge",sections:[{id:"collab-meeting",title:"Meeting Minutes",body:`<p>The meeting module closes the loop from scheduling to follow-up: start → schedule → hold → minutes → resolutions and action items → close. The Meeting Minutes page is where you read the minutes already written for each meeting.</p>
<ol>
<li>Create the meeting (as a draft) under "Meetings → New Meeting".</li>
<li>In the Meeting List click <strong>Schedule</strong> on the draft: fill in the planned start and end time, the format (offline / online / hybrid), location, online link, host, recorder, agenda and attendees; saving writes the attendees and sends in-app notifications.</li>
<li>On the day click <strong>Start</strong>, and <strong>End</strong> when it finishes (minutes can only be written after the meeting ends).</li>
<li>In the meeting details fill in the minutes body and the Vietnamese minutes body, click <strong>Save</strong>, then let the host, the recorder or an administrator click <strong>Confirm &amp; Publish</strong> — publishing notifies all attendees.</li>
<li>Open "Meetings → Minutes" and filter by status (minutes confirmed / closed / ended / all). Resolutions and action items accumulate across meetings on the Decisions &amp; Actions page and can be exported to Excel or printed.</li>
</ol>
<table><thead><tr><th>Meeting status</th><th>Meaning</th></tr></thead><tbody>
<tr><td>Draft</td><td>Created but not scheduled</td></tr>
<tr><td>Scheduled</td><td>Time fixed and attendees notified</td></tr>
<tr><td>In Progress</td><td>Started but not ended</td></tr>
<tr><td>Ended</td><td>Minutes can be written</td></tr>
<tr><td>Minutes Confirmed</td><td>Minutes published</td></tr>
<tr><td>Closed</td><td>Meeting and minutes archived</td></tr>
</tbody></table>
<blockquote><strong>Note:</strong> Minutes can only be written after the meeting ends. Publishing cannot be undone and notifies every attendee.</blockquote>`},{id:"collab-announce",title:"Announcements",body:`<p>Used for company and factory notices, with bilingual titles and bodies, a category, pinning, publish and expiry times, and read receipts. Reach it from the Announcements card on the home page or the red dot in the overview; the page is Announcements.</p>
<ol>
<li>Click <strong>New Announcement</strong> and fill in the title (required), the Vietnamese title, the category, the body and the Vietnamese body.</li>
<li>Optionally set the publish time (empty means publish immediately), the expiry time (empty means no expiry) and whether to pin it.</li>
<li><strong>Save Draft</strong> keeps it as a draft, <strong>Save &amp; Publish</strong> publishes it right away; a draft can also be published later from the list.</li>
<li>A reader clicking <strong>Details</strong> records a read receipt automatically; the list shows the publisher, the publish time and how many people have read it.</li>
</ol>
<table><thead><tr><th>Category</th><th>Notes</th></tr></thead><tbody>
<tr><td>Notice</td><td>General notice</td></tr>
<tr><td>Policy</td><td>Rules and policies</td></tr>
<tr><td>Activity</td><td>Event notices</td></tr>
<tr><td>Urgent</td><td>Urgent matters</td></tr>
</tbody></table>
<blockquote><strong>Note:</strong> Non-administrators only see published announcements plus their own drafts, and only the publisher or a system administrator can edit, publish or delete one.</blockquote>`},{id:"collab-drive",title:"Shared Drive (file sharing)",body:`<p>The shared drive is the team file area, laid out like a file explorer: a folder tree on the left, a multi-column content area in the middle and a preview pane on the right. Permissions are granted per folder.</p>
<ol>
<li>On the Files tab, double-click to enter a folder. You cannot upload files while outside a folder (files live inside folders); at the root you can only create folders.</li>
<li>The command bar offers New Folder and Upload File, and supports multiple selection (Ctrl/Shift), copy / cut / paste, drag-and-drop moves, rename, delete and batch operations.</li>
<li>Files and folders can be shared as a link with an optional validity period and access code; leaving both empty means the link never expires and needs no code.</li>
<li><strong>Permissions</strong> opens inside a folder (enter one first) and lets you grant read-only / read &amp; write / upload / delete / create subfolder.</li>
<li>The Recycle Bin restores or permanently deletes items (kept for 7 business days, then removed automatically); the Audit Log records create / update / delete / move / copy / share / restore / purge / permission changes and can be exported.</li>
</ol>
<blockquote><strong>Note:</strong> Folder owners and system administrators always have full access, and every write goes through the server API, so loop protection and permission inheritance are never bypassed.</blockquote>`},{id:"collab-knowledge",title:"Knowledge Sharing",body:`<p>The knowledge sharing platform is for uploading, reviewing and reading knowledge documents, with versioning, likes, favourites and keyword search.</p>
<ol>
<li>Click <strong>Upload Document</strong>, fill in the title, category and description, choose the file and submit; the status becomes Pending Review.</li>
<li>An administrator or anyone holding <code>knowledge:manage</code> clicks <strong>Approve</strong> to make it Open, or <strong>Reject</strong> to decline it.</li>
<li>Open documents can be previewed online and downloaded, and both actions are counted.</li>
<li>Administrators can upload a new version of an open document: the title is locked and the page shows vN → vN+1; Version History lists every version with its status and allows downloading.</li>
<li>Any user can like or favourite a document and review them on the My Favorites and My Likes tabs.</li>
</ol>
<blockquote><strong>Note:</strong> Documents that are not open (pending review or rejected) cannot be downloaded.</blockquote>`},{id:"collab-training",title:"Training Management",body:`<p>Training &amp; Certification covers pre-job and on-the-job training: plans, records, per-employee queries and work certificates, across four tabs.</p>
<ol>
<li><strong>Training Plans</strong>: create a plan (type pre-job or on-the-job, with a name, the applicable positions and the training items) and use <strong>Import by Position</strong> to add every active employee of a position in one go.</li>
<li>On a plan row click <strong>Generate Training Records</strong> to create records for the enrolled employees in bulk, and <strong>Export Plan Sheet</strong> to export the plan.</li>
<li><strong>Training Records</strong>: enter the assessment result and conclusion; batch saving is supported.</li>
<li><strong>By Employee</strong>: type a name or employee number to see all training records of that person (pre-job / on-the-job / total), with Excel export and printing.</li>
<li><strong>Work Certificates</strong>: check certificates and their validity; trainings that require an exam can be taken online (full score 100, 60 or more passes).</li>
</ol>`}]},{id:"report",title:"Reports",sections:[{id:"report-stats",title:"Dashboard Metrics and How They Are Calculated",body:`<p>"System Management → Dashboard" summarises approval efficiency and form distribution; the figures are computed live from flow instances and to-dos, and Refresh in the page header reloads them.</p>
<table><thead><tr><th>Metric</th><th>Definition</th></tr></thead><tbody>
<tr><td>Average approval time</td><td>Mean of (end time − submit time) over finished forms (approved or rejected), in hours</td></tr>
<tr><td>On-time rate (within 2h)</td><td>Share of those forms whose submit-to-end time is 2 hours or less</td></tr>
<tr><td>On time / total</td><td>Forms within the target divided by all forms included in the statistic</td></tr>
<tr><td>Total forms</td><td>Sum of forms across all statuses</td></tr>
<tr><td>Volume by flow</td><td>Number of forms per enabled flow definition</td></tr>
<tr><td>Forms by status</td><td>All flow instances grouped by status (draft / in progress / approved / rejected / withdrawn / completed / archived / terminated)</td></tr>
<tr><td>Last 7 days</td><td>Forms created per day over the last seven days</td></tr>
<tr><td>Backlog (by person)</td><td>Approval tasks currently in the pending state, grouped by approver</td></tr>
</tbody></table>
<blockquote><strong>Note:</strong> Average approval time and on-time rate only include finished forms (approved or rejected) that have both a submit and an end time; forms still in progress are excluded and both metrics share the same denominator.</blockquote>
<p>To inspect and export form details by flow, department, time or status, use "System Management → Workflow Ledger".</p>`}]},{id:"sys",title:"System Management",sections:[{id:"sys-org",title:"Organisation Structure",body:`<p>"System Management → Org &amp; Staff" shows the department tree on the left — with the department name, code, head and headcount — and the people of the selected department on the right.</p>
<ol>
<li>Hovering a row on the left shows the department code and head; departments outside the company are tagged.</li>
<li>Maintaining the organisation: open "System Management → Org &amp; Position Management", click <strong>Download Template</strong> to get the headers (emp. no. / name / department code / department name / department name (Vietnamese) / parent department code / position code / email / mobile / status), fill it in, upload it with <strong>Select File</strong>, review the preview and error summary, then click <strong>Start Import</strong>.</li>
<li>The import result lists departments and people separately with added, updated and failed counts plus the error rows.</li>
<li><strong>Export Org Structure</strong> exports the whole organisation to Excel (requires <code>org:manage</code>).</li>
</ol>
<blockquote><strong>Note:</strong> Departments are matched and updated by department code, and the hierarchy is attached through the parent code. Department codes are used for flow assignment by department and for ledger filtering, so keep them stable.</blockquote>`},{id:"sys-user",title:"Employees and Accounts",body:`<p>Employees and accounts are maintained on "System Management → Org &amp; Staff": create a user, edit a user, reset a password.</p>
<ol>
<li><strong>New User</strong>: fill in the name (required), username (optional, defaults to the employee number), email, mobile, department, position and roles. On save the system generates the employee number and an initial password, and requires a password change at first sign-in.</li>
<li><strong>Position is required</strong>: positions are how flows find people by position and how trainings import employees by position.</li>
<li><strong>Edit User</strong>: change the name, email, mobile, department, position and roles. The position dropdown only offers enabled positions; if the employee holds a disabled one, it is added to the list marked "Disabled ·".</li>
<li><strong>Reset Password</strong> is available to administrators only; it generates a random password and asks you to tell the person to change it soon. The admin account does not show this button.</li>
</ol>
<blockquote><strong>Note:</strong> An account must complete a work handover before it can be deactivated — if there are still pending to-dos or an unfinished handover, the system refuses and lists them, so start a handover first (or have an administrator force the deactivation). Mobile numbers are visible to department managers and above only; everyone else sees an empty cell.</blockquote>`},{id:"sys-role",title:"Roles and Permissions",body:`<p>Roles decide which menus and actions an account can use; they are ticked per person under "Org &amp; Staff → Edit User".</p><p>Beyond roles, each account also has <strong>module permissions</strong> (none / view / operate), granted per business module and per flow on the "Permission Management" page. They gate API access: view-only can read but not write, none is rejected outright. The stricter of role and module permission wins.</p>
<ol>
<li>Open Org &amp; Staff, click <strong>Edit</strong> on an employee, tick the roles and save.</li>
<li>Permission codes control the visibility of menu items and buttons; the system administrator (admin) is not limited by permission codes and sees every menu.</li>
</ol>
<table><thead><tr><th>Permission code</th><th>Grants</th></tr></thead><tbody>
<tr><td><code>org:manage</code></td><td>Organisation import and export, position dictionary maintenance</td></tr>
<tr><td><code>template:field</code></td><td>Custom field management for inspection templates</td></tr>
<tr><td><code>equip:manage</code></td><td>Equipment management</td></tr>
<tr><td><code>ipqc:manage</code></td><td>Line patrol (IPQC) templates and records</td></tr>
<tr><td><code>doc:issue</code></td><td>Document issue</td></tr>
<tr><td><code>flow:config</code></td><td>Workflow design</td></tr>
<tr><td><code>meeting:manage</code></td><td>Meeting management</td></tr>
</tbody></table>
<blockquote><strong>Note:</strong> The system only assigns roles per person; the role and permission lists are built in and there is no screen for creating or editing roles. Workflow Design is available to administrators only.</blockquote>`},{id:"sys-position",title:"Position Dictionary",body:`<p>Positions are how flows find people by position and how trainings import employees by position, which is why a position is required when creating a user. The position dictionary lives in the Position Dictionary card on "System Management → Org &amp; Position Management".</p>
<ol>
<li>New position: fill in the Chinese name (required), the Vietnamese name (required) and the sort order, then save.</li>
<li><strong>The position code is generated by the system from the Chinese name and is not entered in the UI</strong>; the list does not show codes either.</li>
<li>Disabling a position removes it from pickers while historical data and existing employees keep theirs. The list shows how many places use each position; a position in use can only be disabled, not deleted.</li>
<li>While editing an employee under Org &amp; Staff you can also click <strong>New Position</strong> to create one inline; it is selected automatically afterwards.</li>
</ol>
<blockquote><strong>Note:</strong> Position codes start with a lowercase letter and may contain digits and underscores; codes cannot be changed in the UI, so keep the Chinese and Vietnamese names tidy.</blockquote>`},{id:"sys-field",title:"Inspection Templates and Custom Fields",body:`<p>This group has two parts: inspection templates (inspection, patrol, first article) and template custom fields.</p>
<ol>
<li><strong>Inspection templates</strong>: under "System Management → Inspection Templates / Line Patrol Templates / FAI Templates" click <strong>New Template</strong> and fill in the template number, name, Vietnamese name and so on. <strong>Import Excel</strong> converts a workbook into a rich text draft (.xlsx / .xls; if there are several sheets you are asked which one), and you can adjust tables, text and images in the editor. The original Excel is archived and can be downloaded. After saving, enable or disable it; a template referenced by records cannot be deleted.</li>
<li><strong>Template custom fields</strong>: under "System Management → Template Custom Fields" (requires <code>template:field</code>) you can add horizontal fields such as customer, model or work order number, scoped to equipment inspection, IPQC patrol and FAI first article, at both header and item level.</li>
<li>Field types are text / number / date / select, each with required, order and enabled settings. Built-in fields (equipment / frequency / line / shift / product code / process) accept bilingual labels, enable/disable and reordering, but their key and type cannot change and they cannot be deleted — disable them to hide them.</li>
</ol>
<blockquote><strong>Note:</strong> Deleting a custom field that templates already hold values for returns an error; clear the references first or use force delete. Inspection templates do not currently use header-level custom fields.</blockquote>`},{id:"sys-settings",title:"System Settings",body:`<p>The My Settings page (avatar menu in the top right → My Settings) holds three personal settings.</p>
<ol>
<li><strong>Language</strong>: switch between Chinese, Vietnamese and English; the preference is stored on your account and synced across desktop and mobile. The language button in the top bar does the same thing.</li>
<li><strong>Account information</strong>: username, name, department and position (read-only).</li>
<li><strong>Change Password</strong>: enter the current password, the new password and the confirmation, then save; the new password and the confirmation must match.</li>
</ol>
<blockquote><strong>Note:</strong> The interface is available in Chinese, Vietnamese and English. "System Management → System Settings" in the left menu is currently a placeholder page with no options, so use My Settings for day-to-day changes. An account required to change its password at first sign-in is redirected to the change-password page until it does.</blockquote>`}]},{id:"faq",title:"FAQ",sections:[{id:"faq-general",title:"FAQ and Known Limitations",body:`<p>The following are the system's real limitations and known issues; follow them to avoid misreading the screens.</p>
<h4>1. Phone scanning requires HTTPS on 8443</h4>
<p>Camera-based scanning on phones (inspection, stocktake and so on) needs <strong>HTTPS on port 8443</strong>; the camera cannot be used over plain HTTP. When the self-signed certificate is used for the first time, accept it on the phone.</p>
<h4>2. "Export PDF" is really print-to-PDF</h4>
<p>Export PDF on patrol and first article records is not generated on the server; it opens the browser print dialog where you choose Save as PDF. Do not block the print window.</p>
<h4>3. Automatic verdict only reads Chinese headers and the English word spec</h4>
<p>The automatic table verdict for patrol and first article recognises Chinese header keywords and the English <code>spec</code> only; <strong>Vietnamese headers are not recognised yet</strong> (work in progress), so a Vietnamese header will not trigger a verdict.</p>
<h4>4. On inspection, the automatic verdict and the report are two different things</h4>
<p>Inspection <strong>does judge automatically</strong> (same as patrol and first article): when the table contains a SPEC and measured values are filled in, saving or submitting judges OK/NG — any NG makes the whole record NG, empty cells do not block OK — and a statistics bar shows per-row results, the NG count and the accept/reject totals.</p>
<p>But <strong>reporting an anomaly is manual</strong>: the system does not open an equipment repair order just because the verdict is NG; the person filling in, or an administrator, must click Report Equipment Repair.</p>
<h4>5. Two known errors on the attendance page</h4>
<p>The Attendance page has 2 legacy errors (existing issues, not yet fixed) that do not affect other modules.</p>
<h4>6. Column resizing needs bordered tables</h4>
<p>Dragging column widths relies on table borders, which the system applies to all tables. If a particular table cannot be dragged, refresh the page and try again.</p>
<blockquote><strong>Note:</strong> All of the above follows the actual screen; if this page disagrees with it, please raise it in the issue feedback list.</blockquote>`}]}];export{e as default};
