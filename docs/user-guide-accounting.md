# Accounting Practice user guide

A practical guide for accounting and tax practices using Meridian CRM: partners, accountants, bookkeepers
and practice administrators. It follows an engagement from first enquiry to lodgement and billing. For
general features (lists, search, records, reports) see the [general user guide](user-guide.md); for who can
do what, see [Roles and permissions](roles-and-permissions.md).

> The Accounting Practice workspace supports your professional obligations (APES 305 engagement letters,
> independent review, lodgement by a registered tax agent). It doesn't replace professional judgement:
> confirm due dates against your current ATO lodgment program.

**Contents**

1. [Your workspace at a glance](#1-your-workspace-at-a-glance)
2. [Who does what](#2-who-does-what)
3. [Before you start: set-up checklist](#3-before-you-start-set-up-checklist)
4. [From prospect to client](#4-from-prospect-to-client)
5. [Setting up a client](#5-setting-up-a-client)
6. [Opening an engagement](#6-opening-an-engagement)
7. [Engagement letters](#7-engagement-letters)
8. [Document requests](#8-document-requests)
9. [Doing the work and recording time](#9-doing-the-work-and-recording-time)
10. [Review](#10-review)
11. [Lodging](#11-lodging)
12. [Lodgement deadlines and BAS](#12-lodgement-deadlines-and-bas)
13. [Billing](#13-billing)
14. [Clients in the portal](#14-clients-in-the-portal)
15. [Reports and dashboard](#15-reports-and-dashboard)
16. [Messages you may see and what to do](#16-messages-you-may-see-and-what-to-do)
17. [Quick reference](#17-quick-reference)

---

## 1. Your workspace at a glance

The **Accounting Practice** app opens as your home page. In this workspace the words are slightly
different: your **Clients** are entities (people, companies, trusts, SMSFs), and the individuals you deal
with at each one are **Contact People**. Enquiries are called **Prospects**.

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Start an engagement, Lodgement deadlines, Record time), lodgements due, your engagements, tasks, recent records and the dashboard's key charts. |
| **Prospects** | Potential clients not yet engaged. |
| **Clients** | The entities you act for, with entity type, TFN, GST and BAS frequency. |
| **Contact People** | Directors, trustees, individuals you deal with. |
| **Engagements** | Every job, numbered `JOB-2026-0001`, `JOB-2026-0002`… |
| **Lodgement Deadlines** | Every due date across the practice. |
| **Time Entries** | Time recorded in 6-minute units. |
| **Invoices** | Bills to clients. |
| **Calendar**, **Reports**, **Dashboards** | Diary, the practice's reports and the practice dashboard. |

**An engagement moves through seven stages**, shown as a path across the top of the engagement:

```
Not Started → Awaiting Information → In Progress → Review → Ready to Lodge → Lodged → Complete
```

The system won't let work start (**In Progress**) until the client has signed the engagement letter, won't
let a job reach **Ready to Lodge** without an independent reviewer's sign-off, and only a registered tax agent
can mark it **Lodged**.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Partner** | Principal, partner | Everything on every client and engagement; **lodge**; review sign-off; WIP and billing; import/export; reassign work. |
| **Accountant** | Registered tax agent staff | Their own engagements: letters, document requests, time, invoices; **lodge**. |
| **Bookkeeper** | Bookkeeper, BAS preparer | Work on assigned engagements: document requests, deadlines and time. |
| **Practice Administrator** | Practice / office manager | Onboarding, engagement letters, deadlines, document requests, invoices and payments across the practice. |

**Who sees an engagement.** Engagements are private. An engagement is visible to its owner, its **Responsible
Accountant** and **Reviewer** (they get read/write access automatically), anyone above them in the role
hierarchy, and Partners and Practice Administrators (who see all engagements). Share one with anyone else
from **⌄ More actions → Sharing**.

**Tax File Numbers** are encrypted. Only Partners, Accountants and Practice Administrators see and edit them;
everyone else doesn't see the field.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: practice name, ABN, address and logo. They appear on invoices.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their partner.
3. **Billing**: invoice numbering, payment terms and GST.
4. **Import your clients** (Setup → Data → Import Data) with entity type, GST status, BAS frequency and client
   manager, so BAS deadlines can be generated straight away.
5. **Default charge-out rate** and **return due dates**: the practice defaults are **$220/hour** and the
   due dates in section 6. Changing them needs an administrator with database access for now.

---

## 4. From prospect to client

1. **Prospects → New**: name, contact details, what they need, source.
2. Follow up from the prospect's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When they engage you, open the prospect and choose **Convert**. The system checks for an existing client
   with the same details, then creates the **Client** and its **Contact Person**. The prospect becomes
   read-only.

---

## 5. Setting up a client

On the client record:

| Field | Notes |
|---|---|
| **Entity Type** | Individual, company, trust, partnership, SMSF and so on. |
| **Tax File Number** | Encrypted; visible only to Partners, Accountants and Practice Administrators. |
| **Registered for GST** | Tick if registered. |
| **BAS Frequency** | Monthly, Quarterly or Annually. Needed for **Generate BAS Deadlines**. |
| **Financial Year End** | If not 30 June. |
| **Client Manager** | Receives the client's BAS deadline reminders. |

Add the client's directors, trustees or other people under **Contact People**.

---

## 6. Opening an engagement

From the client's **Related** tab (Engagements → **New**) or **Engagements → New**:

| Field | Notes |
|---|---|
| **Client** (required) | The entity. |
| **Client Contact** | The person you deal with. |
| **Engagement Type** (required) | Individual / Company / Trust / Partnership Tax Return, SMSF Annual Return, BAS, IAS, FBT Return, SMSF Audit, Bookkeeping, Payroll, Advisory. |
| **Financial Year**, **Period** | Filled automatically (see below); change if needed. |
| **Lodgement Due** | Filled automatically for returns (see below). |
| **Responsible Accountant** | Defaults to you: the preparer. |
| **Reviewer** | Someone other than the preparer (needed before Ready to Lodge). |
| **Fee Type**, **Agreed Fee** | Fixed Fee or time-based; the agreed fee. |

**When you save:**
- the engagement gets its number (`JOB-YYYY-0000`) and starts at **Not Started**;
- the **Financial Year** is set: the last completed year for returns and audits (e.g. 2025-26), the current
  year for other work;
- the **Lodgement Due** date is set from the practice defaults:

  | Return | Default due |
  |---|---|
  | Individual Tax Return | 31 October after the year ends |
  | Company Tax Return | 28 February |
  | Trust Tax Return, Partnership Tax Return | 31 March |
  | SMSF Annual Return | 28 February |
  | FBT Return | 21 May |

- a **document request** list is created for the type (for example, for an individual return: income
  statements, bank interest and dividend statements, work-related deduction receipts, private health
  insurance statement, rental income and expenses);
- for returns, BAS, IAS and FBT, a **lodgement deadline** is created with the due date and the Responsible
  Accountant;
- the Responsible Accountant and Reviewer get access.

---

## 7. Engagement letters

APES 305 requires terms of engagement before work starts.

1. On the engagement: **Related → Engagement Letters → New**. Enter the **Scope and Responsibilities**, the
   **Client Responsibilities**, the **Fee / Basis of Fees** (filled from the agreed fee) and **Covers
   Engagements Until**.
2. Choose **Send to Client**.
3. The client opens it in the portal and chooses **Sign Engagement Letter**: they type their full name and
   accept. The system records **Signed By**, **Signed** (time) and **Signed From IP**, and notes it in the
   audit log.
4. Signing ticks **Engagement Letter Signed** on the engagement and moves it to **Awaiting Information**.

Letters go **Draft → Sent → Signed** (or Cancelled). Signed or cancelled letters can't be changed.

Until the letter is signed, the engagement can't move to In Progress: *"The client must sign the engagement
letter (APES 305) before work starts."*

---

## 8. Document requests

The engagement's **Related → Document Requests** lists what you need from the client:

| Status | Meaning |
|---|---|
| **Requested** | Waiting for the client. |
| **Uploaded** | The client has uploaded it and chosen **I've Uploaded This** in the portal. The Responsible Accountant is notified. |
| **Accepted** | You've checked it. |
| **Not Applicable** | Not needed for this client. |

Add requests with **New**, with **Instructions** and a **Due Date**; untick **Visible to Client** for internal
items.

**When every request is Accepted or Not Applicable** (and the letter is signed), the engagement moves to **In
Progress** by itself.

---

## 9. Doing the work and recording time

**Time Entries → New**, or from the engagement (**Related → Time Entries → New**), or the **Record time**
shortcut on Home:

| Field | Notes |
|---|---|
| **Engagement** | Required. |
| **Date** | Defaults to today. |
| **Units (6 min)** | 1 unit = 6 minutes. 1.5 hours = 15 units. |
| **Work Done** | What you did. |
| **Billable** | On by default. |
| **Charge-out Rate** | The practice default ($220/hour) unless you enter another. |

The system works out **Hours** and **Amount (ex GST)**. **Staff Member** defaults to you. On the engagement it
keeps:
- **Time Cost**: all time recorded (except written-off time);
- **Unbilled Time (WIP)**: billable time not yet invoiced;
- **Recoverability**: agreed fee ÷ time cost, as a percentage. Under 100% means the job took more time than
  the fee covers.

Billed time can't be changed. **My Timesheet** shows your entries.

---

## 10. Review

When the preparer has finished, move the engagement to **Review**. To move it on to **Ready to Lodge**:

- a **Reviewer** must be assigned: *"Assign a reviewer before the work is ready to lodge."*;
- the reviewer must be someone other than the **Responsible Accountant**: *"The reviewer must be someone
  other than the preparer."*;
- the **reviewer** signs off by moving it to Ready to Lodge. A registered tax agent with **Lodge Returns**
  can also sign off. Anyone else sees *"Only the reviewer can sign off the review."*

The **Awaiting Review** list view shows engagements waiting for a reviewer.

---

## 11. Lodging

For returns, BAS, IAS and FBT, moving the engagement to **Lodged** (or **Complete**) needs the **Lodge
Returns** permission (registered tax agent: Partners and Accountants). Otherwise: *"Lodging needs the Lodge
Returns permission (registered tax agent)."*

Enter the **ATO Lodgement Reference**. Lodging:
- sets the **Lodged** date (today, if empty);
- marks the engagement's **lodgement deadlines** as Lodged, with the date.

Move the engagement to **Complete** once billed and finished.

---

## 12. Lodgement deadlines and BAS

**Lodgement Deadlines** lists every due date: **Upcoming**, **Overdue**, **Lodged** or **Deferred**.

- Deadlines turn **Overdue** automatically once the due date passes.
- Reminders go to the deadline's **Responsible** person (else its owner) **14 days, 3 days and on the day**.
- **Upcoming and Overdue** (list view) and the **Lodgement Deadlines (next 30 days)** and **Overdue
  Lodgements** reports show what needs attention.

**BAS deadlines.** On a client with a **BAS Frequency**, choose **Generate BAS Deadlines**. It creates this
financial year's remaining activity statement deadlines (skipping past ones and any that already exist),
assigned to the **Client Manager**:

| Frequency | Periods and due dates |
|---|---|
| Quarterly | Q1 Jul–Sep: 28 Oct · Q2 Oct–Dec: 28 Feb · Q3 Jan–Mar: 28 Apr · Q4 Apr–Jun: 28 Jul |
| Monthly | Each month: the 21st of the following month |
| Annually | 28 February after the year ends |

These are standard dates; deferrals and lodgment program concessions are yours to apply (set the deadline to
**Deferred** or change its date).

---

## 13. Billing

On the engagement, choose **Invoice Engagement** (shown from In Progress onwards):

- **Fixed fee**: one invoice line for the **Agreed Fee** (time is absorbed). It can only be invoiced once:
  *"This fixed-fee engagement has already been invoiced."* Enter the fee first: *"Enter the agreed fee
  first."*
- **Time-based**: one line per unbilled billable time entry, in date order. Those entries become **Billed**.
  *"There is no unbilled time on this engagement."* if there's nothing to bill.

The invoice goes to the client, linked to the engagement. Check the draft, then **Issue Invoice**. Use
**PDF** to download it and **Void Invoice** to cancel an issued one. Payments are recorded on the invoice;
status moves Draft → Issued → Partially Paid → Paid.

---

## 14. Clients in the portal

Invite a client contact from their record: **⌄ More actions → Invite to Customer Portal**. Once signed in they
see:
- their engagements and progress;
- **engagement letters** to read and **Sign Engagement Letter**;
- **document requests**: upload the documents and choose **I've Uploaded This**;
- their invoices;
- a way to send you requests and messages.

---

## 15. Reports and dashboard

**Practice dashboard** (also summarised on Home): open engagements by stage, overdue lodgements, workload by
accountant and work in progress.

**Reports** (Reports tab → *Accounting Practice Reports*):

| Report | Shows |
|---|---|
| Open Engagements by Stage | The pipeline of work. |
| Engagements by Type | Mix of work. |
| Workload by Accountant | Open engagements per responsible accountant. |
| Work in Progress (Unbilled Time) | Unbilled time by engagement. |
| Recoverability by Engagement | Fee ÷ time cost per engagement. |
| Lodgement Deadlines (next 30 days) | What's due soon. |
| Overdue Lodgements | What's late. |

**Useful list views on Engagements:** *All Engagements*, *My Engagements*, *Open Engagements*, *Awaiting
Review*.

---

## 16. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New engagements start at Not Started.* | Create the engagement without choosing a later stage. |
| *The client must sign the engagement letter (APES 305) before work starts.* | Send the letter and wait for the client's signature in the portal. |
| *Signed or cancelled engagement letters can't be changed.* | Create a new letter. |
| *Only letters sent to you can be signed.* | (Client) The letter hasn't been sent yet, or was already signed. |
| *Type your full name and accept the terms.* | (Client) Type your full name and tick the box. |
| *Assign a reviewer before the work is ready to lodge.* | Set the **Reviewer**. |
| *The reviewer must be someone other than the preparer.* | Choose a different reviewer. |
| *Only the reviewer can sign off the review.* | Ask the reviewer (or a registered tax agent) to move it on. |
| *Lodging needs the Lodge Returns permission (registered tax agent).* | Ask a Partner or Accountant to lodge. |
| *Record at least one 6-minute unit.* | Enter 1 or more units. |
| *Billed or written-off time can't be changed.* | Record a new entry instead. |
| *Enter the agreed fee first.* | Fill in **Agreed Fee** on the engagement. |
| *This fixed-fee engagement has already been invoiced.* | Void the existing invoice first if it needs re-issuing. |
| *There is no unbilled time on this engagement.* | Nothing to bill: check entries are Billable and Unbilled. |

---

## 17. Quick reference

**The life of an engagement**

1. **Prospect** → **Convert** → **Client** (entity type, TFN, GST, BAS frequency, client manager).
2. **New engagement** (Not Started): financial year, due date, document requests and lodgement deadline fill
   in.
3. **Engagement letter** → **Send to Client** → client **signs** in the portal → Awaiting Information.
4. **Documents**: client uploads and marks each request; you accept them → In Progress automatically.
5. **Prepare** and record time (WIP and recoverability update).
6. **Review** by someone other than the preparer → Ready to Lodge.
7. **Lodge** (Lodge Returns permission) → deadlines marked Lodged.
8. **Invoice Engagement** → **Issue Invoice** → Complete.

| I want to… | Do this |
|---|---|
| Start a job | Client → Related → Engagements → New |
| Send the engagement letter | Engagement → Related → Engagement Letters → New → Send to Client |
| Ask for documents | Engagement → Related → Document Requests → New |
| Record time | Home → Record time, or Time Entries → New |
| Send for review | Set the Reviewer → stage path → Review |
| Sign off a review (reviewer) | Stage path → Ready to Lodge |
| Lodge | Enter the ATO reference → stage path → Lodged |
| Create the year's BAS deadlines | Client → Generate BAS Deadlines |
| Bill | Engagement → Invoice Engagement → Issue Invoice |
| See what's due | Lodgement Deadlines → Upcoming and Overdue |
| Give a client access | Contact Person → ⌄ More actions → Invite to Customer Portal |
