# Migration Practice user guide

A practical guide for migration agencies using Meridian CRM: practice managers, registered migration agents
(RMAs), case officers, intake consultants and accounts staff. It follows a visa matter from first enquiry to
decision. For general features (lists, search, records, reports) see the [general user guide](user-guide.md);
for who can do what, see [Roles and permissions](roles-and-permissions.md).

> The Migration Practice workspace supports your obligations under the Code of Conduct for registered
> migration agents (service agreements naming the agent and MARN, the Consumer Guide, the client account). It
> doesn't replace professional judgement: confirm requirements against current guidance from the Office of
> the MARA and the Department of Home Affairs.

**Contents**

1. [Your workspace at a glance](#1-your-workspace-at-a-glance)
2. [Who does what](#2-who-does-what)
3. [Before you start: set-up checklist](#3-before-you-start-set-up-checklist)
4. [From enquiry to client](#4-from-enquiry-to-client)
5. [Opening a matter](#5-opening-a-matter)
6. [Applicants](#6-applicants)
7. [Service agreements](#7-service-agreements)
8. [Document checklist](#8-document-checklist)
9. [Lodging the application](#9-lodging-the-application)
10. [Further information and the decision](#10-further-information-and-the-decision)
11. [Client account (trust)](#11-client-account-trust)
12. [Billing](#12-billing)
13. [Deadlines and expiry reminders](#13-deadlines-and-expiry-reminders)
14. [Clients in the portal](#14-clients-in-the-portal)
15. [Reports and dashboard](#15-reports-and-dashboard)
16. [Messages you may see and what to do](#16-messages-you-may-see-and-what-to-do)
17. [Quick reference](#17-quick-reference)

---

## 1. Your workspace at a glance

The **Migration Practice** app opens as your home page. Its tabs (tabs that don't fit the screen are under
**More**):

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Open a matter, Add a client), your active matters, tasks, recent records and the practice dashboard's key charts. |
| **Enquiries** | Prospective clients not yet engaged, with their visa interest and current visa expiry. |
| **Clients** | Applicants and other people you act for, with passport and visa details. |
| **Organisations** | Employers and sponsors. |
| **Matters** | Every visa application, numbered `MAT-2026-0001`, `MAT-2026-0002`… |
| **Visa Types** | Your library of visa subclasses with default fees and document checklists. |
| **Invoices** | Bills to clients. |
| **Client Account** | The client account (trust) ledger. |
| **Calendar** | Your events and tasks, plus each matter's **lodge-by deadline**, **information due** date and **visa expiry** (amber). |
| **Reports**, **Dashboards** | The practice's reports and the Practice Dashboard. |

**A matter moves through eight stages**, shown as a path across the top of the matter:

```
Consultation → Service Agreement → Document Collection → Preparation → Ready to Lodge → Lodged → Further Information → Decision
```

The system won't let a matter go past **Service Agreement** until the client has signed one, and only people
with the **Lodge Applications** permission can lodge or record a decision. A decision can only be recorded
once the application has been lodged, and recording it closes the matter.

"**My Matters**" (the list view and the home card) means matters you own **or** are the Responsible RMA or
Case Officer on.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Practice Manager** | Principal / practice owner | Everything on every matter and client; visa types; **lodge**; **override the agreement gate**; read the client account and invoices; import/export; reassign files. |
| **Registered Migration Agent** | RMA (MARA-registered) | Every matter; every client's details (passport, visa, sponsorship); agreements; checklists; invoices (with lines); read the client account; **lodge** and record decisions. |
| **Case Officer** | Case officer, paralegal | Matters where they're the Case Officer or Responsible RMA; applicants and checklist items. |
| **Intake Consultant** | Front desk, intake | Enquiries, clients and converting enquiries; open new matters. |
| **Accounts** | Bookkeeper, accounts | The **client account** ledger (deposits, withdrawals, transfers); invoices and payments; read every matter. |
| **Practice Auditor** | Auditor | Read everything, including the client account; change nothing. |

**Roles** (whose records someone sees) come named for an agency:

```
Principal
├── Practice Manager
│   └── Senior Migration Agent
│       └── Registered Migration Agent
├── Case Manager
│   └── Case Officer
├── Client Services Manager
│   └── Intake Consultant
└── Accounts Manager
    └── Accounts Officer
```

Rename or rearrange them in **Setup → Roles**.

**Who sees a matter.** Matters are private. A matter is visible to its owner, its **Responsible RMA** and
**Case Officer** (they get read/write access automatically, and lose it when they're changed), anyone above
them in the role hierarchy, and Practice Managers, RMAs, Accounts and Auditors (who see all matters). Share a
matter with anyone else from **⌄ More actions → Sharing**.

**Passport numbers** are encrypted. Only Practice Managers, RMAs and Accounts can see and edit them (Auditors
can read them); everyone else doesn't see the field.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: practice name, **ABN**, address and logo. They appear on invoices; an invoice
   can't be issued until the ABN is entered.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their
   supervisor. Record each RMA's **MARN** (7 digits) on their user record: a service agreement can't be
   sent until the agent responsible for it has one.
3. **Visa Types**: a new workspace comes with common subclasses (500, 485, 482, 186, 494, 189, 190, 491,
   820/801, 309/100, 600), each with a document checklist. **Enter your professional fee and the current
   visa application charge on each one** (government charges change every 1 July) and add the subclasses
   you handle.
4. **Practice Settings** (Setup → Settings → Practice Settings): whether the Consumer Guide is required
   before sending agreements (on), and the reminder lead times for visa, passport and sponsorship expiry
   (90, 30 days), further information (7, 2, 0 days) and lodge-by deadlines (14, 7, 2 days).
5. **Billing**: invoice numbering, payment terms and GST.
6. **Import your clients** (Setup → Data → Import Data), with passport and visa expiry dates so reminders
   start working straight away.

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, **Visa Interest** (Skilled, Employer Sponsored, Partner /
   Family, Student, Graduate, Visitor, Business / Investor, Citizenship), **Current Visa Expiry** and
   **Source**.
2. Follow up from the enquiry's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When they become a client, open the enquiry and choose **Convert**. The system checks for an existing
   client with the same details, then creates the **Client** (and an **Organisation** only if they gave an
   employer). The enquiry becomes read-only.
4. On the client, record: **Citizenship**, **Country of Birth**, **Passport Number** and **Passport Expiry**,
   **Current Visa** and **Current Visa Expiry**, **In Australia**, and **Privacy Act Consent** (with its
   date).
5. For a sponsoring employer (organisation): tick **Approved Sponsor** and enter the **Sponsorship
   Approved** and **Sponsorship Expiry** dates.

---

## 5. Opening a matter

**Check the visa type** (Visa Types): **Subclass**, **Stream**, **Category**, **Default Professional Fee**,
**Default Government Fee (VAC)**, and the **Document Checklist** (one document per line, copied to each new
matter). Untick **Active** to retire one.

**Then open the matter** from the client's **Related** tab (Matters → **New**) or **Matters → New**:

| Field | Notes |
|---|---|
| **Client** (required) | The main applicant. |
| **Sponsor**, **Nomination TRN**, **Nomination Status** | Employer sponsored visas: the sponsor and its nomination (required before lodging). |
| **Visa Type** | Choosing it fills the fees and creates the document checklist. |
| **Priority**, **Applicant Location** | Normal/High/Urgent; Onshore/Offshore. |
| **Responsible RMA**, **Case Officer** | Both get access to the matter automatically. |
| **Lodge By** | The invitation or nomination deadline (a SkillSelect invitation is valid for 60 days). Reminders 14, 7 and 2 days before. |
| **Professional Fee**, **Government Fee (VAC)** | Filled from the visa type; change if needed. |

**When you save:**
- the matter gets its number (`MAT-YYYY-0000`);
- the fees come from the visa type (if you left them blank);
- the **document checklist** is created from the visa type's template;
- the Responsible RMA and Case Officer get access.

New matters always start at **Consultation**. If you change the visa type later and the matter has no
checklist yet, the new type's checklist is created. **Generate Checklist** adds any documents the visa
type's checklist has gained (it doesn't duplicate what's there); it's offered until the matter is lodged.

---

## 6. Applicants

On the matter: **Related → Applicants → New**. Add everyone on the application: **Primary**, **Secondary**,
**Dependent**, **Sponsor**, **Nominator**. Each applicant is a client record, so their passport and visa
details (and expiry reminders) are kept in one place. Applicants are named after the person and role, e.g.
"Meera Mehta (Dependent)".

---

## 7. Service agreements

The Code of Conduct requires a written agreement before you work on the matter, naming the agent and
their MARN and setting out the services and fees.

1. On the matter: **Related → Service Agreements → New**. The fees come from the matter; add the **Scope of
   Services** (required) and **Estimated Disbursements**.
2. Give the client the **Consumer Guide** and tick **Consumer Guide Provided**.
3. Choose **Send to Client**. The agreement records the **Registered Migration Agent** (the matter's
   Responsible RMA, else you) and their **Agent MARN**. Sending moves the matter from Consultation to
   **Service Agreement** and **e-mails the client** a link to sign in the portal. If nobody at the client
   can sign in yet, you get a notification to invite them.
4. The client opens it in the portal and chooses **Sign Agreement**: they type their full name and accept.
   The system records **Signed By**, **Signed** (time) and **Signed From IP**, and notes it in the audit log.

**Only the client can sign**: staff don't see a Sign action and can't sign on the client's behalf.

Agreements go **Draft → Sent → Signed** (or Cancelled). Signed or cancelled agreements can't be changed
(they show without Edit); create a new one if the scope changes.

**The agreement gate.** A matter can't move past Service Agreement without a signed agreement: *"A signed
service agreement is needed before moving past Service Agreement (Code of Conduct)."* For a genuine
exception (for example an agreement signed on paper), a Practice Manager can choose **Override Agreement
Gate** on the matter and give a reason; it's offered only while the gate applies. The override is recorded
in the audit log and shown on the matter (**Agreement Gate Overridden**).

---

## 8. Document checklist

The matter's **Related → Document Checklist** lists every document needed. Each item has:

| Field | Notes |
|---|---|
| **Status** | Requested → **Uploaded** (the client says it's there) → Received → Approved, or Not Required. |
| **Due Date** | When you need it. |
| **Visible to Client** | On by default: the client sees the item in the portal, uploads the file on it and presses **I've Uploaded This**. |
| **Notes** | The client can read these. |

When the client presses **I've Uploaded This**, the case officer (else the RMA) is notified; check the file
and mark the item **Received** or **Approved**.

**Send Document Reminder** on the matter e-mails the client the list of documents still requested, with
their due dates and a link to the portal.

Move the matter to **Document Collection** while you're gathering documents and **Preparation** while you're
preparing the application.

---

## 9. Lodging the application

1. Move the matter to **Ready to Lodge**.
2. A person with the **Lodge Applications** permission (Practice Manager or RMA) chooses **Lodge
   Application** on the matter and enters the **ImmiAccount TRN** (required).
3. The matter moves to **Lodged** and the **Lodgement Date** is set. Record the **Bridging Visa** granted
   with an onshore application (BVA, BVB, BVC, BVE).

Lodging is refused when:
- the **Lodge By** date has passed: *"The lodge-by date (…) has passed: the invitation or nomination has
  expired, so the application can't be lodged on it."*;
- the visa type is **Employer Sponsored** and there's no sponsor or **Nomination TRN**: *"Enter the
  nomination TRN: an employer sponsored visa is linked to the sponsor's nomination."*;
- you don't have the permission: *"Moving a matter to Lodged or beyond needs the Lodge Applications
  permission."*;
- there's no TRN: *"Enter the ImmiAccount TRN."*

---

## 10. Further information and the decision

**Requests for further information (s 56).** When the Department asks for more information, move the matter
to **Further Information** and enter **Information Due**: the date your response is due. It's required
(*"Enter the date the Department's request for more information must be answered by."*), shows on the
calendar, and reminds the case officer (else the RMA) 7 and 2 days before and on the day. The list
**Further Information Due** shows every open request.

**The decision.** A person with **Lodge Applications** records the **Outcome**: **Granted**, **Refused**,
**Withdrawn** or **Invalid**, plus the **Grant Number** and **Visa Expiry** for a grant. It can only be
recorded on a lodged matter: *"Record the decision once the application has been lodged."*

Recording an outcome:
- sets the **Decision Date** to today if it's empty;
- moves the matter to **Decision** and its **Status** to **Closed** (Withdrawn for a withdrawn
  application), so it leaves active matters and workload counts;
- calculates **Processing Time (days)** from lodgement to decision.

The visa expiry reminder still arrives for a closed, granted matter.

---

## 11. Client account (trust)

Only **Accounts** staff (and System Administrators) can record client-account money; Practice Managers, RMAs
and Auditors can read the ledger for every client.

**Client Account → New**, or from the matter (**Related → Client Account → New**):

| Type | Use for | Rules |
|---|---|---|
| **Deposit** | Money received from the client in advance (fees, VAC). | Positive amount. |
| **Withdrawal** | Money paid out on the client's behalf (e.g. a visa application charge). | Can't take the client's balance below zero. |
| **Transfer to Office** | Paying your own invoice from the client account. | Needs an **issued, unpaid invoice for the same client**; can't exceed its balance due. Records the payment on the invoice. |

Always choose the **Client**; link the **Matter** too (it must belong to that client). Client money can
only pay that client's own invoice: *"The invoice is for a different client."* The system numbers each
entry (`TRX-000000`), works out the **Client Balance After**, and locks the client while posting so two
withdrawals at once can't overdraw the account.

**The ledger can't be edited or deleted.** To correct a mistake, record a correcting entry and explain it in
**Description**: *"Client-account transactions can't be changed or deleted; record a correcting
transaction."*

**Client account statement.** On a client, **⌄ More actions → Client Account Statement** shows every
deposit, withdrawal and transfer with the running balance. Use **Print or save as PDF** to give it to the
client when they ask.

**Retention:** a matter with client-account transactions can't be deleted (7-year retention), and a client
with client-account transactions within the retention period can't have their personal data erased.

The report **Client Account Balances** shows the balance held for each client.

---

## 12. Billing

Create invoices under **Invoices → New** (or from the matter's **Related → Invoices**), linking the matter.
For an individual client leave **Organisation** empty: the client is billed in their own name (one billing
record, created once and reused). Add lines for your professional fee and any disbursements, then **Issue
Invoice**. Use **PDF** on the invoice for the tax invoice, and **Void Invoice** to cancel an issued one.
Payments are recorded on the invoice; a **Transfer to Office** from the client account records the payment
for you. Status moves Draft → Issued → Partially Paid → Paid.

---

## 13. Deadlines and expiry reminders

Reminders arrive in the bell menu (change the lead times in Practice Settings):

| What | Where it's recorded | When | Reminder goes to |
|---|---|---|---|
| Lodge-by deadline | Matter: **Lodge By** | 14, 7 and 2 days before (until lodged) | Case Officer, else Responsible RMA |
| Further information due | Matter: **Information Due** | 7 and 2 days before, and on the day | Case Officer, else Responsible RMA |
| Visa expiry (granted visa) | Matter: **Visa Expiry** | 90 and 30 days before | Responsible RMA (else the matter's owner) |
| Passport expiry | Client: **Passport Expiry** | 90 and 30 days before | The client's owner |
| Current visa expiry | Client: **Current Visa Expiry** | 90 and 30 days before | The client's owner |
| Sponsorship expiry | Organisation: **Sponsorship Expiry** | 90 and 30 days before | The organisation's owner |

The calendar shows lodge-by, information-due and visa expiry dates in amber. The **Visas Expiring (90
days)** and **Lodgement Deadlines** list views and the **Upcoming Visa Expiries** report show what's coming
up across the practice; expiries are a good source of repeat work. Reminders are a safety net, not a
substitute for your diary system.

---

## 14. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Client Portal**. The invitation e-mail
comes from your practice's name. Once signed in they see:
- their matters: stage, visa type and key dates. They don't see fees, the case officer or RMA, the
  agreement-gate override, processing time or your internal notes;
- their **document checklist**, with each item's status, where they upload documents and press **I've
  Uploaded This**;
- their **service agreements**, with the agent's name and MARN, to read and **Sign Agreement**;
- their invoices;
- **New Client Request** to send you a question, and a conversation and files area on each matter.

They're e-mailed when an agreement is waiting for their signature and when you send a document reminder.

---

## 15. Reports and dashboard

**Practice Dashboard** (also summarised on Home): matters by stage, grant rate, agent workload, matters by visa
type and upcoming visa expiries.

**Reports** (Reports tab → *Migration Practice Reports*):

| Report | Shows |
|---|---|
| Matters by Stage | Pipeline of active matters. |
| Matters by Visa Type | Mix of work by subclass. |
| Grant Rate | Outcomes: granted, refused, withdrawn, invalid. |
| Processing Time by Visa Type | Average days from lodgement to decision. |
| Client Account Balances | Money held per client. |
| Upcoming Visa Expiries | Granted visas expiring soon, with the responsible RMA. |
| Agent Workload | Active matters per RMA. |

**Useful list views on Matters:** *All Matters*, *My Matters*, *Active Matters*, *Further Information Due*,
*Lodgement Deadlines*, *Visas Expiring (90 days)*.

---

## 16. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New matters start at Consultation.* | Create the matter without choosing a later stage. |
| *A signed service agreement is needed before moving past Service Agreement (Code of Conduct).* | Send the agreement and wait for the client's signature, or ask a Practice Manager to override with a reason. |
| *Confirm the Consumer Guide has been provided (Code of Conduct).* | Give the client the Consumer Guide and tick **Consumer Guide Provided**. |
| *Add [agent]'s MARN in Setup → Users before sending the agreement…* | An administrator records the RMA's MARN on their user record. |
| *Choose the responsible RMA on the matter before sending the agreement.* | Set the Responsible RMA. |
| *Only the client can do this, from the client portal.* | Signing is the client's own act: invite them to the portal. |
| *Only agreements sent to you can be signed.* | (Client) The agreement hasn't been sent yet, or was already signed. |
| *Signed or cancelled agreements can't be changed.* | Create a new agreement. |
| *Only administrators can override the agreement gate.* | Ask a Practice Manager. |
| *Enter the reason for the override.* | Give the reason in the override box. |
| *Moving a matter to Lodged or beyond needs the Lodge Applications permission.* | Ask an RMA or Practice Manager to lodge. |
| *Enter the ImmiAccount TRN.* | Enter the TRN from ImmiAccount. |
| *The lodge-by date (…) has passed…* | The invitation or nomination has expired: a new one is needed. Correct the date if it was wrong. |
| *Choose the sponsoring employer before lodging an employer sponsored visa.* / *Enter the nomination TRN…* | Record the sponsor and the nomination TRN on the matter. |
| *Enter the date the Department's request for more information must be answered by.* | Fill in **Information Due**. |
| *Record the decision once the application has been lodged.* | Lodge first; a decision isn't recorded on an unlodged matter. |
| *Recording a decision needs the Lodge Applications permission.* | Ask an RMA or Practice Manager to record the outcome. |
| *Every requested document has been provided.* | Nothing to remind the client about. |
| *The matter belongs to a different client.* | Choose the right client or matter on the transaction. |
| *The invoice is for a different client.* | Client money pays only that client's invoice. |
| *Transfers to the office account need an issued, unpaid invoice.* | Issue the invoice first, then link it. |
| *The transfer is more than the invoice's balance due.* | Transfer no more than what's owing. |
| *Only transfers to office are linked to invoices.* | Remove the invoice from a deposit or withdrawal. |
| *The client account balance can't go negative (available …).* | Reduce the amount or record the deposit first. |
| *Client-account transactions can't be changed or deleted; record a correcting transaction.* | Post a correcting entry and explain it. |
| *Matters with client-account transactions must be kept (7-year retention).* | Close the matter instead of deleting it. |
| *Add the practice's ABN in Setup → Company & Branding before issuing tax invoices.* | Enter the ABN there. |
| *… isn't available for this record now.* | The action doesn't apply to the record as it stands. Refresh the page. |

---

## 17. Quick reference

**The life of a matter**

1. **Enquiry** (visa interest) → **Convert** → **Client** (with passport and visa details).
2. **New matter** (Consultation): choose the visa type; fees and the document checklist fill in. Record the
   lodge-by deadline and, for employer sponsored visas, the sponsor and nomination.
3. **Service agreement**: Consumer Guide ticked → **Send to Client** (agent and MARN recorded; client
   e-mailed) → client **signs** in the portal.
4. **Documents**: client uploads and presses I've Uploaded This; you mark items Received / Approved;
   **Send Document Reminder** for what's outstanding.
5. **Preparation** → **Ready to Lodge** → **Lodge Application** with the ImmiAccount TRN (before the
   lodge-by date).
6. **Further Information**: record Information Due; reminders until you respond.
7. **Decision**: record the outcome, grant number and visa expiry; the matter closes and processing time is
   calculated.
8. **Expiry reminders** 90 and 30 days before visa, passport and sponsorship expiries.

| I want to… | Do this |
|---|---|
| Set fees on a visa subclass | Visa Types → open it → Default fees and checklist |
| Open a file | Client → Related → Matters → New, choose the visa type |
| Add a dependant | Matter → Related → Applicants → New |
| Send the agreement | Matter → Related → Service Agreements → New → tick Consumer Guide → Send to Client |
| Chase documents | Matter → Send Document Reminder |
| Rebuild the checklist | Matter → Generate Checklist |
| Lodge | Stage path → Ready to Lodge → Lodge Application → TRN |
| Record a request for information | Stage path → Further Information → Information Due |
| Record the decision | Matter → Outcome, Grant Number, Visa Expiry |
| Receive client money | Client Account → New → Deposit |
| Pay my invoice from the client account | Issue invoice → Client Account → New → Transfer to Office → choose the invoice |
| Give a client their statement | Client → ⌄ More actions → Client Account Statement → Print or save as PDF |
| See expiring visas | Matters → Visas Expiring (90 days), or the calendar |
| Give a client access | Client → ⌄ More actions → Invite to Client Portal |
