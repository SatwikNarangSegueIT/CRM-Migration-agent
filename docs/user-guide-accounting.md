# Accounting Practice user guide

A practical guide for accounting and tax practices using Meridian CRM: partners, accountants, bookkeepers
and practice administrators. It follows an engagement from first enquiry to lodgement and billing. For
general features (lists, search, records, reports) see the [general user guide](user-guide.md); for who can
do what, see [Roles and permissions](roles-and-permissions.md).

> The Accounting Practice workspace supports your professional obligations: APES 305 terms of engagement,
> independent review, lodgement by a registered tax agent, proof of identity and client-to-agent linking, and
> SMSF auditor independence. It doesn't replace professional judgement: confirm due dates against your
> current ATO lodgment program.

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

The **Accounting Practice** app opens as your home page. The words are slightly different here: your
**Clients** are entities (people, companies, trusts, SMSFs), and the individuals you deal with at each one
are **Contact People**. Enquiries are called **Prospects**.

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Start an engagement, Lodgement deadlines, Record time), lodgements due, your engagements, tasks, recent records and the dashboard's key charts. |
| **Prospects** | Potential clients not yet engaged, with the service they need. |
| **Clients** | The entities you act for, with entity type, TFN, ABN, GST, BAS frequency and identity checks. |
| **Contact People** | Directors, trustees, individuals you deal with. |
| **Engagements** | Every job, numbered `JOB-2026-0001`, `JOB-2026-0002`… |
| **Lodgement Deadlines** | Every due date across the practice. |
| **Time Entries** | Time recorded in 6-minute units. |
| **Invoices** | Bills to clients. |
| **Calendar** | Your events and tasks, plus every open **lodgement deadline** (amber). |
| **Reports**, **Dashboards** | The practice's reports and the Practice Dashboard. |

Tabs that don't fit the screen are under **More**.

**An engagement moves through seven stages**, shown as a path across the top of the engagement:

```
Not Started → Awaiting Information → In Progress → Review → Ready to Lodge → Lodged → Complete
```

The system won't let work start (**In Progress**) until the client has signed the engagement letter, won't
let a job reach **Ready to Lodge** without an independent reviewer's sign-off, and only a registered tax agent
can mark a return **Lodged**, once the client's identity is verified and (for a business) the practice is
linked as its agent.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Partner** | Principal, partner | Everything on every client and engagement; **lodge**; sign off any review; record a letter signed on paper; WIP and billing; import/export; reassign work. |
| **Accountant** | Registered tax agent staff | Their own engagements: letters, document requests, time, invoices; **lodge**. |
| **Bookkeeper** | Bookkeeper, BAS preparer | Work on assigned engagements: document requests, deadlines and time. |
| **Practice Administrator** | Practice / office manager | Onboarding, engagement letters, deadlines, document requests, invoices and payments across the practice. |

**Roles** (whose records someone sees) come named for a practice:

```
Managing Partner
├── Partner
│   └── Client Manager
│       └── Accountant
├── Bookkeeping Manager
│   └── Bookkeeper
├── Client Services Manager
│   └── Client Services Coordinator
└── Practice Manager
    └── Practice Administrator
```

Rename or rearrange them in **Setup → Roles**.

**Who sees an engagement.** Engagements are private. An engagement is visible to its owner, its **Responsible
Accountant** and **Reviewer** (they get read/write access automatically, and lose it when they're changed),
anyone above them in the role hierarchy, and Partners and Practice Administrators (who see all engagements).
**My Engagements** means engagements you own or are the Responsible Accountant or Reviewer on. Share one with
anyone else from **⌄ More actions → Sharing**.

**The client manager** gets read/write access to their client (to keep its details and BAS deadlines up to
date), whoever owns the record.

**Tax File Numbers** are encrypted. Only Partners, Accountants and Practice Administrators see and edit them;
everyone else doesn't see the field.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding** (Setup → Settings): practice name, **ABN**, address and logo. They appear on
   invoices; a tax invoice can't be issued until the ABN is entered.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their partner.
   Record each registered tax agent's **tax agent number** (8 digits) on their user record.
3. **Practice Settings** (Setup → Settings → Practice Settings):

   | Setting | Default | Notes |
   |---|---|---|
   | Practice tax agent number | (blank) | The practice's TPB registration, shown on letters when the practitioner has no number of their own. A letter can't be sent without one or the other. |
   | Default charge-out rate | $220/hour | Used for time entries without a rate. |
   | Engagement letter before work starts (APES 305) | On | Blocks In Progress until the letter is signed. |
   | BAS due dates | Standard ATO dates | Or **Registered agent lodgment program** (see section 12). |
   | Lodgement deadline reminders | 14, 3 and 0 days before | |
   | Return due dates (DD-MM) | See section 6 | One per return type. |

4. **Billing**: invoice numbering, payment terms and GST.
5. **Import your clients** (Setup → Data → Import Data) with entity type, GST status, BAS frequency and client
   manager, so BAS deadlines can be generated straight away.

---

## 4. From prospect to client

1. **Prospects → New**: name, contact details, **Service Required** (Individual Tax Return, Company / Trust
   Tax Return, BAS / Bookkeeping, SMSF, Payroll, Business Advisory), **Entity Type** and **Source**.
2. Follow up from the prospect's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When they engage you, open the prospect and choose **Convert**. The system checks for an existing client
   with the same details, then creates the **Client** and its **Contact Person**. The prospect becomes
   read-only.

---

## 5. Setting up a client

On the client record:

| Field | Notes |
|---|---|
| **Entity Type** | Individual, Sole Trader, Company, Trust, Partnership, SMSF, Not-for-profit. |
| **Tax File Number** | Encrypted; checked with the ATO check digit, so a typo is caught: *"That TFN isn't valid. Check the digits."* |
| **ABN** | Checked with the ABN check digits and formatted `51 824 753 556`. |
| **Registered for GST** | Tick if registered. |
| **BAS Frequency** | Monthly, Quarterly, Annually or Not Registered. Needed for **Generate BAS Deadlines**. |
| **Financial Year End** | If not 30 June. |
| **Client Manager** | Gets access to the client and receives its BAS deadline reminders. |
| **Identity Verified**, **Identity Verified On** | Tick once you've sighted proof of identity for the client and the person you deal with (TPB and ATO proof-of-identity guidance). Needed before lodging. |
| **Agent Nominated (Client-to-Agent Linking)** | For companies, trusts, partnerships, SMSFs and other businesses: tick once the client has nominated the practice in ATO Online services for business. Needed before lodging for them. |

Add the client's directors, trustees or other people under **Contact People**.

---

## 6. Opening an engagement

From the client's **Related** tab (Engagements → **New**) or **Engagements → New**:

| Field | Notes |
|---|---|
| **Client** (required) | The entity. |
| **Client Contact** | The person you deal with (and who receives portal e-mails). |
| **Engagement Type** (required) | Individual / Company / Trust / Partnership Tax Return, SMSF Annual Return, BAS, IAS, FBT Return, SMSF Audit, Bookkeeping, Payroll, Advisory. |
| **Financial Year**, **Period** | Leave the year empty: it's set for the type (see below). |
| **Lodgement Due** | Leave empty to use the practice's due date for the return. |
| **Responsible Accountant** | Leave empty to make it you: the preparer. |
| **Reviewer** | Someone other than the preparer (needed before Ready to Lodge). |
| **Fee Type**, **Agreed Fee** | Fixed Fee or Time-based; the agreed fee. |

**When you save:**
- the engagement gets its number (`JOB-YYYY-0000`) and starts at **Not Started**;
- the **Financial Year** is set: the last completed year for returns and audits (e.g. 2025-26), the current
  year for other work, and for an **FBT Return** the last completed FBT year (1 April to 31 March);
- the **Lodgement Due** date is set from the practice's due dates, the first one after the year ends:

  | Return | Default due |
  |---|---|
  | Individual Tax Return | 31 October |
  | Company Tax Return | 28 February |
  | Trust Tax Return, Partnership Tax Return | 31 March |
  | SMSF Annual Return | 28 February |
  | FBT Return | 21 May (the FBT year ends 31 March) |

  These are starting points. Your lodgment program gives clients on your client list their own dates
  (earlier for large or late-lodging clients, later for most others; an FBT return lodged electronically by
  the practice is due 25 June). Change the date on the engagement, or the defaults in Practice Settings;

- a **document request** list is created for the type (for example, for an individual return: income
  statements, bank interest and dividend statements, work-related deduction receipts, private health
  insurance statement, rental income and expenses);
- for returns, BAS, IAS and FBT, a **lodgement deadline** is created with the due date and the Responsible
  Accountant (it follows the engagement when you change its due date or preparer);
- the Responsible Accountant and Reviewer get access.

**SMSF audits.** The auditor must be independent of the fund. An **SMSF Audit** engagement can't have a
Responsible Accountant or Reviewer who prepared the fund's **SMSF Annual Return** or **Bookkeeping** for
the same year: *"The SMSF auditor must be independent of the fund: choose someone who didn't prepare its
accounts or return for 2025-26 (JOB-2026-0012)."*

---

## 7. Engagement letters

APES 305 requires terms of engagement before work starts.

1. On the engagement: **Related → Engagement Letters → New**. Enter the **Scope and Responsibilities**, the
   **Client Responsibilities**, the **Fee / Basis of Fees** (filled from the agreed fee) and **Covers
   Engagements Until**.
2. Choose **Send to Client**. The letter records the **Tax Practitioner** (the Responsible Accountant, else
   you) and their **Tax Agent Number** (theirs, else the practice's), and **e-mails the client contact** a
   link to sign it in the portal. If nobody at the client can sign in yet, you get a notification to invite
   them.
3. The client opens it in the portal and chooses **Sign Engagement Letter**: they type their full name and
   accept. The system records **Signed By**, **Signed** (time) and **Signed From IP**, and notes it in the
   audit log. Only the client can sign: staff don't see the Sign action.
4. Signing ticks **Engagement Letter Signed** on the engagement and moves it to **Awaiting Information**.

**Signed on paper?** A Partner can choose **Record Paper Signature** on the letter, enter who signed and where
the signed copy is kept, and attach the scan. It's recorded in the audit log like an e-signature.

Letters go **Draft → Sent → Signed** (or Cancelled). Signed or cancelled letters can't be changed (they show
without Edit); create a new letter for a new year or a change of scope.

Until the letter is signed, the engagement can't move to In Progress: *"The client must sign the engagement
letter (APES 305) before work starts."*

---

## 8. Document requests

The engagement's **Related → Document Requests** lists what you need from the client:

| Status | Meaning |
|---|---|
| **Requested** | Waiting for the client. |
| **Uploaded** | The client has uploaded it and pressed **I've Uploaded This** in the portal. The Responsible Accountant is notified. |
| **Accepted** | You've checked it. |
| **Not Applicable** | Not needed for this client. |

Add requests with **New**, with **Instructions** and a **Due Date**; untick **Visible to Client** for internal
items.

**Send Document Reminder** on the engagement (until it goes to Review) e-mails the client contact the list of
documents still requested, with their due dates and a link to the portal.

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
| **Charge-out Rate** | Leave empty for the practice's charge-out rate. |

The system works out **Hours** and **Amount (ex GST)**. **Staff Member** defaults to you. On the engagement it
keeps:
- **Time Cost**: all time recorded (except written-off time);
- **Unbilled Time (WIP)**: billable time not yet invoiced;
- **Recoverability**: agreed fee ÷ time cost, as a percentage. Under 100% means the job took more time than
  the fee covers.

Billed or written-off time can't be changed (it shows without Edit). **My Timesheet** shows your entries.

---

## 10. Review

When the preparer has finished, move the engagement to **Review**. To move it on to **Ready to Lodge**:

- a **Reviewer** must be assigned: *"Assign a reviewer before the work is ready to lodge."*;
- the reviewer must be someone other than the **Responsible Accountant**: *"The reviewer must be someone
  other than the preparer."*;
- the **reviewer** signs off by moving it to Ready to Lodge. A Partner can also sign off. Anyone else
  (including the preparer, even with lodging rights) sees *"Only the reviewer (or a partner) can sign off the
  review."*

The **Awaiting Review** list view shows engagements waiting for a reviewer.

---

## 11. Lodging

For returns, BAS, IAS and FBT, moving the engagement to **Lodged** (or **Complete**) needs:

- the **Lodge Returns** permission (registered tax agent: Partners and Accountants): *"Lodging needs the Lodge
  Returns permission (registered tax agent)."*;
- the client's identity verified: *"Verify [client]'s identity before lodging (tick Identity Verified on the
  client)."*;
- for a business client (anything but an individual or sole trader), the practice nominated as its agent:
  *"[client] hasn't nominated the practice as its tax agent in ATO Online services (client-to-agent linking)…"*

Enter the **ATO Lodgement Reference**. Lodging:
- sets the **Lodged** date (today, if empty);
- marks the engagement's **lodgement deadlines** as Lodged, with the date.

When the **notice of assessment** arrives, record its date and the **Refund / (Payable)** amount (refund
positive, tax payable negative) on the engagement. Move the engagement to **Complete** once billed and
finished.

---

## 12. Lodgement deadlines and BAS

**Lodgement Deadlines** lists every due date: **Upcoming**, **Overdue**, **Lodged** or **Deferred**.

- Deadlines turn **Overdue** automatically once the due date passes.
- Reminders go to the deadline's **Responsible** person (else its owner) **14 days, 3 days and on the day**
  until it's lodged (change the lead times in Practice Settings).
- Open deadlines show on the calendar (in amber); **Only mine** shows the ones you're responsible for.
- **Upcoming and Overdue** (list view) and the **Lodgement Deadlines (next 30 days)** and **Overdue
  Lodgements** reports show what needs attention.

**BAS deadlines.** On a client with a **BAS Frequency**, choose **Generate BAS Deadlines**. It creates this
financial year's remaining activity statement deadlines (skipping past ones and any that already exist),
assigned to the **Client Manager**. The dates follow the **BAS due dates** practice setting:

| Frequency | Standard ATO dates | Registered agent lodgment program |
|---|---|---|
| Quarterly | Q1 Jul–Sep: 28 Oct · Q2 Oct–Dec: 28 Feb · Q3 Jan–Mar: 28 Apr · Q4 Apr–Jun: 28 Jul | Q1: 25 Nov · Q2: 28 Feb · Q3: 26 May · Q4: 25 Aug |
| Monthly | The 21st of the following month (December: 21 January) | The same, except December: 21 February |
| Annually (annual GST return) | 31 October | 31 October |

The lodgment program dates apply to activity statements the practice lodges electronically; the December
monthly concession is for business clients with turnover up to $10 million. A client on the program whose
income tax return is due later lodges an annual GST return with that return, and one with no income tax
return to lodge has until 28 February: change the deadline's date. Deferrals are yours to apply too: set the
deadline to **Deferred** or change its date.

---

## 13. Billing

On the engagement, choose **Invoice Engagement** (shown from In Progress onwards):

- **Fixed fee**: one invoice line for the **Agreed Fee** (time is absorbed). It can only be invoiced once:
  *"This fixed-fee engagement has already been invoiced."* Enter the fee first: *"Enter the agreed fee
  first."*
- **Time-based**: one line per unbilled billable time entry, in date order. Those entries become **Billed**.
  *"There is no unbilled time on this engagement."* if there's nothing to bill.

The invoice goes to the client, linked to the engagement. Check the draft, then **Issue Invoice**: a GST tax
invoice needs the practice's ABN (Setup → Settings → Company & Branding). Use **PDF** to download it and
**Void Invoice** to cancel an issued one. Payments are recorded on the invoice; status moves Draft → Issued →
Partially Paid → Paid.

---

## 14. Clients in the portal

Invite a client's contact person from their record: **⌄ More actions → Invite to Client Portal**. The
invitation comes from your practice's name. Once signed in they see:
- their engagements and progress (not the reviewer, time cost, WIP, recoverability or your scope notes);
- **engagement letters**, with the practitioner and tax agent number, to read and **Sign Engagement Letter**;
- **document requests**: upload the documents and press **I've Uploaded This**;
- their invoices;
- **New Client Request** to send you a question, and a conversation and files area on each engagement.

They're e-mailed when a letter is waiting for their signature and when you send a document reminder.

---

## 15. Reports and dashboard

**Practice Dashboard** (also summarised on Home): open engagements by stage, overdue lodgements, workload by
accountant, work in progress and upcoming lodgement deadlines.

**Reports** (Reports tab → *Accounting Practice Reports*):

| Report | Shows |
|---|---|
| Open Engagements by Stage | The pipeline of work. |
| Engagements by Type | Mix of work. |
| Workload by Accountant | Open engagements per responsible accountant. |
| Work in Progress (Unbilled Time) | Unbilled time by engagement. |
| Recoverability by Engagement | Fee ÷ time cost per engagement. |
| Lodgement Deadlines (next 30 days) | What's due soon. |
| Overdue Lodgements | What's late, by responsible person. |

**Useful list views on Engagements:** *All Engagements*, *My Engagements*, *Open Engagements*, *Awaiting
Review*.

---

## 16. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New engagements start at Not Started.* | Create the engagement without choosing a later stage. |
| *That TFN isn't valid. Check the digits.* / *That ABN isn't valid. Check the digits.* | Re-enter the number from the client's documents. |
| *The client must sign the engagement letter (APES 305) before work starts.* | Send the letter and wait for the client's signature in the portal (or record a paper signature). |
| *Add the tax agent number (Setup → Practice settings, or the accountant's own in Setup → Users) before sending…* | Record the practice's or the accountant's tax agent number. |
| *Choose the responsible accountant on the engagement before sending the letter.* | Set the Responsible Accountant. |
| *Only the client can do this, from the client portal.* | Signing is the client's own act: invite them to the portal, or have a Partner record a paper signature. |
| *Only a partner can record a letter signed on paper.* | Ask a Partner. |
| *Enter who signed and where the signed copy is kept.* | Fill in both boxes. |
| *Signed or cancelled engagement letters can't be changed.* | Create a new letter. |
| *Only letters sent to you can be signed.* | (Client) The letter hasn't been sent yet, or was already signed. |
| *Type your full name and accept the terms.* | (Client) Type your full name and tick the box. |
| *Every requested document has been provided.* | Nothing to remind the client about. |
| *Assign a reviewer before the work is ready to lodge.* | Set the **Reviewer**. |
| *The reviewer must be someone other than the preparer.* | Choose a different reviewer. |
| *Only the reviewer (or a partner) can sign off the review.* | Ask the reviewer or a Partner to move it on. |
| *The SMSF auditor must be independent of the fund…* | Choose an auditor who didn't prepare the fund's accounts or return for that year. |
| *Lodging needs the Lodge Returns permission (registered tax agent).* | Ask a Partner or Accountant to lodge. |
| *Verify [client]'s identity before lodging…* | Sight proof of identity, then tick **Identity Verified** on the client. |
| *[client] hasn't nominated the practice as its tax agent in ATO Online services…* | Ask the client to nominate you, then tick **Agent Nominated** on the client. |
| *Record at least one 6-minute unit.* | Enter 1 or more units. |
| *Billed or written-off time can't be changed.* | Record a new entry instead. |
| *Enter the agreed fee first.* | Fill in **Agreed Fee** on the engagement. |
| *This fixed-fee engagement has already been invoiced.* | Void the existing invoice first if it needs re-issuing. |
| *There is no unbilled time on this engagement.* | Nothing to bill: check entries are Billable and Unbilled. |
| *Add the practice's ABN in Setup → Company & Branding before issuing tax invoices.* | Enter the ABN there. |
| *… isn't available for this record now.* | The action doesn't apply to the record as it stands. Refresh the page. |

---

## 17. Quick reference

**The life of an engagement**

1. **Prospect** → **Convert** → **Client** (entity type, TFN, ABN, GST, BAS frequency, client manager,
   identity verified, agent nominated).
2. **New engagement** (Not Started): financial year, due date, document requests and lodgement deadline fill
   in.
3. **Engagement letter** → **Send to Client** (practitioner and tax agent number recorded; client e-mailed) →
   client **signs** in the portal → Awaiting Information.
4. **Documents**: client uploads and marks each request; you accept them → In Progress automatically.
5. **Prepare** and record time (WIP and recoverability update).
6. **Review** by someone other than the preparer → Ready to Lodge.
7. **Lodge** (Lodge Returns permission) → deadlines marked Lodged; record the notice of assessment.
8. **Invoice Engagement** → **Issue Invoice** → Complete.

| I want to… | Do this |
|---|---|
| Start a job | Client → Related → Engagements → New |
| Send the engagement letter | Engagement → Related → Engagement Letters → New → Send to Client |
| Record a letter signed on paper | Letter → Record Paper Signature (Partner) |
| Ask for documents | Engagement → Related → Document Requests → New |
| Chase documents | Engagement → Send Document Reminder |
| Record time | Home → Record time, or Time Entries → New |
| Send for review | Set the Reviewer → stage path → Review |
| Sign off a review (reviewer) | Stage path → Ready to Lodge |
| Lodge | Enter the ATO reference → stage path → Lodged |
| Create the year's BAS deadlines | Client → Generate BAS Deadlines |
| Use the lodgment program dates | Setup → Settings → Practice Settings → BAS due dates |
| Bill | Engagement → Invoice Engagement → Issue Invoice |
| See what's due | Lodgement Deadlines → Upcoming and Overdue, or the calendar |
| Give a client access | Contact Person → ⌄ More actions → Invite to Client Portal |
