# Loan Broking user guide

A practical guide for mortgage and finance brokers using Meridian CRM: principal brokers, brokers, loan
processors and commissions administrators. It follows a loan application from first enquiry to settlement
and commission. For general features (lists, search, records, reports) see the
[general user guide](user-guide.md); for who can do what, see [Roles and permissions](roles-and-permissions.md).

> The Loan Broking workspace supports your NCCP responsible lending and Best Interests Duty obligations
> (credit guide, consent, fact find, preliminary assessment, BID record, record keeping). It doesn't replace
> professional judgement: confirm requirements against current ASIC guidance and your licensee's policies.

**Contents**

1. [Your workspace at a glance](#1-your-workspace-at-a-glance)
2. [Who does what](#2-who-does-what)
3. [Before you start: set-up checklist](#3-before-you-start-set-up-checklist)
4. [From enquiry to client](#4-from-enquiry-to-client)
5. [Your lender panel](#5-your-lender-panel)
6. [Opening a loan application](#6-opening-a-loan-application)
7. [Credit guide and consent](#7-credit-guide-and-consent)
8. [Fact find](#8-fact-find)
9. [Preliminary assessment and Best Interests Duty](#9-preliminary-assessment-and-best-interests-duty)
10. [Lodging with a lender](#10-lodging-with-a-lender)
11. [Approval to settlement](#11-approval-to-settlement)
12. [Declined or withdrawn](#12-declined-or-withdrawn)
13. [Commissions](#13-commissions)
14. [Reminders and retention](#14-reminders-and-retention)
15. [Clients in the portal](#15-clients-in-the-portal)
16. [Reports and dashboard](#16-reports-and-dashboard)
17. [Messages you may see and what to do](#17-messages-you-may-see-and-what-to-do)
18. [Quick reference](#18-quick-reference)

---

## 1. Your workspace at a glance

The **Loan Broking** app opens as your home page. Its tabs:

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (New loan application, Lender panel, Commissions), your pipeline, tasks, recent records and the dashboard's key charts. |
| **Enquiries** | Prospective borrowers not yet engaged. |
| **Clients** | Borrowers, with residency, ID check and licence details. |
| **Loan Applications** | Every application, numbered `LA-2026-0001`, `LA-2026-0002`… |
| **Lenders** | Your lender panel, with BDMs and commission rates. |
| **Commissions** | The commission ledger: upfront, trail and clawbacks. |
| **Organisations** | Companies, employers and other entities. |
| **Calendar**, **Reports**, **Dashboards** | Diary, the practice's reports and the broker dashboard. |

**An application moves through these stages**, shown as a path across the top of the application:

```
Enquiry → Fact Find → Preliminary Assessment → Lodged → Conditional Approval → Valuation → Unconditional → Settlement → Settled
                                                                                                    (or Declined)
```

The system won't let an application past **Fact Find** until the credit guide and consent are recorded, and
won't let it be **lodged** until the preliminary assessment and Best Interests Duty record are done.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Principal Broker** | Credit licensee / principal | Everything on every application, the lender panel and the commission ledger; **submit to lender**; **manage commissions**; import/export; reassign clients. |
| **Broker** | Credit representative | Their own clients and applications; fact finds and BID records; **submit to lender**; read lenders and commissions. |
| **Loan Processor** | Processor, assistant | Work on every application and fact find: prepare and track them with lenders through to settlement. |
| **Commissions Administrator** | Commissions / finance | Reconcile lender statements: **manage commissions**; maintain lenders; read every application. |

**Who sees an application.** Applications are private. An application is visible to its owner, its
**Broker** and **Loan Processor** (they get read/write access automatically), anyone above them in the role
hierarchy, and Principal Brokers, Loan Processors and Commissions Administrators (who see all
applications). Share one with anyone else from **⌄ More actions → Sharing**.

**Driver licence numbers** are encrypted. Only Principal Brokers, Brokers and Loan Processors see and edit
them.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: business name, ABN, Australian Credit Licence details in the address block, logo.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their principal.
3. **Lenders**: set up your panel with upfront and trail rates (section 5), so expected commissions are
   created at settlement.
4. **Import your clients** (Setup → Data → Import Data), including fixed-rate expiry dates on existing
   loans so reminders start working.

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, what they're looking for, source.
2. Follow up from the enquiry's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When they engage you, open the enquiry and choose **Convert**. The system checks for an existing client
   with the same details, then creates the **Client**. The enquiry becomes read-only.
4. On the client, record **Date of Birth**, **Residency Status**, **First Home Buyer**, **ID Verified (100
   points)** once you've sighted ID, and the **Driver Licence Number**.

---

## 5. Your lender panel

**Lenders → New**:

| Field | Notes |
|---|---|
| **Type** | Major Bank, Bank, Non-bank, Credit Union / Mutual, Private. |
| **Accreditation / Broker ID** | Your ID with this lender. |
| **Upfront Commission Rate** | Percentage of the loan amount; used to create the expected upfront commission at settlement. |
| **Trail Commission Rate (p.a.)** | For your reference and reconciliation. |
| **Clawback Period (months)** | How long upfront commission can be clawed back. |
| **BDM**, **BDM E-mail**, **BDM Phone** | Your business development manager. |
| **On Panel** | Untick when you stop using a lender. |

The **Lender Panel** list view shows your active lenders.

---

## 6. Opening a loan application

From the client's **Related** tab (Loan Applications → **New**) or **Loan Applications → New**:

| Field | Notes |
|---|---|
| **Primary Borrower** (required), **Co-borrower** | The clients applying. |
| **Purpose** (required) | Purchase – Owner Occupied, Purchase – Investment, Refinance, Construction, Equity Release, First Home Buyer, Commercial, Car / Asset Finance, Personal. |
| **Loan Amount**, **Security Value**, **Security Property** | The **LVR** is calculated from amount ÷ security value. |
| **Lender**, **Product**, **Interest Rate**, **Rate Type**, **Fixed Rate Expiry** | Rate type: Variable, Fixed or Split. |
| **Term (years)**, **Repayments** | Principal & Interest or Interest Only. |
| **Broker** | Defaults to you. |
| **Loan Processor** | Gets access automatically. |
| **Lender Reference** | The lender's application number, once lodged. |

**When you save:** the application gets its number (`LA-YYYY-0000`), the LVR is calculated, and the Broker and
Loan Processor get access. New applications start at **Enquiry** or **Fact Find**.

---

## 7. Credit guide and consent

Before providing credit assistance, record on the application:
- **Credit Guide Provided**: the date you gave the client your credit guide;
- **Privacy / Credit Check Consent**: the date the client consented to the privacy disclosure and credit
  check.

Without them, the application can't move past **Fact Find**: *"Give the client your credit guide before
providing credit assistance."* / *"Record the client's privacy and credit-check consent."*

---

## 8. Fact find

On the application: **Related → Fact Finds → New**:

| Field | Notes |
|---|---|
| **Employment** | PAYG Full-time, PAYG Part-time, Casual, Self-employed, Contractor, Retired, Other. |
| **Gross Annual Income**, **Other Annual Income** | Required before completing. |
| **Monthly Living Expenses** | Required before completing. |
| **Monthly Loan / Card Repayments** | Existing commitments. |
| **Dependants** | Number of dependants. |
| **Total Assets**, **Total Liabilities** | |
| **Expenses Verified (bank statements)** | Tick once you've checked expenses against statements. |

The system works out:
- **Net Position** = total assets − total liabilities;
- **Monthly Surplus (before new loan)** = monthly income − living expenses − existing repayments.

Set **Status** to **Complete** when done. Without income and living expenses: *"Enter income and living
expenses before completing the fact find."*

---

## 9. Preliminary assessment and Best Interests Duty

On the application, complete the **Best Interests Duty** record:

| Field | What to record |
|---|---|
| **Requirements and Objectives** | What the client needs and wants from the loan. |
| **Products Considered** | The products and lenders you compared. |
| **Why This Product Is in the Client's Best Interests** | Your reasons for the recommendation. |

Then choose **Record Preliminary Assessment**. It checks that:
- all three BID fields are filled: *"Complete the requirements, products considered and recommendation
  reasons first."*;
- the credit guide and consent are recorded: *"Record the credit guide and privacy consent first."*;
- there's a **completed fact find**: *"Complete a fact find (income, expenses, assets and liabilities)
  first."*

Recording it:
- ticks **Best Interests Duty Recorded** and sets **Preliminary Assessment Completed** to today;
- moves the application to **Preliminary Assessment** (if it was earlier);
- **locks the BID record**: *"The Best Interests Duty record is locked once the assessment is recorded."*;
- notes it in the audit log.

---

## 10. Lodging with a lender

Move the application to **Lodged** on the stage path. This needs:
- the preliminary assessment and BID record: *"Record the preliminary assessment and Best Interests Duty
  before lodging."*;
- a **Lender**: *"Choose the lender."*;
- the **Submit to Lender** permission (Principal Brokers and Brokers): *"Lodging with a lender needs the
  Submit to Lender permission."*

The **Lodged With Lender** date is set to today. Enter the **Lender Reference**.

---

## 11. Approval to settlement

Move through **Conditional Approval → Valuation → Unconditional → Settlement** as the lender progresses the
application. Record the **Approval Expiry** date when you have a conditional approval, and the **Settlement
Date** once booked.

When you move it to **Settled**:
- the **Settlement Date** is set (today, if empty);
- the **Next Rate Review** is set to a year after settlement;
- the **expected upfront commission** is created in the commission ledger (loan amount × the lender's upfront
  rate), and shown on the application as **Expected Upfront Commission**.

---

## 12. Declined or withdrawn

Move the application to **Declined** and record the **Decline Reason** (required): *"Record why the
application was declined or withdrawn."*

---

## 13. Commissions

Only people with **Manage Commissions** (Principal Brokers and Commissions Administrators) can record or
change commission: *"Recording commission needs the Manage Commissions permission."*

**Commissions → New**, or from the application:

| Field | Notes |
|---|---|
| **Loan Application** | Required. The **Lender** and **Broker** are filled from it. |
| **Type** | **Upfront**, **Trail** or **Clawback**. |
| **Amount** | Always enter a positive amount; a **Clawback** is recorded as a negative **Ledger Amount**. |
| **Statement Period**, **Statement Reference** | From the lender's commission statement. |
| **Status** | **Expected** or **Received**. **Received** fills the **Received** date. |

**Amounts can't be edited.** To correct one, record a clawback or a new entry: *"Commission amounts can't be
changed; record a clawback or a new entry."* You can still change the status (e.g. Expected → Received) and
the statement details.

The **Expected Commissions** list view shows what you're waiting to receive.

---

## 14. Reminders and retention

Reminders arrive in the bell menu for the application's **Broker** (else its owner):

| What | When |
|---|---|
| Settlement date | 7 days and 1 day before |
| Approval expiry | 14 days before |
| Fixed-rate expiry | 90 and 30 days before |
| Rate review | 7 days before |

Fixed-rate expiries and rate reviews are your best source of repeat business: the **Fixed Rates Expiring (90
days)** list view and **Fixed Rate Expiries** report show them across the business.

**Retention:** applications with a recorded preliminary assessment can't be deleted for **7 years**:
*"Preliminary assessments and BID records must be kept for 7 years."*

---

## 15. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Customer Portal**. Once signed in they see their
loan applications and progress, their invoices, and a way to send you requests, messages and documents.

---

## 16. Reports and dashboard

**Broker dashboard** (also summarised on Home): pipeline by stage, commission, settled volume by lender, broker
volume and upcoming settlements.

**Reports** (Reports tab → *Loan Broking Reports*):

| Report | Shows |
|---|---|
| Pipeline by Stage | Applications and value at each stage. |
| Settled Volume by Lender | Where your settled loans went. |
| Broker Volume (this year) | Settled volume per broker. |
| Commission by Type | Upfront, trail and clawbacks. |
| Commission Ledger by Lender | Net commission per lender. |
| Upcoming Settlements | Settlements booked soon. |
| Fixed Rate Expiries | Fixed rates coming off soon. |

**Useful list views on Loan Applications:** *All Applications*, *My Pipeline*, *Active Pipeline*, *Settling (30
days)*, *Fixed Rates Expiring (90 days)*.

---

## 17. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New applications start at Enquiry or Fact Find.* | Create the application at one of those stages. |
| *Give the client your credit guide before providing credit assistance.* | Enter the **Credit Guide Provided** date. |
| *Record the client's privacy and credit-check consent.* | Enter the **Privacy / Credit Check Consent** date. |
| *Enter income and living expenses before completing the fact find.* | Fill in income and monthly living expenses. |
| *Complete a fact find (income, expenses, assets and liabilities) first.* | Complete a fact find and set it to Complete. |
| *Complete the requirements, products considered and recommendation reasons first.* | Fill in the three BID fields. |
| *Record the credit guide and privacy consent first.* | Enter both dates on the application. |
| *The Best Interests Duty record is locked once the assessment is recorded.* | It can't be changed; add a note or task explaining any later change in circumstances. |
| *Record the preliminary assessment and Best Interests Duty before lodging.* | Use **Record Preliminary Assessment** first. |
| *Choose the lender.* | Set the **Lender**. |
| *Lodging with a lender needs the Submit to Lender permission.* | Ask a Broker or Principal Broker to lodge. |
| *Record why the application was declined or withdrawn.* | Fill in **Decline Reason**. |
| *Recording commission needs the Manage Commissions permission.* | Ask a Principal Broker or Commissions Administrator. |
| *Commission amounts can't be changed; record a clawback or a new entry.* | Record a Clawback (or new entry) for the difference. |
| *Preliminary assessments and BID records must be kept for 7 years.* | Leave the application; set it to Declined if it didn't proceed. |

---

## 18. Quick reference

**The life of a loan application**

1. **Enquiry** → **Convert** → **Client** (residency, ID check, licence).
2. **New application** (Enquiry / Fact Find): borrowers, purpose, amount, security; LVR calculated.
3. **Credit guide** and **privacy / credit-check consent** dates recorded.
4. **Fact find** completed (income, expenses, assets, liabilities).
5. **BID record** + **Record Preliminary Assessment** (locks the BID).
6. **Lodge** with the lender (Submit to Lender permission).
7. **Conditional Approval → Valuation → Unconditional → Settlement → Settled**: rate review and expected
   upfront commission created.
8. **Commissions** reconciled: Expected → Received; clawbacks as new entries.

| I want to… | Do this |
|---|---|
| Add a lender | Lenders → New (with upfront and trail rates) |
| Start an application | Client → Related → Loan Applications → New |
| Record the credit guide and consent | Application → Credit Guide Provided, Privacy / Credit Check Consent |
| Do the fact find | Application → Related → Fact Finds → New → Status: Complete |
| Record BID and assessment | Fill the three BID fields → Record Preliminary Assessment |
| Lodge | Choose the lender → stage path → Lodged |
| Settle | Stage path → Settled |
| Record a commission | Commissions → New |
| Record a clawback | Commissions → New → Type: Clawback |
| See expiring fixed rates | Loan Applications → Fixed Rates Expiring (90 days) |
| Give a client access | Client → ⌄ More actions → Invite to Customer Portal |
