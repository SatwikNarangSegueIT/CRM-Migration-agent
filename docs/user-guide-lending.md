# Loan Broking user guide

A practical guide for mortgage and finance brokers using Meridian CRM: principal brokers, brokers, loan
processors and commissions administrators. It follows a loan application from first enquiry to settlement
and commission. For general features (lists, search, records, reports) see the
[general user guide](user-guide.md); for who can do what, see [Roles and permissions](roles-and-permissions.md).

> The Loan Broking workspace supports your NCCP responsible lending and Best Interests Duty obligations:
> credit guide, credit quote and credit proposal disclosure, consent, a verified fact find, the preliminary
> assessment with a serviceability buffer, the BID record and 7-year record keeping. It doesn't replace
> professional judgement: confirm requirements against current ASIC guidance and your licensee's policies.

**Contents**

1. [Your workspace at a glance](#1-your-workspace-at-a-glance)
2. [Who does what](#2-who-does-what)
3. [Before you start: set-up checklist](#3-before-you-start-set-up-checklist)
4. [From enquiry to client](#4-from-enquiry-to-client)
5. [Your lender panel](#5-your-lender-panel)
6. [Opening a loan application](#6-opening-a-loan-application)
7. [Credit guide, consent, quote and proposal](#7-credit-guide-consent-quote-and-proposal)
8. [Fact find](#8-fact-find)
9. [Preliminary assessment and Best Interests Duty](#9-preliminary-assessment-and-best-interests-duty)
10. [Lodging with a lender](#10-lodging-with-a-lender)
11. [Approval to settlement](#11-approval-to-settlement)
12. [Declined or withdrawn](#12-declined-or-withdrawn)
13. [Commissions and clawbacks](#13-commissions-and-clawbacks)
14. [Reminders and retention](#14-reminders-and-retention)
15. [Clients in the portal](#15-clients-in-the-portal)
16. [Reports and dashboard](#16-reports-and-dashboard)
17. [Messages you may see and what to do](#17-messages-you-may-see-and-what-to-do)
18. [Quick reference](#18-quick-reference)

---

## 1. Your workspace at a glance

The **Loan Broking** app opens as your home page. Its tabs (tabs that don't fit the screen are under
**More**):

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (New loan application, Lender panel, Commissions), your pipeline, tasks, recent records and the dashboard's key charts. |
| **Enquiries** | Prospective borrowers not yet engaged, with their loan purpose and approximate amount. |
| **Clients** | Borrowers, with residency, ID check and licence details. |
| **Loan Applications** | Every application, numbered `LA-2026-0001`, `LA-2026-0002`… |
| **Lenders** | Your lender panel, with BDMs, commission rates and clawback terms. |
| **Commissions** | The commission ledger: upfront, trail and clawbacks. |
| **Organisations** | Companies, employers and other entities. |
| **Calendar** | Your events and tasks, plus each application's **settlement**, **approval expiry** and **fixed rate expiry** (amber). |
| **Reports**, **Dashboards** | The business's reports and the Broking Dashboard. |

**An application moves through these stages**, shown as a path across the top of the application:

```
Enquiry → Fact Find → Preliminary Assessment → Lodged → Conditional Approval → Valuation → Unconditional → Settlement → Settled
                                                                                                    (or Declined)
```

The system won't let an application past **Fact Find** until the credit guide and consent (and a credit
quote, if you charge a fee) are recorded, and won't let it be **lodged** until the preliminary assessment,
the Best Interests Duty record and the credit proposal disclosure are done. A **Settled** or **Declined**
application is finished: open a new application for new borrowing.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Principal Broker** | Credit licensee / principal | Everything on every application, the lender panel and the commission ledger; **submit to lender**; **manage commissions**; correct a finished application; import/export; reassign clients. |
| **Broker** | Credit representative | Their own clients and applications; fact finds and BID records; **submit to lender**; read lenders and the commission on their own loans. |
| **Loan Processor** | Processor, assistant | Work on every application and fact find: prepare and track them with lenders through to settlement. |
| **Commissions Administrator** | Commissions / finance | Reconcile lender statements: **manage commissions** (including expected commissions the system creates); maintain lenders; read every application. |

**Roles** (whose records someone sees) come named for a broking business:

```
Principal Broker
├── Broking Manager
│   └── Senior Broker
│       └── Broker
├── Processing Manager
│   └── Loan Processor
├── Marketing Manager
│   └── Marketing Coordinator
└── Finance Manager
    └── Commissions Administrator
```

Rename or rearrange them in **Setup → Roles**.

**Who sees an application.** Applications are private. An application is visible to its owner, its
**Broker** and **Loan Processor** (they get read/write access automatically, and lose it when they're
changed), anyone above them in the role hierarchy, and Principal Brokers, Loan Processors and Commissions
Administrators (who see all applications). **My Pipeline** means active applications you own or are the
Broker or Loan Processor on. Share one with anyone else from **⌄ More actions → Sharing**.

**Driver licence numbers** are encrypted. Only Principal Brokers, Brokers and Loan Processors see and edit
them.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding** (Setup → Settings): business name, **ABN**, Australian Credit Licence details in
   the address block, logo. A tax invoice can't be issued until the ABN is entered.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their principal.
   Record each broker's **credit representative number** (ASIC, 6 or 7 digits) on their user record.
3. **Lenders**: set up your panel with upfront and trail rates and clawback terms (section 5), so expected
   commissions and clawbacks are created for you.
4. **Practice Settings** (Setup → Settings → Practice Settings):

   | Setting | Default | Notes |
   |---|---|---|
   | Serviceability buffer | 3% above the product rate | APRA expects lenders to assess at least 3 percentage points above the loan rate. |
   | Minimum assessment rate | 0 (none) | A floor for the assessment rate. |
   | Keep assessments and BID records for | 7 years | NCCP record keeping. |
   | Settlement reminders | 7 and 1 days before | |
   | Approval expiry reminders | 14 days before | |
   | Fixed rate expiry reminders | 90 and 30 days before | |
   | Rate review reminders | 7 days before | |

5. **Import your clients** (Setup → Data → Import Data), including fixed-rate expiry dates on existing
   loans so reminders start working.

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, **Loan Purpose** (the same list as on the application),
   **Approximate Loan Amount** and **Source**.
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
| **Clawback Period (months)** | How long upfront commission can be clawed back after settlement. |
| **Clawback Halves After (months)** | If the lender claws back only half after a point (often 12 months), enter it here. |
| **BDM**, **BDM E-mail**, **BDM Phone** | Your business development manager. |
| **On Panel** | Untick when you stop using a lender. |

The **Lender Panel** list view shows your active lenders. Clients see a lender's name in the portal, never
your commission rates or BDM details.

---

## 6. Opening a loan application

From the client's **Related** tab (Loan Applications → **New**) or **Loan Applications → New**:

| Field | Notes |
|---|---|
| **Primary Borrower** (required), **Co-borrower** | The clients applying. |
| **Purpose** (required) | Purchase – Owner Occupied, Purchase – Investment, Refinance, Construction, Equity Release, First Home Buyer, Commercial, Car / Asset Finance, Personal. |
| **Loan Amount**, **Security Value**, **Security Property** | The **LVR** is calculated from amount ÷ security value; **LMI Likely** is ticked above 80%. |
| **Lender**, **Product**, **Interest Rate**, **Rate Type**, **Fixed Rate Expiry** | Rate type: Variable, Fixed or Split. |
| **Term (years)**, **Repayments** | Principal & Interest or Interest Only. |
| **Broker** | Leave empty to make it you. |
| **Loan Processor** | Gets access automatically. |
| **Lender Reference** | The lender's application number, once lodged. |

**When you save:** the application gets its number (`LA-YYYY-0000`); the LVR and LMI flag are calculated; with
a rate, amount and term, the **Assessment Rate** (the rate plus the serviceability buffer) and the **Monthly
Repayment at Assessment Rate** are worked out; and the Broker and Loan Processor get access. New applications
start at **Enquiry** or **Fact Find**.

---

## 7. Credit guide, consent, quote and proposal

Record these in the application's **Credit Compliance (NCCP)** section:

| Field | When | Needed before |
|---|---|---|
| **Credit Guide Provided** | When you first deal with the client: your credit guide. | Moving past Fact Find. |
| **Privacy / Credit Check Consent** | The client's consent to the privacy disclosure and credit check. | Moving past Fact Find. |
| **Broker Fee to Client**, **Credit Quote Given** | Only if the client pays you a fee: give them a credit quote first (NCCP s 114). | Moving past Fact Find. |
| **Credit Proposal Disclosure Given** | The fees, charges and commissions involved in the loan you'll apply for (NCCP s 121). | Lodging with the lender. |

Without them: *"Give the client your credit guide before providing credit assistance."* / *"Record the
client's privacy and credit-check consent."* / *"A fee is charged to the client: give them a credit quote
first (NCCP s 114)."* / *"Give the client the credit proposal disclosure (fees, charges and commissions)
before applying to the lender (NCCP s 121)."*

---

## 8. Fact find

On the application: **Related → Fact Finds → New**:

| Field | Notes |
|---|---|
| **Employment** | PAYG Full-time, PAYG Part-time, Casual, Self-employed, Contractor, Retired, Other. |
| **Gross Annual Income**, **Other Annual Income** | Required before completing. |
| **Monthly Living Expenses** | Required before completing. |
| **Monthly Loan / Card Repayments** | Existing commitments (leave out a debt the new loan will pay off). |
| **Dependants** | Number of dependants. |
| **Total Assets**, **Total Liabilities** | |
| **Expenses Verified (bank statements)** | Tick once you've verified income (payslips, tax returns) and expenses (bank statements). Needed for the assessment. |

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

Enter the product's **Interest Rate** and the **Term**, then choose **Record Preliminary Assessment**. It
checks that:
- all three BID fields are filled: *"Complete the requirements, products considered and recommendation
  reasons first."*;
- the credit guide and consent are recorded: *"Record the credit guide and privacy consent first."*;
- there's a **completed fact find**: *"Complete a fact find (income, expenses, assets and liabilities)
  first."*, and its income and expenses are **verified**;
- there's a rate and term to assess: *"Enter the product's interest rate and the loan term to assess the
  repayments."*;
- the loan isn't unsuitable: the **repayment at the assessment rate** must fit within the latest completed
  fact find's **monthly surplus**. Otherwise: *"The loan looks unsuitable: repayments of $… a month at the
  …% assessment rate exceed the client's monthly surplus of $… (NCCP: they could only repay with substantial
  hardship)."*

Recording it:
- ticks **Best Interests Duty Recorded** and sets **Preliminary Assessment Completed** to today;
- moves the application to **Preliminary Assessment** (if it was earlier);
- **locks the BID record**: *"The Best Interests Duty record is locked once the assessment is recorded."*;
- notes it in the audit log.

**If the loan changes before lodging** (the amount, purpose or primary borrower, or a switch to a different
lender or co-borrower), the assessment no longer fits the loan: **Best Interests Duty Recorded** is cleared,
the change is noted in the audit log, and you record the assessment again (the BID record unlocks so you can
update it).

---

## 10. Lodging with a lender

Move the application to **Lodged** on the stage path. This needs:
- the preliminary assessment and BID record: *"Record the preliminary assessment and Best Interests Duty
  before lodging."*;
- a **current** assessment, made within the last 90 days (120 days for buying residential property:
  Purchase – Owner Occupied, Purchase – Investment, First Home Buyer), as NCCP s 115 requires: *"The
  preliminary assessment was made on …, more than 90 days ago: record it again before applying to the
  lender (NCCP s 115)."* An expired assessment can be recorded again (and its BID record brought up to
  date) with **Record Preliminary Assessment**;
- a **Lender**: *"Choose the lender."*;
- the **Credit Proposal Disclosure Given** date (section 7);
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

A settled application stays editable for its rate details (fixed rate expiry, rate review), but its stage
can't be changed: *"The application is Settled; open a new application instead."* A Principal Broker can
correct a mistake.

**When the loan is repaid or refinanced away**, choose **Record Discharge** on the application and enter the
date. Within the lender's clawback period an **expected clawback** of the upfront commission is created:
all of it, or half after the lender's halving point.

---

## 12. Declined or withdrawn

Move the application to **Declined** and record the **Decline Reason** (required): *"Record why the
application was declined or withdrawn."*

---

## 13. Commissions and clawbacks

Only people with **Manage Commissions** (Principal Brokers and Commissions Administrators) can record or
change commission: *"Recording commission needs the Manage Commissions permission."* Brokers can read the
commission on their own loans.

**Commissions → New**, or from the application:

| Field | Notes |
|---|---|
| **Loan Application** | Required. The **Lender** and **Broker** are filled from it. |
| **Type** | **Upfront**, **Trail** or **Clawback**. |
| **Amount** | Always positive: a **Clawback** is recorded as a negative **Ledger Amount**. |
| **Statement Period**, **Statement Reference** | From the lender's commission statement. |
| **Status** | **Expected** or **Received**. **Received** fills the **Received** date. |

**Amounts can't be edited.** To correct one, record a clawback or a new entry: *"Commission amounts can't be
changed; record a clawback or a new entry."* You can still change the status (e.g. Expected → Received) and
the statement details, including on the expected upfront commissions and clawbacks the system creates.

The **Expected Commissions** list view shows what you're waiting to receive (or to be clawed back).

---

## 14. Reminders and retention

Reminders arrive in the bell menu for the application's **Broker** (else its owner); change the lead times
in Practice Settings:

| What | When | Stops when |
|---|---|---|
| Settlement date | 7 days and 1 day before | The application is settled or declined |
| Approval expiry | 14 days before | The application is settled or declined |
| Fixed-rate expiry | 90 and 30 days before | The application is declined or the loan discharged |
| Rate review | 7 days before | The application is declined or the loan discharged |

The calendar shows settlements and fixed rate expiries (not for declined applications or discharged loans)
and approval expiries (until settled or declined) in amber. Fixed-rate expiries and rate reviews are your best source of repeat business: the **Fixed Rates
Expiring (90 days)** list view and **Fixed Rate Expiries** report show them across the business.

**Retention:** applications with a recorded preliminary assessment can't be deleted for **7 years** (the
Practice Settings period): *"Preliminary assessments and BID records must be kept for 7 years."*

---

## 15. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Client Portal**. The invitation comes from
your business's name. Once signed in they see their loan applications and progress (with the lender's name,
but not the broker or processor, products considered, commissions, the lender reference or decline notes),
their invoices, and **New Client Request** to send you a question, with a conversation and files area on
each application.

---

## 16. Reports and dashboard

**Broking Dashboard** (also summarised on Home): pipeline by stage, net commission by type, settled volume by
lender, broker volume and upcoming settlements.

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
| *A fee is charged to the client: give them a credit quote first (NCCP s 114).* | Give the credit quote and enter **Credit Quote Given**. |
| *Enter income and living expenses before completing the fact find.* | Fill in income and monthly living expenses. |
| *Complete a fact find (income, expenses, assets and liabilities) first.* | Complete a fact find and set it to Complete. |
| *Verify the client's income and expenses (payslips, bank statements) on the fact find before the assessment…* | Check the documents, then tick **Expenses Verified** on the fact find. |
| *Enter the product's interest rate and the loan term to assess the repayments.* | Fill in **Interest Rate** and **Term (years)**. |
| *The loan looks unsuitable: repayments of … exceed the client's monthly surplus…* | Review the loan amount, term or product; if the loan pays off a debt, take that repayment out of the fact find. |
| *Complete the requirements, products considered and recommendation reasons first.* | Fill in the three BID fields. |
| *Record the credit guide and privacy consent first.* | Enter both dates on the application. |
| *The Best Interests Duty record is locked once the assessment is recorded.* | It can't be changed; add a note or task explaining any later change in circumstances. |
| *Record the preliminary assessment and Best Interests Duty before lodging.* | Use **Record Preliminary Assessment** first (again, if the loan changed). |
| *The preliminary assessment was made on …, more than 90 days ago…* | Check the client's circumstances are unchanged (update the fact find and BID record if not) and choose **Record Preliminary Assessment** again. |
| *Give the client the credit proposal disclosure (fees, charges and commissions) before applying to the lender (NCCP s 121).* | Give the disclosure and enter **Credit Proposal Disclosure Given**. |
| *Choose the lender.* | Set the **Lender**. |
| *Lodging with a lender needs the Submit to Lender permission.* | Ask a Broker or Principal Broker to lodge. |
| *The application is Settled; open a new application instead.* | Start a new application for new borrowing (a Principal Broker can correct a mistake). |
| *Record why the application was declined or withdrawn.* | Fill in **Decline Reason**. |
| *Only settled loans can be discharged.* / *The discharge was recorded on …* | Discharge applies once, to a settled loan. |
| *Recording commission needs the Manage Commissions permission.* | Ask a Principal Broker or Commissions Administrator. |
| *Commission amounts can't be changed; record a clawback or a new entry.* | Record a Clawback (or new entry) for the difference. |
| *Preliminary assessments and BID records must be kept for 7 years.* | Leave the application; set it to Declined if it didn't proceed. |
| *Add the practice's ABN in Setup → Company & Branding before issuing tax invoices.* | Enter the ABN there. |
| *… isn't available for this record now.* | The action doesn't apply to the record as it stands. Refresh the page. |

---

## 18. Quick reference

**The life of a loan application**

1. **Enquiry** (loan purpose) → **Convert** → **Client** (residency, ID check, licence).
2. **New application** (Enquiry / Fact Find): borrowers, purpose, amount, security; LVR and LMI flag
   calculated.
3. **Credit guide** and **privacy / credit-check consent** recorded (and a **credit quote** if you charge a
   fee).
4. **Fact find** completed and verified (income, expenses, assets, liabilities).
5. **BID record**, rate and term → **Record Preliminary Assessment** (serviceability checked at the
   assessment rate; locks the BID).
6. **Credit proposal disclosure** given → **Lodge** with the lender within 90 days of the assessment (120 for
   a residential purchase; Submit to Lender permission).
7. **Conditional Approval → Valuation → Unconditional → Settlement → Settled**: rate review and expected
   upfront commission created.
8. **Commissions** reconciled: Expected → Received; **Record Discharge** creates any clawback.

| I want to… | Do this |
|---|---|
| Add a lender | Lenders → New (with upfront and trail rates and clawback terms) |
| Start an application | Client → Related → Loan Applications → New |
| Record the credit guide, consent and quote | Application → Credit Compliance (NCCP) |
| Do the fact find | Application → Related → Fact Finds → New → verify → Status: Complete |
| Record BID and assessment | Fill the three BID fields, rate and term → Record Preliminary Assessment |
| Lodge | Credit proposal date → choose the lender → stage path → Lodged |
| Settle | Stage path → Settled |
| Record a refinance away | Application → Record Discharge |
| Record a commission | Commissions → New |
| Record a clawback | Commissions → New → Type: Clawback (or Record Discharge) |
| Change the serviceability buffer | Setup → Settings → Practice Settings |
| See expiring fixed rates | Loan Applications → Fixed Rates Expiring (90 days), or the calendar |
| Give a client access | Client → ⌄ More actions → Invite to Client Portal |
