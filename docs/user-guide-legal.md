# Legal Practice user guide

A practical guide for law firms using Meridian CRM: principals, solicitors, paralegals and trust accountants.
It follows a matter from first enquiry to closed file. For general features (lists, search, records,
reports) see the [general user guide](user-guide.md); for who can do what, see
[Roles and permissions](roles-and-permissions.md).

> The Legal Practice workspace supports your compliance obligations (conflicts, costs disclosure, trust
> accounting). It doesn't replace professional judgement: confirm thresholds and procedures against your
> law society's current guidance.

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
12. [Court dates and limitation dates](#12-court-dates-and-limitation-dates)
13. [Closing a matter](#13-closing-a-matter)
14. [Clients in the portal](#14-clients-in-the-portal)
15. [Reports and dashboard](#15-reports-and-dashboard)
16. [Messages you may see and what to do](#16-messages-you-may-see-and-what-to-do)
17. [Quick reference](#17-quick-reference)

---

## 1. Your workspace at a glance

The **Legal Practice** app opens as your home page. Its tabs:

| Tab | What's there |
|---|---|
| **Home** | Shortcuts (Open a matter, Record time, Trust ledger), your open matters, tasks, recent records and the practice dashboard's key charts. |
| **Enquiries** | Prospective clients not yet engaged. |
| **Clients** | People you act for (with date of birth and identity verification). |
| **Organisations** | Companies and other entities (with ACN). |
| **Matters** | Every file, numbered `LM-2026-0001`, `LM-2026-0002`… |
| **Time Entries** | Time recorded in 6-minute units. |
| **Trust Ledger** | Receipts, payments and transfers to office. |
| **Invoices** | Bills to clients. |
| **Calendar**, **Reports**, **Dashboards** | Diary, the practice's reports and the Practice Dashboard. |

**A matter moves through six stages**, shown as a path across the top of the matter:

```
Intake → Conflict Check → Engaged → Active → Settlement/Hearing → Closed
```

The system won't let a matter reach **Engaged** until the conflict check is clear and costs disclosure is
recorded, and won't let it **close** while money is held in trust.

---

## 2. Who does what

| Profile | Typical person | Can |
|---|---|---|
| **Principal** | Legal practitioner director, partner | Everything on every matter; **clear conflicts**; **write off time**; **trust ledger**; import/export; reassign files. |
| **Solicitor** | Employed solicitor | Open and run their own matters; record time; add parties and court dates; raise invoices; read the trust ledger. |
| **Paralegal** | Paralegal, law clerk | Work on matters shared with them; add parties and court dates; record time. |
| **Trust Accountant** | Accounts / trust officer | **Trust ledger** (receipts, payments, transfers), invoices and payments; read every matter. |
| **External Examiner** | Annual trust examiner | Read matters and the trust ledger; change nothing. |

**Who sees a matter.** Matters are private. A matter is visible to its owner, the **Responsible Solicitor**
and the **Supervising Principal** (they get read/write access automatically), anyone above them in the
role hierarchy, and Principals, Trust Accountants and Examiners (who see all matters). Share a matter with
anyone else from **⌄ More actions → Sharing**.

---

## 3. Before you start: set-up checklist

An administrator (Setup, left rail) should:

1. **Company & Branding**: firm name, ABN, address and logo. They appear on invoices.
2. **Users**: add each person with the right **profile** (table above) and a **role** under their
   supervisor. Trust Accountants and Principals need their profiles for trust work.
3. **Billing**: invoice numbering, payment terms and GST.
4. **Import your clients** (Setup → Data → Import Data), so conflict searches cover your existing client
   base from day one. Import past matters' parties too if you can: the conflict search looks at them.
5. **Default hourly rate**: the practice default is **$380/hour**, used when a matter has no rate of its
   own. Set each matter's rate on the matter. (Changing the practice default needs an administrator with
   database access for now.)

---

## 4. From enquiry to client

1. **Enquiries → New**: name, contact details, what it's about, source.
2. Follow up from the enquiry's **Activity** panel (**Log a Call**, **New Task**, **New Event**).
3. When you're taking them on, open the enquiry and choose **Convert**. The system checks for an existing
   client with the same details, then creates the **Client** (and **Organisation** if they're a
   business). The enquiry becomes read-only.
4. On the client, record **Date of Birth** and, once you've sighted ID, tick **Identity Verified** (the date
   goes in **Identity Verified On**).

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
| **Limitation Date** | Triggers reminders 90, 30 and 7 days before. |
| **Billing Method** | Hourly (default), Fixed Fee, Conditional, Pro Bono. |
| **Hourly Rate** | Filled with the practice default for hourly matters; change it if needed. |
| **Estimated Legal Costs** | Decides whether costs disclosure is required (section 7). |

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

To move a matter to **Engaged** (or any later stage), two things must be true:

1. **The conflict check is clear.** Otherwise: *"Clear the conflict check before engaging on this
   matter."*
2. **Costs disclosure has been given** (Legal Profession Uniform Law s 174), unless:
   - the **Estimated Legal Costs** are **$750 or less**; or
   - the **Billing Method** is **Pro Bono**.

   Otherwise: *"Give the client costs disclosure (Legal Profession Uniform Law s 174) before work starts,
   or record an estimate of $750 or less."*

   Tick **Costs Disclosure Provided** on the matter. **Costs Disclosure Date** fills in with today if you
   leave it blank. If there's no estimate, disclosure is required.

Then select **Engaged** on the stage path and choose **Mark as Current Stage**. Continue to **Active**
when work is under way and **Settlement/Hearing** as the matter nears its end.

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
| **Date** | Defaults to today. |
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

Once an entry is **Billed** or **Written Off** it can't be changed.

---

## 10. Billing

**From time.** On the matter, choose **Invoice Unbilled Time** (shown when there's WIP). It:
- creates a **draft invoice** to the billing organisation (or the client; if the client has no
  organisation, one is created in their name);
- adds **one line per unbilled billable entry**, in date order: the date and narrative, hours × rate;
- marks those entries **Billed** and links them to the invoice.

Check the draft, add any disbursements or fixed-fee lines, then **Issue Invoice**. Use **PDF** on the
invoice to download it. **Void Invoice** cancels an issued invoice.

**Fixed-fee matters**: create the invoice yourself under **Invoices → New** and link the matter.

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
| **Payment** | Money paid out of trust for the matter (settlement monies, disbursements). | Can't take the matter's trust balance below zero. |
| **Transfer to Office** | Paying your own invoice from trust. | Needs an **issued, unpaid invoice on the same matter**; can't exceed the invoice's balance due. Records the payment on the invoice. |

Also enter: **Date**, **Paid By / Paid To**, **Method** (EFT, Cheque, BPAY, Cash, Card), **Reference** and
**Purpose** (required).

The system fills in the **Client**, a receipt/payment number (`TR-000000`), the **Matter Trust Balance
After** each entry, and the matter's **Trust Balance**. It locks the matter while posting, so two people
paying out at once can't overdraw it.

**The ledger can't be edited or deleted**, by anyone. To correct a mistake, record a correcting entry
(for example a receipt reversing a wrong payment) and explain it in **Purpose**: *"Trust records can't be
changed or deleted; record a correcting transaction."*

**Statements and examination.** The **Trust Ledger** list, filtered by matter, shows every entry with the
running balance. The report *Trust Balances by Matter* totals them. A formal per-matter statement is
available through the API for the trust accountant or examiner (ask your administrator); there's no
on-screen statement yet. Give your external examiner the **External Examiner** profile: read-only access
to matters and the ledger.

---

## 12. Court dates and limitation dates

**Court dates**: on the matter, **Related → Court Dates → New**: **Type** (Mention, Directions, Hearing,
Trial, Mediation, Conciliation, Judgment, Filing Deadline), **Date and Time**, **Court**, **Courtroom /
Registry**, **Appearing**, **Outcome**. The matter's **Next Court Date** updates itself. Tick **Visible to
Client** to show the date in the client portal (on by default).

**Reminders** arrive in the bell menu:

| What | When | To |
|---|---|---|
| Limitation date | 90, 30 and 7 days before | Responsible Solicitor (else the matter's owner) |
| Court date | 7 days and 1 day before | The person **Appearing** (else the court date's owner) |

The **Limitation Dates (90 days)** list view and report show what's coming up across the practice.
Reminders are a safety net, not a substitute for your diary system.

---

## 13. Closing a matter

1. Bill any remaining WIP or write it off.
2. **Bring the trust balance to $0**: pay out or transfer the remaining funds. Otherwise: *"Account for
   the $… held in trust before closing the matter."*
3. Select **Closed** on the stage path (or set Status to Closed). The **Closed** date is set and the
   matter's stage and status both become Closed. No more time can be recorded on it.

**Retention.** Matters with time or trust records can't be deleted: *"Matters with time or trust records
must be kept (7-year retention)."*

---

## 14. Clients in the portal

Invite a client from their record: **⌄ More actions → Invite to Customer Portal**. Once signed in they see:
- their matters: stage and key dates. They don't see rates, WIP, the supervising principal, conflict
  status or the internal description;
- court dates marked **Visible to Client**;
- their invoices;
- a way to send you requests and messages.

---

## 15. Reports and dashboard

**Practice Dashboard** (also summarised on Home): open matters by stage, practice areas, work in progress,
billable hours this month and limitation dates.

**Reports** (Reports tab → *Legal Practice Reports*):

| Report | Shows |
|---|---|
| Open Matters by Stage | Pipeline of open matters. |
| Matters by Practice Area | Mix of work. |
| Work in Progress (Unbilled Time) | Unbilled billable time by matter (amount and hours). |
| Billable Hours by Timekeeper | This month's billable hours and value per person. |
| Trust Balances by Matter | Net trust held per matter. |
| Limitation Dates (next 90 days) | Upcoming limitation dates with the responsible solicitor. |
| Solicitor Workload | Open matters per responsible solicitor. |

**Subscribe** to a report to get it by e-mail daily, weekly or monthly (once e-mail is set up).

---

## 16. Messages you may see and what to do

| Message | What to do |
|---|---|
| *New matters start at Intake.* | Create the matter without choosing a later stage. |
| *Clear the conflict check before engaging on this matter.* | Open the matter's conflict check; if it found matches, a Principal must clear it with notes (section 6). |
| *Give the client costs disclosure (Legal Profession Uniform Law s 174)…* | Tick **Costs Disclosure Provided**, or record an estimate of $750 or less, or mark the matter Pro Bono. |
| *Only a principal can clear a check that found matches.* | Ask a Principal to review and clear it. |
| *Record why the matches are not a conflict (or the waiver).* | Fill in **Clearance Notes / Waiver** before setting Clear. |
| *Time can't be recorded on a closed matter.* | Record it on an open matter, or ask a Principal whether to reopen. |
| *Billed or written-off time can't be changed.* | Adjust on the invoice (credit), or record a new entry. |
| *Record at least one 6-minute unit.* | Enter 1 or more units. |
| *Only a principal can write off time.* | Ask a Principal. |
| *There is no unbilled billable time on this matter.* | Nothing to bill: check the entries are Billable and Unbilled. |
| *Recording trust money needs the Manage Trust Account permission.* | Ask a Principal or Trust Accountant to post it. |
| *Trust money can't be overdrawn (available on this matter: $…).* | Reduce the amount or receipt more funds first. |
| *Transfers to office need an issued, unpaid invoice on this matter.* | Issue the invoice first, and link the one for this matter. |
| *The transfer is more than the invoice's balance due.* | Transfer no more than what's owing. |
| *Trust records can't be changed or deleted; record a correcting transaction.* | Post a correcting entry and explain it in Purpose. |
| *Account for the $… held in trust before closing the matter.* | Pay out or transfer the balance, then close. |
| *Matters with time or trust records must be kept (7-year retention).* | Close the matter instead of deleting it. |

---

## 17. Quick reference

```
Enquiry ──Convert──► Client ──New matter──► Matter (Intake)
                                               │  conflict check runs automatically
                                               ▼
                                         Conflict Check ── matches? ── Principal clears with notes
                                               │ clear + costs disclosure (or ≤ $750 / pro bono)
                                               ▼
                                            Engaged ► Active ► Settlement/Hearing
                                               │
              time entries (6-min units) ──► WIP ──Invoice Unbilled Time──► Invoice ──Issue──► Paid
              trust: Receipt / Payment / Transfer to Office (issued invoice, same matter)
                                               │ trust balance $0
                                               ▼
                                             Closed (kept 7 years if time or trust records exist)
```

| I want to… | Do this |
|---|---|
| Open a file | Client → Related → Matters → New |
| See possible conflicts | Matter → Related → Conflict Checks |
| Clear a conflict (Principal) | Conflict check → notes → Result: Clear |
| Engage | Tick Costs Disclosure Provided → stage path → Engaged |
| Record time | Home → Record time, or Time Entries → New |
| Bill WIP | Matter → Invoice Unbilled Time → check draft → Issue Invoice |
| Receive money into trust | Trust Ledger → New → Receipt |
| Pay my invoice from trust | Issue invoice → Trust Ledger → New → Transfer to Office → choose the invoice |
| Add a hearing | Matter → Related → Court Dates → New |
| Close the file | Trust to $0 → stage path → Closed |
| Give a client access | Client → ⌄ More actions → Invite to Customer Portal |
