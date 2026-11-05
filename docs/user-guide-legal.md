# Legal Practice user guide

A practical guide for law firms using Meridian CRM: principals, solicitors, paralegals and trust accountants.
It follows a matter from first enquiry to closed file. For general features (lists, search, records,
reports) see the [general user guide](user-guide.md); for who can do what, see
[Roles and permissions](roles-and-permissions.md).

> The Legal Practice workspace supports your obligations under the Legal Profession Uniform Law and the
> Uniform General Rules (conflicts, costs disclosure, trust accounting). It doesn't replace professional
> judgement: confirm thresholds and procedures against your law society's current guidance.

**Contents**

1. [Your workspace at a glance](#1-your-workspace-at-a-glance)
2. [Who does what](#2-who-does-what)
3. [Before you start: set-up checklist](#3-before-you-start-set-up-checklist)
4. [From enquiry to client](#4-from-enquiry-to-client)
5. [Opening a matter](#5-opening-a-matter)
6. [Conflict checks](#6-conflict-checks)
7. [Engaging: costs disclosure](#7-engaging-costs-disclosure)
8. [Parties](#8-parties)
9. [Recording time](#9-recording-time)
10. [Billing](#10-billing)
11. [Trust accounting](#11-trust-accounting)
12. [Monthly trust reconciliation](#12-monthly-trust-reconciliation)
13. [Court dates and limitation dates](#13-court-dates-and-limitation-dates)
14. [Closing a matter](#14-closing-a-matter)
15. [Clients in the portal](#15-clients-in-the-portal)
16. [Reports and dashboard](#16-reports-and-dashboard)
17. [Messages you may see and what to do](#17-messages-you-may-see-and-what-to-do)
18. [Quick reference](#18-quick-reference)

---

## 1. Your workspace at a glance

The **Legal Practice** app opens as your home page. Its tabs (tabs that don't fit the screen are under
**More**):

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Open a matter, Record time, Trust ledger), your matters, tasks, recent records and the practice dashboard's key charts. |
| **Enquiries** | Prospective clients not yet engaged, with the area of law they need. |
| **Clients** | People you act for (with date of birth and identity verification). |
| **Organisations** | Companies and other entities (with ACN). |
| **Matters** | Every file, numbered `LM-2026-0001`, `LM-2026-0002`… |
| **Time Entries** | Time recorded in 6-minute units. |
| **Trust Ledger** | Receipts, payments and transfers to office. |
| **Trust Reconciliations** | The monthly reconciliation of the trust account (section 12). |
| **Invoices** | Bills to clients. |
| **Calendar** | Your events and tasks, plus **court dates** and **limitation dates** (amber). |
| **Reports**, **Dashboards** | The practice's reports and the Practice Dashboard. |

**A matter moves through six stages**, shown as a path across the top of the matter:

```
Intake → Conflict Check → Engaged → Active → Settlement/Hearing → Closed
```

The system won't let a matter reach **Engaged** until the conflict check is clear, costs disclosure is
recorded (where it's required), the client's identity is verified for conveyancing, and a limitation date
is recorded for claims. It won't let a matter **close** while there is unbilled time or money in trust.

"**My Matters**" (the list view and the home card) means matters you own **or** are the Responsible
Solicitor or Supervising Principal on.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Principal** | Legal practitioner director, partner | Everything on every matter (including solicitors' matters); **clear conflicts**; **write off time**; **trust ledger**; **sign off trust reconciliations**; import/export; reassign files. |
| **Solicitor** | Employed solicitor | Open and run their own matters; record time; add parties and court dates; raise invoices; read the trust ledger. |
| **Paralegal** | Paralegal, law clerk | Work on matters shared with them; add parties and court dates; record time. |
| **Trust Accountant** | Accounts / trust officer | **Trust ledger** (receipts, payments, transfers), **prepares trust reconciliations**, invoices and payments; reads every matter. |
| **External Examiner** | Annual trust examiner | Reads matters, the trust ledger and reconciliations; changes nothing. |

**Roles** (where someone sits, and so whose records they see) come named for a law firm:

```
Managing Principal
├── Principal
│   └── Senior Associate
│       └── Solicitor
├── Practice Manager
│   └── Paralegal
├── Business Development Manager
│   └── Business Development Coordinator
└── Finance Manager
    └── Trust Accountant
```

Rename or rearrange them in **Setup → Roles**. A role you rename keeps your name.

**Who sees a matter.** Matters are private. A matter is visible to its owner, the **Responsible Solicitor**
and the **Supervising Principal** (they get read/write access automatically), anyone above them in the
role hierarchy, and Principals, Trust Accountants and Examiners (who see all matters). Share a matter with
anyone else from **⌄ More actions → Sharing**.

**Practising certificate numbers.** Record each solicitor's practising certificate number on their user
record (**Setup → Users**).

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: firm name, **ABN**, address and logo. They appear on invoices, and **an invoice
   can't be issued until the ABN is entered** (a tax invoice must show it).
2. **Users**: add each person with the right **profile** (table above), a **role** under their supervisor,
   and their practising certificate number.
3. **Practice Settings** (Setup → Settings → Practice Settings):

   | Setting | Shipped value | What it does |
   |---|---|---|
   | Default hourly rate | $380 | Used when a matter has no rate of its own. |
   | Costs disclosure threshold | $750 | Uniform Law s 174: no disclosure needed when costs are not likely to exceed this. |
   | Uniform standard disclosure form limit | $3,000 | Above this, full written disclosure is required (s 174(5)). |
   | Significant change in costs | 10% | An estimate rise, or billing past the estimate, by this much needs updated disclosure. |
   | Significant cash transaction | $10,000 | Cash receipts of this or more create a task to report to AUSTRAC. |
   | Identity verification required for | Property & Conveyancing | The client's identity must be verified before engaging. |
   | Limitation date required for | Personal Injury, Litigation | The limitation date must be recorded before engaging. |
   | Limitation / court date reminders | 90, 30, 7 / 7, 1 days | When reminders arrive. |

4. **Billing**: invoice numbering, payment terms and GST.
5. **Import your clients** (Setup → Data → Import Data), so conflict searches cover your existing client
   base from day one. Import past matters' parties too if you can: the conflict search looks at them.

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, **Area of Law** (Family, Property & Conveyancing, Wills &
   Estates…), **Source** (Web, Phone Enquiry, Client Referral, Professional Referral, Search Engine,
   Walk-in…) and a description.
2. Follow up from the enquiry's **Activity** panel (**Log a Call**, **New Task**, **New Event**). Status
   moves New → Contacted → Follow-up → Qualified, or **Not Proceeding**.
3. When you're taking them on, open the enquiry and choose **Convert**. The system checks for an existing
   client with the same details, then creates the **Client** (and an **Organisation** only if they gave a
   company). The enquiry becomes read-only.
4. On the client, record **Date of Birth** and, once you've sighted ID, tick **Identity Verified** (the date
   goes in **Identity Verified On**). Conveyancing matters can't be engaged without it.

---

## 5. Opening a matter

From the client's **Related** tab (Matters → **New**) or **Matters → New**:

| Field | Notes |
|---|---|
| **Matter Title** (required) | e.g. "Smith – property settlement". |
| **Client** (required) | The person you act for. |
| **Billing Organisation** | Who pays, if not the client personally. |
| **Practice Area** | Family, Property & Conveyancing, Wills & Estates, Commercial, Litigation, Employment, Criminal, Personal Injury, Immigration, Other. |
| **Responsible Solicitor** | Defaults to you. Gets reminders and conflict alerts. |
| **Supervising Principal** | Gets access to the matter automatically. |
| **Court / Tribunal, Jurisdiction, Court File Number** | For litigation. |
| **Limitation Date** | Required before engaging on Personal Injury and Litigation matters (unless a court file number is recorded). Triggers reminders. |
| **Billing Method** | Hourly (default), Fixed Fee, Conditional, Pro Bono. |
| **Client Type** | Individual (default), or **Commercial or Government**: costs disclosure isn't required for those (s 170). |
| **Hourly Rate** | Filled with the practice default for hourly matters; change it if needed. |
| **Agreed Fixed Fee** | For fixed-fee matters: what the client is invoiced. |
| **Estimated Legal Costs** | Decides whether, and how, costs disclosure is required (section 7). |

**When you save:**
- the matter gets its number (`LM-YYYY-0000`);
- a **conflict check runs straight away**, and the matter moves to **Conflict Check**;
- the Responsible Solicitor and Supervising Principal get access.

New matters always start at Intake; you can't create one at a later stage.

---

## 6. Conflict checks

Open the matter's **Related** tab → **Conflict Checks**, or the check from the notification.

**What's searched.** The first check searches the client's name, every party's name and the billing
organisation. For each name, it looks for:
- the name as a **party on any other matter** (by name, or the same ACN/ABN);
- for every name except your own client's, the name as an existing **client, organisation or contact**,
  and the matters they're on.

Searching your own client against other matters' parties catches acting *against* a former client.

**Results:**

| Result | Meaning | What happens |
|---|---|---|
| **Clear** | No matches. | The matter is marked *Conflict Cleared*. |
| **Potential Conflict** | One or more matches, listed under **Matches Found**. | The Responsible Solicitor gets a notification: *"Possible conflict on LM-…"*. The matter can't be engaged. |
| **Conflict** | You've decided it is a conflict. | The matter can't proceed. |

**Clearing a potential conflict** (Principals only, the *Clear Conflicts* permission):
1. Review each match.
2. Write in **Clearance Notes / Waiver** why the matches aren't a conflict, or the details of the
   informed consent or waiver obtained.
3. Set **Result** to **Clear** and save. *Cleared By* is recorded, and the clearance goes in the audit log
   with your notes.

Anyone else who tries sees *"Only a principal can clear a check that found matches."* Clearing without
notes gives *"Record why the matches are not a conflict (or the waiver)."*

**Run it again.** If you've corrected names or added search terms (**Names Searched**, one per line), use
**Run Search Again** on the check.

**Adding a party later** runs a new conflict check for that party automatically. If it finds matches, the
matter is marked not cleared again until a Principal clears it.

---

## 7. Engaging: costs disclosure

To move a matter to **Engaged** (or any later stage):

1. **The conflict check is clear.** Otherwise: *"Clear the conflict check before engaging on this
   matter."*
2. **Costs disclosure has been given** where the Uniform Law requires it:

   | Situation | Disclosure |
   |---|---|
   | Pro bono, or a **Commercial or Government** client (s 170) | Not required. |
   | Estimated legal costs **$750 or less** | Not required. |
   | Estimated costs up to **$3,000** | The **Uniform Standard Disclosure Form** may be used (s 174(5)). |
   | Estimated costs **over $3,000**, or no estimate | **Full Written Disclosure** (s 174). |

   Tick **Costs Disclosure Provided** and choose **Disclosure Given As**. If you leave the method blank it
   is recorded as Full Written Disclosure. **Costs Disclosure Date** fills in with today if you leave it
   blank. Choosing the standard form above $3,000 is refused: *"The uniform standard disclosure form is
   only for costs up to $3,000; give full written disclosure (Uniform Law s 174)."*
3. **Conveyancing** (or another area set in Practice Settings): the client's identity is verified.
   Otherwise: *"Verify [client]'s identity (VOI) before acting on a Property & Conveyancing matter: tick
   Identity Verified on the client."*
4. **Personal Injury and Litigation** (or other areas set): a **Limitation Date** is recorded, or a court
   file number once proceedings are filed. Otherwise: *"Record the limitation date before engaging on a
   Litigation matter (or the court file number once proceedings are filed)."*

Then select **Engaged** on the stage path and choose **Mark as Current Stage**. Continue to **Active**
when work is under way and **Settlement/Hearing** as the matter nears its end.

**When the estimate changes (s 174(1)(b)).** If you raise the **Estimated Legal Costs** by 10% or more
after disclosure, the matter is flagged **Updated Disclosure Due** and the Responsible Solicitor is
notified. Give the client the revised estimate in writing, then change the **Costs Disclosure Date** to the
date you did: the flag clears. Until then the matter can't be billed. The list **Costs Disclosure Updates
Due** shows every flagged matter.

---

## 8. Parties

On the matter: **Related → Parties → New**.

| Field | Notes |
|---|---|
| **Role** | Other Party, Other Side's Lawyer, Related Party, Witness, Expert, Insurer, Guarantor. |
| **Contact / Organisation** | Link to an existing record if you have one. |
| **ACN / ABN** | Helps the conflict search match companies exactly. |

Every party you add gets its own conflict check (section 6). Add the other side and their lawyers
**before** engaging, so the first clearance covers them.

---

## 9. Recording time

**Time Entries → New**, or from the matter (**Related → Time Entries → New**), or the **Record time**
shortcut on Home.

| Field | Notes |
|---|---|
| **Matter** | Required. You can't record time on a closed matter. |
| **Date** | Defaults to today (the firm's local date). |
| **Units (6 min)** | 1 unit = 6 minutes (1–240). 1.5 hours = 15 units. |
| **Activity** | Attendance, Correspondence, Drafting, Research, Court Appearance, Travel, Review, Other. |
| **Narrative** | Required: what was done. It appears on the invoice. |
| **Billable** | On by default. Turn off for non-chargeable time. |
| **Hourly Rate** | The matter's rate (else the practice default) unless you enter another. |

The system works out **Hours** (units × 0.1) and **Amount** (hours × rate, ex GST). The **Timekeeper**
defaults to you. Unbilled billable time is totalled on the matter as **Unbilled Time (WIP)**.

**Useful lists:** *My Time* and *Unbilled Time (WIP)*.

**Writing off time.** A Principal can open an unbilled entry and choose **Write Off**, giving a reason.
The entry becomes *Written Off*, drops out of WIP, and the write-off is audited. Others see *"Only a
principal can write off time."*

Once an entry is **Billed** or **Written Off** it can't be changed, and it shows without an Edit button.

---

## 10. Billing

**Hourly matters: Invoice Unbilled Time** (on the matter when there's WIP). It:
- creates a **draft invoice** to the billing organisation (or the client: an individual is billed through
  one billing record in their name, created once and reused on their later matters);
- adds **one line per unbilled billable entry**, in date order: the date and narrative, hours × rate;
- marks those entries **Billed** and links them to the invoice.

**Fixed-fee matters: Invoice Fixed Fee.** Enter the **Agreed Fixed Fee** on the matter, then choose
**Invoice Fixed Fee**: one line for the fee, and any time recorded is marked billed (absorbed). It can be
used once: *"The fixed fee has already been invoiced on this matter."*

**Billing stays within the disclosed estimate.** If a bill would take the matter's invoices more than 10%
past the **Estimated Legal Costs**, it's refused: *"This bill takes the matter to $…, past the $…
estimate disclosed to the client. Disclose the revised estimate (Uniform Law s 174(1)(b)) and update it on
the matter first."* Raise the estimate, disclose it, record the new disclosure date, then bill.

Check the draft, add any disbursements, then **Issue Invoice** (the practice's ABN must be set up). Use
**PDF** on the invoice for the tax invoice. **Void Invoice** cancels an issued invoice. **Billed to Date**
on the matter totals the issued invoices (ex GST).

**Payments** are recorded on the invoice. A transfer from trust records the payment for you (section 11).
Invoice status moves Draft → Issued → Partially Paid → Paid.

---

## 11. Trust accounting

Only people with the **Manage Trust Account** permission (Principals and Trust Accountants) can record
trust money; others see *"Recording trust money needs the Manage Trust Account permission."*

**Trust Ledger → New**, or from the matter (**Related → Trust Ledger → New**):

| Type | Use for | Rules |
|---|---|---|
| **Receipt** | Money received into trust for the matter. | Positive amount. |
| **Payment** | Money paid out of trust for the matter (settlement monies, disbursements). | Can't take the matter's trust balance below zero; **EFT, BPAY or cheque only**. |
| **Transfer to Office** | Paying your own invoice from trust. | Needs an **issued, unpaid invoice on the same matter**; can't exceed the invoice's balance due; **EFT, BPAY or cheque only**. Records the payment on the invoice. |

Also enter: **Date**, **Paid By / Paid To**, **Method** (EFT, Cheque, BPAY, Cash, Card), **Reference** and
**Purpose** (required). Paying out of trust in cash or by card is refused: *"Trust money is paid out only by
EFT, BPAY or cheque, never in cash (Legal Profession Uniform General Rules)."*

The system fills in the **Client**, a receipt/payment number (`TR-000000`), the **Matter Trust Balance
After** each entry, and the matter's **Trust Balance**. It locks the matter while posting, so two people
paying out at once can't overdraw it.

**Significant cash transactions.** A **cash receipt of $10,000 or more** (the threshold in Practice
Settings) creates a high-priority task for the person who receipted it: *"Report significant cash transaction TR-… to AUSTRAC"*, due in three weeks
(the report is due within 15 business days). When it's lodged, open the receipt and enter the **AUSTRAC
Report Reference**: that is the only change allowed on a trust record. The list **Cash Receipts
(AUSTRAC)** shows them all.

**The ledger can't be edited or deleted**, by anyone. To correct a mistake, record a correcting entry
(for example a receipt reversing a wrong payment) and explain it in **Purpose**: *"Trust records can't be
changed or deleted; record a correcting transaction."*

**Trust statement.** On a matter, **⌄ More actions → Trust Statement** shows every receipt and payment
with the running balance and the balance held. Use **Print or save as PDF** to give it to the client (at
the end of the matter, or when they ask). Give your external examiner the **External Examiner** profile:
read-only access to matters, the ledger and reconciliations.

---

## 12. Monthly trust reconciliation

The trust account is reconciled every month, within 15 working days after the month ends (Uniform General
Rules). **Trust Reconciliations → New**:

| Field | Notes |
|---|---|
| **Month Ending** | The last day of the month (e.g. 31 October 2026). Any other date is refused: *"Choose the last day of the month being reconciled."* |
| **Trust Bank Statement Balance** | From the bank statement at month end. |
| **Unpresented / Uncleared Items** | Unpresented cheques (negative) and deposits not yet credited (positive). Explain them in **Notes and Explanations**. |

The system works out the **Total of Matter Ledgers** (every trust entry up to the month end) and the
**Difference** (bank balance + uncleared items − ledgers). It's named *"Trust reconciliation October
2026"*; each month can be reconciled once.

**Signing off.** When the difference is $0, a **Principal** sets **Status** to **Reconciled**. Signed Off
By and Signed Off are recorded and the reconciliation is locked. Typically the Trust Accountant prepares it
and a Principal signs it off.

| Message | Meaning |
|---|---|
| *The trust account doesn't reconcile (difference $…)…* | Find the error (a missing receipt, a wrong amount) and correct the ledger, or record the uncleared item. |
| *A principal signs off the trust reconciliation.* | Ask a Principal to set Reconciled. |
| *A signed-off reconciliation can't be changed…* | Correct the ledger and reconcile the next month. |

**Reminders.** From the 10th of each month, if last month isn't reconciled yet, Principals and Trust
Accountants get one notification (*"Trust reconciliation due: October 2026"*).

---

## 13. Court dates and limitation dates

**Court dates**: on the matter, **Related → Court Dates → New**: **Type** (Mention, Directions, Hearing,
Trial, Mediation, Conciliation, Judgment, Filing Deadline), **Date and Time**, **Court**, **Courtroom /
Registry**, **Appearing**, **Outcome**. The court date is named from its type and local date ("Hearing
2026-03-12"). The matter's **Next Court Date** updates itself. Tick **Visible to Client** to show the date
in the client portal (on by default).

**The calendar** shows court dates and open matters' limitation dates in amber alongside your events and
tasks. With **Only mine** ticked you see those where you're appearing, responsible or supervising.

**Reminders** arrive in the bell menu:

| What | When | To |
|---|---|---|
| Limitation date | 90, 30 and 7 days before (until the matter is closed) | Responsible Solicitor (else the matter's owner) |
| Court date | 7 days and 1 day before | The person **Appearing** (else the court date's owner) |

Change the lead times in Practice Settings. The **Limitation Dates (90 days)** list view and report show
what's coming up across the practice. Reminders are a safety net, not a substitute for your diary system.

---

## 14. Closing a matter

1. **Bill or write off the unbilled time.** Otherwise: *"Bill or write off the unbilled time before
   closing the matter."*
2. **Bring the trust balance to $0**: pay out or transfer the remaining funds, and give the client a
   final trust statement. Otherwise: *"Account for the $… held in trust before closing the matter."*
3. Select **Closed** on the stage path (or set Status to Closed). The **Closed** date is set and the
   matter's stage and status both become Closed. No more time can be recorded on it.

**Retention.** Matters with time or trust records can't be deleted: *"Matters with time or trust records
must be kept (7-year retention)."* A client with trust transactions from the last 7 years can't have their
personal data erased either.

---

## 15. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Client Portal**. The invitation e-mail
comes from your firm's name. Once signed in they see:
- their matters: stage and key dates. They don't see rates, WIP, billed-to-date, the supervising
  principal, conflict status, disclosure flags or the internal description;
- court dates marked **Visible to Client**;
- their invoices (and tax invoice PDFs);
- **New Client Request** to send you a question or request, and a conversation and files area on each
  matter.

---

## 16. Reports and dashboard

**Practice Dashboard** (also summarised on Home): open matters by stage, practice areas, work in progress,
billable hours this month and limitation dates.

**Reports** (Reports tab → *Legal Practice Reports*; sales, case and campaign reports aren't shown in a law
firm):

| Report | Shows |
|---|---|
| Open Matters by Stage | Pipeline of open matters. |
| Matters by Practice Area | Mix of work. |
| Work in Progress (Unbilled Time) | Unbilled billable time by matter (amount and hours). |
| Billable Hours by Timekeeper | This month's billable hours and value per person. |
| Trust Balances by Matter | Net trust held per matter. |
| Limitation Dates (next 90 days) | Upcoming limitation dates with the responsible solicitor. |
| Solicitor Workload | Open matters per responsible solicitor. |
| Aged Receivables, Revenue by Month | Unpaid invoices by age; invoiced revenue. |

**Subscribe** to a report to get it by e-mail daily, weekly or monthly (once e-mail is set up).

---

## 17. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New matters start at Intake.* | Create the matter without choosing a later stage. |
| *Clear the conflict check before engaging on this matter.* | Open the matter's conflict check; if it found matches, a Principal must clear it with notes (section 6). |
| *Give the client costs disclosure (Legal Profession Uniform Law s 174)…* | Tick **Costs Disclosure Provided** (and the method), or record an estimate of $750 or less, mark the client Commercial or Government, or mark the matter Pro Bono. |
| *The uniform standard disclosure form is only for costs up to $3,000…* | Give full written disclosure and choose **Full Written Disclosure**. |
| *Verify [client]'s identity (VOI) before acting on a … matter…* | Sight ID and tick **Identity Verified** on the client. |
| *Record the limitation date before engaging on a … matter…* | Enter the **Limitation Date** (or the court file number if proceedings are filed). |
| *Give the client updated costs disclosure first…* | Disclose the revised estimate in writing, then change the **Costs Disclosure Date**. |
| *This bill takes the matter to $…, past the $… estimate…* | Raise the estimate, disclose it, record the disclosure date, then bill. |
| *This is a fixed-fee matter: use Invoice Fixed Fee…* | Bill the agreed fee with **Invoice Fixed Fee**. |
| *The fixed fee has already been invoiced on this matter.* | Nothing more to bill; add disbursements to an invoice yourself. |
| *Add the practice's ABN in Setup → Company & Branding before issuing tax invoices.* | Enter the ABN there (it must be a valid ABN). |
| *Only a principal can clear a check that found matches.* | Ask a Principal to review and clear it. |
| *Record why the matches are not a conflict (or the waiver).* | Fill in **Clearance Notes / Waiver** before setting Clear. |
| *Time can't be recorded on a closed matter.* | Record it on an open matter, or ask a Principal whether to reopen. |
| *Billed or written-off time can't be changed.* | Adjust on the invoice (credit), or record a new entry. |
| *Record at least one 6-minute unit.* | Enter 1 or more units. |
| *Only a principal can write off time.* | Ask a Principal. |
| *There is no unbilled billable time on this matter.* | Nothing to bill: check the entries are Billable and Unbilled. |
| *Recording trust money needs the Manage Trust Account permission.* | Ask a Principal or Trust Accountant to post it. |
| *Trust money is paid out only by EFT, BPAY or cheque…* | Choose EFT, BPAY or Cheque as the method. |
| *Trust money can't be overdrawn (available on this matter: $…).* | Reduce the amount or receipt more funds first. |
| *Transfers to office need an issued, unpaid invoice on this matter.* | Issue the invoice first, and link the one for this matter. |
| *The transfer is more than the invoice's balance due.* | Transfer no more than what's owing. |
| *Trust records can't be changed or deleted; record a correcting transaction.* | Post a correcting entry and explain it in Purpose. |
| *Bill or write off the unbilled time before closing the matter.* | Invoice the WIP or have a Principal write it off. |
| *Account for the $… held in trust before closing the matter.* | Pay out or transfer the balance, then close. |
| *Matters with time or trust records must be kept (7-year retention).* | Close the matter instead of deleting it. |
| *… isn't available for this record now.* | The action doesn't apply to the record as it stands (for example billing a matter with nothing to bill). Refresh the page. |

---

## 18. Quick reference

```
Enquiry ──Convert──► Client ──New matter──► Matter (Intake)
                                               │  conflict check runs automatically
                                               ▼
                                         Conflict Check ── matches? ── Principal clears with notes
                                               │ clear + costs disclosure (where required)
                                               │ + VOI (conveyancing) + limitation date (claims)
                                               ▼
                                            Engaged ► Active ► Settlement/Hearing
                                               │
   time (6-min units) ──► WIP ──Invoice Unbilled Time / Invoice Fixed Fee──► Invoice ──Issue──► Paid
   (within the disclosed estimate; estimate up 10%+ → Updated Disclosure Due)
   trust: Receipt / Payment / Transfer to Office (EFT, BPAY, cheque; issued invoice, same matter)
   every month: Trust Reconciliation (balances to $0) → Principal signs off
                                               │ WIP billed + trust balance $0
                                               ▼
                                             Closed (kept 7 years if time or trust records exist)
```

| I want to… | Do this |
|---|---|
| Open a file | Client → Related → Matters → New |
| See possible conflicts | Matter → Related → Conflict Checks |
| Clear a conflict (Principal) | Conflict check → notes → Result: Clear |
| Engage | Tick Costs Disclosure Provided (+ method) → stage path → Engaged |
| Record a revised estimate | Change Estimated Legal Costs → disclose → change Costs Disclosure Date |
| Record time | Home → Record time, or Time Entries → New |
| Bill WIP | Matter → Invoice Unbilled Time → check draft → Issue Invoice |
| Bill a fixed fee | Matter → Invoice Fixed Fee → Issue Invoice |
| Receive money into trust | Trust Ledger → New → Receipt |
| Pay my invoice from trust | Issue invoice → Trust Ledger → New → Transfer to Office → choose the invoice |
| Give a client their trust statement | Matter → ⌄ More actions → Trust Statement → Print or save as PDF |
| Reconcile the trust account | Trust Reconciliations → New → month end and bank balance → Principal: Reconciled |
| Add a hearing | Matter → Related → Court Dates → New |
| Close the file | Bill or write off WIP → trust to $0 → stage path → Closed |
| Give a client access | Client → ⌄ More actions → Invite to Client Portal |
| Change rates and thresholds | Setup → Practice Settings |
