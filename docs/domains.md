# Domain CRMs (plan v4, sections 5 and 6)

A firm chooses its profession at sign-up. Provisioning (`app.domains.apply_domain`) then:

1. installs the domain's industry pack (objects, fields, profiles, list views, reports, dashboard, rules);
2. makes the pack's app the first app and the home page (`/`), and hides the generic Sales, Service,
   Marketing and Billing apps. They are not deleted; switch them back on in **Setup → Apps**;
3. renames standard objects for the profession. The new names also apply to lookups, related lists,
   list views and standard reports;
4. sets the workspace colour (unless the firm already chose one) and records the domain in the
   `workspace` setting (`{"domain", "primary_app"}`).

| Domain | Pack | App | Terminology | Colour |
|---|---|---|---|---|
| Law firm | `legal_practice` | Legal Practice | Contact → Client, Account → Organisation, Lead → Enquiry | `#1e3a8a` |
| Migration agency | `migration_agency` | Migration Practice | Contact → Client, Account → Organisation, Lead → Enquiry | `#0f766e` |
| Accounting practice | `accounting_practice` | Accounting Practice | Account → Client, Contact → Contact Person, Lead → Prospect | `#6d28d9` |
| Loan broking | `loan_broker` | Loan Broking | Contact → Client, Account → Organisation, Lead → Enquiry | `#b45309` |

Existing workspaces can install any pack from **Setup → Industry Packs**. Installing a pack there doesn't
change navigation or terminology; administrators adjust those in Setup.

The packs support compliance workflows. They do not replace professional advice on the rules; each
practice confirms thresholds and due dates against current guidance.

## Legal Practice

**Objects**
- Matter (`legal_matter`, LM-YYYY-0000), with stages Intake → Conflict Check → Engaged → Active →
  Settlement/Hearing → Closed.
- Party.
- Conflict Check.
- Time Entry (`legal_time_entry`, 6-minute units).
- Court Date.
- Trust Transaction (the trust ledger).
- Extra fields on contacts (date of birth, ID verification) and accounts (ACN).

**Rules**
- **Conflict search:** runs when a matter is opened and whenever a party is added. It searches other
  matters' parties and, for every name except the client's, clients, organisations and contacts. With no
  matches the check is *Clear*. With matches the check is *Potential Conflict*: the responsible solicitor
  is notified, and only a principal (*Clear Conflicts* permission) can clear it, with notes. Clearing is
  audited.
- **Engaging a matter:** a matter can't move to Engaged or beyond until the conflict check is clear. It
  also needs costs disclosure (Legal Profession Uniform Law s 174) unless the estimate is $750 or less or
  the matter is pro bono.
- **Time recording:** hours = units × 0.1 and amount = hours × rate (the matter's rate, else the
  practice default). Unbilled time is rolled up as WIP on the matter. **Invoice Unbilled Time** creates a
  draft invoice with one line per entry and marks the entries Billed (then locked). Only principals can
  write time off, with a reason.
- **Trust ledger:**
  - It is append-only and needs the *Manage Trust Account* permission.
  - It can never be overdrawn per matter; the matter row is locked while posting.
  - Transfers to office are allowed only against an issued, unpaid invoice on the same matter, and they
    record the payment on that invoice.
  - A matter can't close with money in trust.
  - A statement is available at `GET /packs/legal_practice/trust-statement/{matter}`.
- **Reminders:** limitation dates (90/30/7 days) and court dates (7/1 days).

**Profiles:** Principal, Solicitor, Paralegal, Trust Accountant, External Examiner.

**Reports and dashboard:** open matters by stage, practice areas, WIP, billable hours, trust balances,
limitation dates and solicitor workload.

## Accounting Practice

**Objects**
- Engagement (JOB-YYYY-0000): tax returns, BAS/IAS, FBT, SMSF audit, bookkeeping, payroll and advisory.
  Stages are Not Started → Awaiting Information → In Progress → Review → Ready to Lodge → Lodged →
  Complete.
- Engagement Letter.
- Lodgement Deadline.
- Document Request.
- Time Entry (`engagement_time_entry`).
- Entity fields on accounts: entity type, TFN (encrypted and hidden by default), GST, BAS frequency and
  client manager.

**Rules**
- **New engagements:** get the right financial year and a default due date from the `accounting_practice`
  setting (`return_due`, editable). They also get a document checklist for the engagement type and a
  lodgement deadline.
- **Engagement letter (APES 305):** work can't start (In Progress) until the client signs the engagement
  letter in the portal. Signing moves the engagement to Awaiting Information. When every document request
  is accepted, the engagement moves to In Progress.
- **Review:** before Ready to Lodge, a reviewer who is not the preparer must be assigned, and only the
  reviewer (or a tax agent with *Lodge Returns*) signs off.
- **Lodging:** needs *Lodge Returns*. It sets the lodged date and closes the matching deadlines.
- **Deadlines:**
  - **Generate BAS Deadlines** (on the client) creates the year's monthly, quarterly or annual activity
    statement deadlines: 28 Oct / 28 Feb / 28 Apr / 28 Jul for quarterly, the 21st of the following month
    for monthly.
  - Deadlines turn Overdue automatically, with reminders 14, 3 and 0 days before they're due.
- **Time and WIP:** time cost, unbilled WIP and recoverability (agreed fee ÷ time cost) are kept on the
  engagement. **Invoice Engagement** bills the fixed fee once, or each unbilled entry for time-based
  work.
- **Portal:** clients see their engagements, sign letters and mark document requests uploaded.

**Profiles:** Partner, Accountant, Bookkeeper, Practice Administrator.

**Reports and dashboard:** engagements by stage and type, workload, WIP, recoverability, upcoming and
overdue lodgements.

## Loan Broker

**Objects**
- Loan Application (LA-YYYY-0000), with stages Enquiry → Fact Find → Preliminary Assessment → Lodged →
  Conditional Approval → Valuation → Unconditional → Settlement → Settled / Declined.
- Lender.
- Fact Find.
- Commission.
- Borrower fields on contacts (residency, first home buyer, ID check, licence number encrypted).

**Rules (NCCP and Best Interests Duty)**
- **Before credit assistance:** no stage past Fact Find without the credit guide date and the privacy
  and credit-check consent.
- **Preliminary assessment:** **Record Preliminary Assessment** needs a completed fact find and the BID
  record (requirements and objectives, products considered, why the recommendation is in the client's
  best interests). It locks the BID record and is audited.
- **Lodging:** needs the assessment, a lender and the *Submit to Lender* permission.
- **Retention:** applications with an assessment can't be deleted for 7 years.
- **Calculations:**
  - LVR is calculated from the loan amount and security value.
  - Fact finds calculate the net position and the monthly surplus.
- **Settlement:** sets the settlement date and a rate review a year later. It also creates the expected
  upfront commission from the lender's upfront rate.
- **Commission ledger:** clawbacks are recorded as negative amounts, and amounts can't be edited (record
  a new entry instead).
- **Reminders:** settlement, approval expiry, fixed-rate expiry and rate review.

**Profiles:** Principal Broker, Broker, Loan Processor, Commissions Administrator.

**Reports and dashboard:** pipeline by stage, settled volume by lender, broker volume, commission by type
and by lender, upcoming settlements and fixed-rate expiries.

## Migration Agency

The existing pack is unchanged (see plan v3, section 11): matters with visa stages, visa types,
applicants, checklists, service agreements with portal e-signature, the client-account ledger and
expiry reminders.
