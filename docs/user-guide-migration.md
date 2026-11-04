# Migration Practice user guide

A practical guide for migration agencies using Meridian CRM: practice managers, registered migration agents
(RMAs), case officers, intake consultants and accounts staff. It follows a visa matter from first enquiry to
decision. For general features (lists, search, records, reports) see the [general user guide](user-guide.md);
for who can do what, see [Roles and permissions](roles-and-permissions.md).

> The Migration Practice workspace supports your obligations under the Code of Conduct for registered
> migration agents (service agreements, Consumer Guide, client account). It doesn't replace professional
> judgement: confirm requirements against current guidance from the Office of the MARA and the Department.

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
13. [Expiry reminders](#13-expiry-reminders)
14. [Clients in the portal](#14-clients-in-the-portal)
15. [Reports and dashboard](#15-reports-and-dashboard)
16. [Messages you may see and what to do](#16-messages-you-may-see-and-what-to-do)
17. [Quick reference](#17-quick-reference)

---

## 1. Your workspace at a glance

The **Migration Practice** app opens as your home page. Its tabs:

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Open a matter, Add a client), your active matters, tasks, recent records and the practice dashboard's key charts. |
| **Enquiries** | Prospective clients not yet engaged. |
| **Clients** | Applicants and other people you act for, with passport and visa details. |
| **Organisations** | Employers and sponsors. |
| **Matters** | Every visa application, numbered `MAT-2026-0001`, `MAT-2026-0002`… |
| **Visa Types** | Your library of visa subclasses with default fees and document checklists. |
| **Invoices** | Bills to clients. |
| **Client Account** | The client account (trust) ledger. |
| **Calendar**, **Reports** | Diary and the practice's reports. |

**A matter moves through eight stages**, shown as a path across the top of the matter:

```
Consultation → Service Agreement → Document Collection → Preparation → Ready to Lodge → Lodged → Further Information → Decision
```

The system won't let a matter go past **Service Agreement** until the client has signed one, and only people
with the **Lodge Applications** permission can lodge or record a decision.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Practice Manager** | Principal / practice owner | Everything on every matter; visa types; **lodge**; **override the agreement gate**; read the client account and invoices; import/export; reassign files. |
| **Registered Migration Agent** | RMA (MARA-registered) | Every matter; agreements; checklists; invoices; **lodge** and record decisions. |
| **Case Officer** | Case officer, paralegal | Matters where they're the Case Officer or Responsible RMA; applicants and checklist items. |
| **Intake Consultant** | Front desk, intake | Enquiries, clients and converting enquiries; open new matters. |
| **Accounts** | Bookkeeper, accounts | The **client account** ledger (deposits, withdrawals, transfers); invoices and payments; read every matter. |
| **Practice Auditor** | Auditor | Read everything, including the client account; change nothing. |

**Who sees a matter.** Matters are private. A matter is visible to its owner, its **Responsible RMA** and
**Case Officer** (they get read/write access automatically, and lose it when they're changed), anyone above
them in the role hierarchy, and Practice Managers, RMAs, Accounts and Auditors (who see all matters). Share a
matter with anyone else from **⌄ More actions → Sharing**.

**Passport numbers** are encrypted. Only Practice Managers, RMAs and Accounts can see and edit them (Auditors
can read them); everyone else doesn't see the field.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: practice name, ABN, address and logo. They appear on invoices.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their
   supervisor. Record each RMA's **MARA number** on their user record.
3. **Billing**: invoice numbering, payment terms and GST.
4. **Visa Types**: set up the subclasses you handle (section 5). This is what makes new matters quick.
5. **Import your clients** (Setup → Data → Import Data), with passport and visa expiry dates so reminders
   start working straight away.

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, what visa they're interested in, source.
2. Follow up from the enquiry's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When they become a client, open the enquiry and choose **Convert**. The system checks for an existing
   client with the same details, then creates the **Client** (and **Organisation** for an employer or
   sponsor). The enquiry becomes read-only.
4. On the client, record: **Citizenship**, **Country of Birth**, **Passport Number** and **Passport Expiry**,
   **Current Visa** and **Current Visa Expiry**, **In Australia**, and **Privacy Act Consent** (with its
   date).
5. For a sponsoring employer (organisation): tick **Approved Sponsor** and enter the **Sponsorship
   Approved** and **Sponsorship Expiry** dates.

---

## 5. Opening a matter

**Set up visa types first.** Visa Types → New:

| Field | Notes |
|---|---|
| **Subclass**, **Stream**, **Category** | e.g. 482, Core Skills, Employer Sponsored. |
| **Default Professional Fee** | Your usual fee; copied to new matters. |
| **Default Government Fee (VAC)** | The visa application charge; copied to new matters. |
| **Document Checklist** | One document per line, e.g. "Passport bio page", "Skills assessment". Copied to each new matter as its checklist. |
| **Active** | Untick to retire a visa type. |

**Then open the matter** from the client's **Related** tab (Matters → **New**) or **Matters → New**:

| Field | Notes |
|---|---|
| **Client** (required) | The main applicant. |
| **Sponsor** | The sponsoring organisation, if any. |
| **Visa Type** | Choosing it fills the fees and creates the document checklist. |
| **Priority**, **Applicant Location** | Normal/High/Urgent; Onshore/Offshore. |
| **Responsible RMA**, **Case Officer** | Both get access to the matter automatically. |
| **Professional Fee**, **Government Fee (VAC)** | Filled from the visa type; change if needed. |
| **Visa Expiry** | Once granted; drives reminders. |

**When you save:**
- the matter gets its number (`MAT-YYYY-0000`);
- the fees come from the visa type (if you left them blank);
- the **document checklist** is created from the visa type's template;
- the Responsible RMA and Case Officer get access.

New matters always start at **Consultation**. If you change the visa type later and the matter has no
checklist yet, the new type's checklist is created. **Generate Checklist** on the matter re-creates it from
the visa type at any time.

---

## 6. Applicants

On the matter: **Related → Applicants → New**. Add everyone on the application: **Primary**, **Secondary**,
**Dependent**, **Sponsor**, **Nominator**. Each applicant is a client record, so their passport and visa
details (and expiry reminders) are kept in one place.

---

## 7. Service agreements

The Code of Conduct requires a written agreement before you work on the matter.

1. On the matter: **Related → Service Agreements → New**. The fees come from the matter; add the **Scope of
   Services** (required) and **Estimated Disbursements**.
2. Give the client the **Consumer Guide** and tick **Consumer Guide Provided**.
3. Choose **Send to Client**. Without the Consumer Guide tick you'll see *"Confirm the Consumer Guide has
   been provided (Code of Conduct)."* Sending moves the matter from Consultation to **Service Agreement**.
4. The client opens it in the portal and chooses **Sign Agreement**: they type their full name and accept.
   The system records **Signed By**, **Signed** (time) and **Signed From IP**, and notes it in the audit log.

Agreements go **Draft → Sent → Signed** (or Cancelled). Signed or cancelled agreements can't be changed;
create a new one if the scope changes.

**The agreement gate.** A matter can't move past Service Agreement without a signed agreement: *"A signed
service agreement is needed before moving past Service Agreement (Code of Conduct)."* For a genuine
exception, a Practice Manager can choose **Override Agreement Gate** on the matter and give a reason. The
override is recorded in the audit log and shown on the matter (**Agreement Gate Overridden**).

---

## 8. Document checklist

The matter's **Related → Document Checklist** lists every document needed. Each item has:

| Field | Notes |
|---|---|
| **Status** | Requested → Received → Approved, or Not Required. |
| **Due Date** | When you need it. |
| **Visible to Client** | On by default: the client sees the item in the portal and can upload against it. |
| **Notes** | The client can read these. |

Add items with **New**, or **Generate Checklist** on the matter to rebuild from the visa type. Move the matter
to **Document Collection** while you're gathering documents and **Preparation** while you're preparing the
application.

---

## 9. Lodging the application

1. Move the matter to **Ready to Lodge**.
2. A person with the **Lodge Applications** permission (Practice Manager or RMA) chooses **Lodge
   Application** on the matter and enters the **ImmiAccount TRN** (required).
3. The matter moves to **Lodged** and the **Lodgement Date** is set.

Without the permission: *"Moving a matter to Lodged or beyond needs the Lodge Applications permission."*
Without a TRN: *"Enter the ImmiAccount TRN."*

---

## 10. Further information and the decision

- Move the matter to **Further Information** while you respond to requests from the Department.
- When the decision arrives, a person with **Lodge Applications** records the **Outcome**: **Granted**,
  **Refused**, **Withdrawn** or **Invalid**, plus the **Grant Number** and **Visa Expiry** for a grant.

Recording an outcome:
- sets the **Decision Date** to today if it's empty;
- moves the matter to **Decision**;
- calculates **Processing Time (days)** from lodgement to decision.

Set **Status** to Closed (or Withdrawn) when the file is finished.

---

## 11. Client account (trust)

Only **Accounts** staff (and System Administrators) can record client-account money; Practice Managers, RMAs
and Auditors can read the ledger.

**Client Account → New**, or from the matter (**Related → Client Account → New**):

| Type | Use for | Rules |
|---|---|---|
| **Deposit** | Money received from the client in advance (fees, VAC). | Positive amount. |
| **Withdrawal** | Money paid out on the client's behalf (e.g. a visa application charge). | Can't take the client's balance below zero. |
| **Transfer to Office** | Paying your own invoice from the client account. | Needs an **issued, unpaid invoice**; can't exceed its balance due. Records the payment on the invoice. |

Always choose the **Client**; link the **Matter** too (it must belong to that client). The system numbers each
entry (`TRX-000000`), works out the **Client Balance After**, and locks the client while posting so two
withdrawals at once can't overdraw the account.

**The ledger can't be edited or deleted.** To correct a mistake, record a correcting entry and explain it in
**Description**: *"Client-account transactions can't be changed or deleted; record a correcting
transaction."*

**Retention:** a matter with client-account transactions can't be deleted (7-year retention), and a client
with client-account transactions within the retention period can't have their personal data erased.

The report **Client Account Balances** shows the balance held for each client.

---

## 12. Billing

Create invoices under **Invoices → New** (or from the matter's **Related → Invoices**), linking the matter. Add
lines for your professional fee and any disbursements, then **Issue Invoice**. Use **PDF** on the invoice to
download it, and **Void Invoice** to cancel an issued one. Payments are recorded on the invoice; a
**Transfer to Office** from the client account records the payment for you. Status moves Draft → Issued →
Partially Paid → Paid.

---

## 13. Expiry reminders

Reminders arrive in the bell menu, 90 and 30 days before each date:

| What | Where it's recorded | Reminder goes to |
|---|---|---|
| Visa expiry (granted visa) | Matter: **Visa Expiry** | Responsible RMA (else the matter's owner) |
| Passport expiry | Client: **Passport Expiry** | The client's owner |
| Current visa expiry | Client: **Current Visa Expiry** | The client's owner |
| Sponsorship expiry | Organisation: **Sponsorship Expiry** | The organisation's owner |

The **Visas Expiring (90 days)** list view and the **Upcoming Visa Expiries** report show what's coming up
across the practice; they're a good source of repeat work. Reminders are a safety net, not a substitute for
your diary system.

---

## 14. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Customer Portal**. Once signed in they see:
- their matters: stage and key dates. They don't see fees, the case officer or RMA, the agreement-gate
  override, processing time or your internal notes;
- their **document checklist**, where they can upload documents against each item;
- their **service agreements**, to read and **Sign Agreement**;
- their invoices;
- a way to send you requests and messages.

---

## 15. Reports and dashboard

**Practice Dashboard** (also summarised on Home): matters by stage, grant rate, agent workload, matters by visa
type and upcoming visa expiries.

**Reports** (Reports tab → *Migration Practice Reports*):

| Report | Shows |
|---|---|
| Matters by Stage | Pipeline of open matters. |
| Matters by Visa Type | Mix of work by subclass. |
| Grant Rate | Outcomes: granted, refused, withdrawn, invalid. |
| Processing Time by Visa Type | Average days from lodgement to decision. |
| Client Account Balances | Money held per client. |
| Upcoming Visa Expiries | Granted visas expiring soon, with the responsible RMA. |
| Agent Workload | Open matters per RMA. |

**Useful list views on Matters:** *All Matters*, *My Matters*, *Active Matters*, *Visas Expiring (90 days)*.

---

## 16. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New matters start at Consultation.* | Create the matter without choosing a later stage. |
| *A signed service agreement is needed before moving past Service Agreement (Code of Conduct).* | Send the agreement and wait for the client's signature, or ask a Practice Manager to override with a reason. |
| *Confirm the Consumer Guide has been provided (Code of Conduct).* | Give the client the Consumer Guide and tick **Consumer Guide Provided**. |
| *Only agreements sent to you can be signed.* | (Client) The agreement hasn't been sent yet, or was already signed. |
| *Signed or cancelled agreements can't be changed.* | Create a new agreement. |
| *Only administrators can override the agreement gate.* | Ask a Practice Manager. |
| *Enter the reason for the override.* | Give the reason in the override box. |
| *Moving a matter to Lodged or beyond needs the Lodge Applications permission.* | Ask an RMA or Practice Manager to lodge. |
| *Lodging needs the Lodge Applications permission.* | As above. |
| *Enter the ImmiAccount TRN.* | Enter the TRN from ImmiAccount. |
| *Recording a decision needs the Lodge Applications permission.* | Ask an RMA or Practice Manager to record the outcome. |
| *The matter belongs to a different client.* | Choose the right client or matter on the transaction. |
| *Transfers to the office account need an issued, unpaid invoice.* | Issue the invoice first, then link it. |
| *The transfer is more than the invoice's balance due.* | Transfer no more than what's owing. |
| *Only transfers to office are linked to invoices.* | Remove the invoice from a deposit or withdrawal. |
| *The client account balance can't go negative (available …).* | Reduce the amount or record the deposit first. |
| *Client-account transactions can't be changed or deleted; record a correcting transaction.* | Post a correcting entry and explain it. |
| *Matters with client-account transactions must be kept (7-year retention).* | Close the matter instead of deleting it. |

---

## 17. Quick reference

**The life of a matter**

1. **Enquiry** → **Convert** → **Client** (with passport and visa details).
2. **New matter** (Consultation): choose the visa type; fees and the document checklist fill in.
3. **Service agreement**: Consumer Guide ticked → **Send to Client** → client **signs** in the portal.
4. **Documents**: client uploads against the checklist; you mark items Received / Approved.
5. **Preparation** → **Ready to Lodge** → **Lodge Application** with the ImmiAccount TRN.
6. **Further Information** while responding to the Department.
7. **Decision**: record the outcome, grant number and visa expiry; processing time is calculated.
8. **Expiry reminders** 90 and 30 days before visa, passport and sponsorship expiries.

| I want to… | Do this |
|---|---|
| Set up a visa subclass | Visa Types → New (fees and checklist template) |
| Open a file | Client → Related → Matters → New, choose the visa type |
| Add a dependant | Matter → Related → Applicants → New |
| Send the agreement | Matter → Related → Service Agreements → New → tick Consumer Guide → Send to Client |
| Rebuild the checklist | Matter → Generate Checklist |
| Lodge | Stage path → Ready to Lodge → Lodge Application → TRN |
| Record the decision | Matter → Outcome, Grant Number, Visa Expiry |
| Receive client money | Client Account → New → Deposit |
| Pay my invoice from the client account | Issue invoice → Client Account → New → Transfer to Office → choose the invoice |
| See expiring visas | Matters → Visas Expiring (90 days) |
| Give a client access | Client → ⌄ More actions → Invite to Customer Portal |
