# Meridian CRM user guide

For everyone who uses Meridian CRM day to day: principals, practitioners, case officers, accountants,
brokers, administrators. Profession-specific steps (matters, engagements, loan applications) are in
[How each profession's workspace works](domain-workflows.md); who can do what is in
[Roles and permissions](roles-and-permissions.md).

**Contents**

1. [Create your firm's workspace](#1-create-your-firms-workspace)
2. [Sign in](#2-sign-in)
3. [Finding your way around](#3-finding-your-way-around)
4. [Lists](#4-lists)
5. [Records](#5-records)
6. [Activities, calendar and notifications](#6-activities-calendar-and-notifications)
7. [The client portal](#7-the-client-portal)
8. [Importing and exporting](#8-importing-and-exporting)
9. [Reports and dashboards](#9-reports-and-dashboards)
10. [Privacy requests](#10-privacy-requests)
11. [For administrators](#11-for-administrators)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Create your firm's workspace

Each firm gets its own private workspace. Its data is kept separate from every other firm's and stored in
Australia.

1. Open the sign-in page and choose **Create a workspace for your firm**.
2. **Step 1 of 2: What kind of firm do you run?** Choose *Law firm*, *Migration agency*, *Accounting
   practice* or *Loan broking*, then **Continue**. The panel on the left shows what your workspace will
   include.
3. **Step 2 of 2: Tell us about your firm.**
   - **Firm name** and **Your name**.
   - **ABN (optional)**: checked as you type; leave it blank if you don't have it handy.
   - **Work e-mail**: you'll sign in with it.
   - **Password**: at least 12 characters. The checklist under the field turns green as each rule is met
     (long enough, not a common password, doesn't contain your name or e-mail). Passwords found in known
     data breaches are refused.
   - Tick the terms and choose **Create workspace**.
4. **Check your inbox.** Open the link in the e-mail within 24 hours; it works once. Didn't get it? Check
   spam, or use **send it again** on the same screen.
5. The link finishes setting up your workspace and signs you in. You're its first **System
   Administrator**.

On a test installation without e-mail set up, there's no e-mail step: the workspace opens as soon as you
choose **Create workspace**.

Your workspace opens with the profession's app, records, stages, reports and dashboard ready, in the
profession's colour, and with the profession's words (for example *Clients* and *Matters*).

**First steps** (shown on your home page as *Get your workspace ready*): invite your colleagues, import
your clients, add your firm's details (ABN, address, logo) and set up e-mail sending.

---

## 2. Sign in

- Go to your firm's address and enter your **work e-mail** and **password**. Choose **Show** to check what
  you typed.
- **Two-step verification.** The first time, scan the QR code with an authenticator app (Microsoft or
  Google Authenticator, 1Password, Authy) and enter the 6-digit code. **Save the recovery codes**
  somewhere safe; each works once if you lose your phone (**Use a recovery code** on the sign-in step).
- **More than one workspace?** If your e-mail belongs to several firms, choose which one to open.
- **Forgot your password?** Choose it on the sign-in page; you'll get a link valid for 30 minutes.
- **Locked out?** Five wrong passwords lock the account for 15 minutes. An administrator can unlock it
  sooner.
- You're signed out after 60 minutes without activity, and after 12 hours in any case.

---

## 3. Finding your way around

| Area | What it's for |
|---|---|
| **Left rail** | Your apps (your profession's app, Analytics) and **Setup** if you administer the workspace. |
| **Tabs** under the app name | The app's areas: Home, Enquiries, Clients, Matters, Calendar, Reports… |
| **Search** (top) | Find any record you're allowed to see, by name, number, e-mail or phone. Results appear as you type; press Enter for the full results page. |
| **Bell** | Notifications: reminders, assignments, conflict-check alerts, signed agreements. |
| **Your initials** | **Account settings** (your details, password, two-step verification) and **Sign out**. |
| **Home** | A greeting with shortcuts for your profession, your open work, tasks due, recent records and the practice dashboard's key charts. |

On a phone, the menu button at top left opens the apps.

---

## 4. Lists

Every tab that holds records (Clients, Matters, Time Entries…) opens a list.

- **Switch list view**: use the view name at the top (for example *All Matters*, *My Matters*,
  *Limitation Dates (90 days)*). Pin a view as your default with the pin icon.
- **Search this list** narrows the current view.
- **Sort**: select a column heading.
- **Filters** (funnel icon): add conditions such as *Stage equals Lodged* or *Due date in the next 30
  days*.
- **Edit columns** (columns icon): choose and order the columns.
- **Kanban** (grid icon): see records as cards by stage and drag a card to move it; the same stage checks
  apply as on the record.
- **List view controls** (gear): create a **New list view** with its own filters and columns, choose **Who
  sees this view** (only you or everyone), or delete one you made.
- **New** creates a record. **Import** and **Export** appear if your profile allows them.
- **Select rows** with the tick boxes to **Change owner** or **Delete** several at once.

---

## 5. Records

A record page has:

- **Header**: the record's name, its key details, **Edit**, and the **⌄ More actions** menu.
- **Stage path** (matters, engagements, applications): the stages as chevrons. Choose the next stage and
  **Mark as Current Stage**, or **Mark Stage as Complete** to move on one step. If something's missing
  (a conflict check, a signed agreement, a reviewer…), you'll see exactly what, and nothing changes.
- **Details**: all fields in sections. Fields you can't edit are read-only; fields your profile can't see
  aren't shown at all.
- **Related**: linked records (a client's matters and invoices, a matter's parties, checklist, time,
  trust entries). Use **New** on a related list to create a linked record with the link filled in.
- **History**: who changed what and when, for tracked fields.
- **Activity** (right): calls, tasks, events and notes (see below).
- **Profession actions** appear as buttons when they apply, for example **Lodge Application**, **Invoice
  Unbilled Time**, **Record Preliminary Assessment**, **Generate BAS Deadlines**, **Send to Client**.

**⌄ More actions**

| Action | What it does |
|---|---|
| **Clone** | A new record pre-filled from this one. |
| **Change Owner** | Hand the record to a colleague. |
| **Sharing** | Give a person or group read or read/write access to this record. |
| **Invite to Customer Portal** | (Clients) give the client a portal sign-in. |
| **Export Personal Data** / **Erase Personal Data** | (Clients) privacy requests; see [section 10](#10-privacy-requests). |
| **Delete** | Moves the record to the Recycle Bin. Some records can't be deleted (trust and client-account entries, records under 7-year retention). |

**Recycle Bin**: deleted records stay restorable for 30 days (your administrator can change this). Find
it in Setup → Data → Recycle Bin.

---

## 6. Activities, calendar and notifications

- On any record's **Activity** panel: **Log a Call**, **New Task**, **New Event**, **New Note**. Tasks have
  a due date and an assignee; events appear in the calendar; notes can be attached to the record.
- **Files**: upload documents on a record (up to 25 MB each). They're stored with the record and covered
  by the same backups and access rules.
- **Calendar** tab: your events and due tasks by day, week or month.
- **Notifications** (bell): reminders for limitation dates, court dates, visa and passport expiries,
  lodgement deadlines, settlements and rate reviews (see your profession's reminders in
  [domain-workflows.md](domain-workflows.md)), plus tasks assigned to you and items needing your
  attention.

---

## 7. The client portal

Clients sign in to a simplified, secure portal to see their own matters, engagements or applications.
Depending on your profession they can:

- follow progress (stages and key dates, never your internal notes, fees or rates);
- upload documents against their checklist or mark document requests uploaded;
- read and **sign** service agreements or engagement letters (typed name; the time and IP address are
  recorded);
- see their invoices;
- raise a request and message your team.

To invite a client: open their record → **⌄ More actions → Invite to Customer Portal**. They get an e-mail
to set a password. Administrators manage portal access in Setup → Portal Users.

---

## 8. Importing and exporting

**Import** (Setup → Data → Import Data, or **Import** on a list) brings records in from a CSV file in four
steps:

1. **Object**: what you're importing (Clients, Organisations, Matters…).
2. **Upload** the CSV (first row = column names).
3. **Map fields**: match columns to fields; choose what to do with duplicates: **Update the existing
   record**, **Skip the row**, **Create anyway**, or **Don't check (always create)**.
4. **Review & import**: a dry run shows what will happen and any errors per row before anything is saved.

Imports follow the same validation, permissions and duplicate rules as typing records in. Small files
import straight away; large ones run in the background. **Import history** shows every import's results.

**Export**: **Export** on a list downloads the current view (with its filters) as CSV. Exports need the
*Export Data* permission and are recorded in the audit log.

---

## 9. Reports and dashboards

- **Reports** tab: your profession's reports are ready in a shared folder (for example *Open Matters by
  Stage*, *Work in Progress*, *Grant Rate*, *Upcoming Lodgements*, *Commission by Lender*).
- **New Report**: choose the record type, filters, columns, grouping (summaries such as count, sum,
  average), and a chart.
- **Subscribe** to a report to receive it by e-mail daily, weekly or monthly.
- **Dashboards** (Analytics app): charts from several reports on one page; the practice dashboard's key
  charts also appear on Home. **New Dashboard** to build your own.
- Reports only ever include records you're allowed to see.

---

## 10. Privacy requests

On a client's record, **⌄ More actions**:

- **Export Personal Data**: a file with everything held about the person (an access request under the
  Privacy Act).
- **Erase Personal Data**: anonymises their personal details, notes, files and portal sign-in, after you
  confirm with your password and record the reason or request reference. It can't be undone. Records you
  must keep (invoices, consent proof) stay, anonymised. If the person has client-account or trust
  transactions still within the 7-year retention period, erasure is refused and the message says so.

Both are recorded in the audit log. Retention periods are set in Setup → Data Retention.

---

## 11. For administrators

Everything here is in **Setup** (left rail).

| Task | Where |
|---|---|
| Add people, deactivate leavers, reset two-step verification, unlock accounts | Setup → Users |
| What each role can see and do | Setup → Profiles, Roles, Sharing Settings; see [roles-and-permissions.md](roles-and-permissions.md) |
| Firm name, ABN, address, logo, colour | Setup → Company & Branding |
| Invoice numbering, terms, tax | Setup → Billing |
| How long records and files are kept | Setup → Data Retention |
| Fields, picklists, page layouts, validation | Setup → Object Manager |
| Which apps and tabs appear | Setup → App Manager (the general Sales, Service, Marketing and Billing apps are hidden in profession workspaces, not deleted; switch them on here) |
| Add another practice area | Setup → Industry Packs |
| Client portal access | Setup → Portal Users |
| Who did what | Setup → Audit Log |

**Adding a colleague**: Setup → Users → New user. Choose their **profile** (what they can do, e.g.
*Solicitor*) and **role** (where they sit, e.g. under their supervising principal). They get an e-mail
invitation, set a password and enrol two-step verification.

**E-mail sending**: confirmation links, password resets, invitations and reminders need outgoing e-mail.
The platform administrator sets it up once for everyone, either in the server settings or through the
platform e-mail API, which can also send a test e-mail. Zoho Mail (SMTP) and Zoho ZeptoMail are supported.
See *E-mail delivery (Zoho)* in [operations.md](operations.md) and `backend/.env.production.example`.

---

## 12. Troubleshooting

| Problem | What to do |
|---|---|
| **The confirmation / reset / invitation e-mail never arrives** | Check spam. Ask your administrator to check outgoing e-mail is set up (with Zoho, the From address must be the Zoho mailbox or an alias, and accounts with two-factor sign-in need an application-specific password). |
| **"This link is invalid or has expired"** | Links work once and expire (sign-up 24 h, password reset 30 min, invitations 72 h). Start again to get a new one. |
| **"Too many attempts. Please wait a few minutes and try again."** | Sign-in and sign-up are rate limited; wait and retry. |
| **I can't see a record a colleague mentioned** | Most work records are private to their owner and the people above them. Ask the owner (or an administrator) to share it via **⌄ More actions → Sharing**. |
| **A tab or field is missing** | Your profile doesn't include it. Ask an administrator. |
| **I can't move a matter / engagement / application to the next stage** | Read the message: it names the missing step (conflict clearance, costs disclosure, signed agreement, engagement letter, reviewer, lodging permission, BID record…). See [domain-workflows.md](domain-workflows.md). |
| **I can't edit or delete a trust or client-account entry** | By design: ledgers are append-only. Record a correcting entry. |
| **"Request origin is not allowed."** | The app is being opened at an address other than its configured one (`PUBLIC_APP_URL`). Use the usual address or ask your administrator. |
| **Something went wrong** | Try again. If it keeps happening, send your administrator the time and what you were doing; errors are logged with a reference. |
