# Domain CRMs (plan v4, sections 5 and 6)

A firm chooses its profession at sign-up. Provisioning (`app.domains.apply_domain`) then:

1. installs the domain's industry pack (objects, fields, profiles, list views, reports, dashboard, rules,
   practice settings) and records its forms as current (`mark_forms_current`);
2. makes the pack's app the first app and the home page (`/`), and hides the generic Sales, Service,
   Marketing and Billing apps. They are not deleted; switch them back on in **Setup → App Manager**;
3. renames standard objects for the profession. The new names also apply to lookups, related lists,
   list views and standard reports;
4. applies the profession's content (`app.domain_content.apply_content`): enquiry sources and statuses,
   organisation types, the profession's enquiry question, *Client Requests* for cases and their queue, and
   role names (a role or value an administrator renamed is left alone);
5. seeds starter records where the profession needs them (migration: common visa types with document
   checklists, fees blank);
6. sets the workspace colour (unless the firm already chose one) and records the domain in the
   `workspace` setting (`{"domain", "primary_app", "forms_version"}`).

| Domain | Pack | App | Terminology | Colour |
|---|---|---|---|---|
| Law firm | `legal_practice` | Legal Practice | Contact → Client, Account → Organisation, Lead → Enquiry | `#1e3a8a` |
| Migration agency | `migration_agency` | Migration Practice | Contact → Client, Account → Organisation, Lead → Enquiry | `#0f766e` |
| Accounting practice | `accounting_practice` | Accounting Practice | Account → Client, Contact → Contact Person, Lead → Prospect | `#6d28d9` |
| Loan broking | `loan_broker` | Loan Broking | Contact → Client, Account → Organisation, Lead → Enquiry | `#b45309` |

Existing workspaces can install any pack from **Setup → Industry Packs**. Installing a pack there doesn't
change navigation or terminology; administrators adjust those in Setup.

The packs support compliance workflows. They do not replace professional advice on the rules; each
practice confirms thresholds and due dates against current guidance. The full rules, with the messages users
see, are in [domain-workflows.md](domain-workflows.md).

## How packs are built and upgraded

Each pack is `app/packs/<key>/definition.py` (objects, fields, layouts, list views, profiles, reports,
dashboard, `SETTINGS_DEFAULTS` / `SETTINGS_FIELDS`, and the upgrade lists) plus `__init__.py` (hooks with
`@on`, actions with `@action`, `locked_when` predicates, the daily job and `key_dates` for the calendar).
All four packs are at version **1.1.0**.

- **Actions** declare `visible` (re-checked on the server: *"… isn't available for this record now."*),
  an optional `guard` (permission), and `client_only` for e-signatures that only a portal user can run.
- **`locked_when(object, predicate)`** turns off edit and delete for final records (signed agreements and
  letters, billed time, ledger entries, signed-off reconciliations).
- **`key_dates`**: `(object, date field, label, user fields for "Only mine", filters)`; the calendar
  endpoint returns them as amber entries.
- **Practice settings** are served by `/setup/practice-settings` from the pack's `SETTINGS_FIELDS` and
  validated by kind (currency, number, checkbox, days, multi, select, text; `return_due.<type>` as DD-MM).
- **Client e-mails** go through `app.packs.common.tell_client`, sent after the change commits; with no portal
  user at the client, the acting user is notified instead.
- **Upgrades** (`app.pack_upgrade.upgrade_pack`, run at API start-up when `FORMS_VERSION` (8) is newer than
  the workspace's `forms_version`): add-only. The bundle is installed with `ON CONFLICT DO NOTHING`; the
  definition's `upgrade(conn)` adds grants and field security for new objects; `NEW_ON_FORMS`,
  `NEW_PICKLIST_VALUES` and `NEW_APP_TABS` are applied once each and recorded in the `pack_form_additions`
  setting. No SQL is needed.

## Legal Practice

**Objects:** Matter (`legal_matter`, LM-YYYY-0000; stages Intake → Conflict Check → Engaged → Active →
Settlement/Hearing → Closed), Party, Conflict Check, Time Entry (`legal_time_entry`, 6-minute units), Court
Date, Trust Transaction (the trust ledger), Trust Reconciliation. Extra fields on contacts (date of birth,
identity verified and date) and accounts (ACN).

**Rules**
- **Conflict search** when a matter opens and whenever a party is added; only a principal (*Clear
  Conflicts*) clears a potential conflict, with notes (audited).
- **Engaging** needs a clear conflict check; costs disclosure (Uniform Law s 174) unless pro bono, a
  commercial or government client (s 170) or an estimate at or under the threshold ($750); the standard
  disclosure form only up to $3,000 (s 174(5)); identity verification for the configured practice areas
  (conveyancing); a limitation date for personal injury and litigation unless proceedings are filed.
- **Significant change** (10%) in the estimate after disclosure sets *Updated Disclosure Due* and notifies
  the solicitor; billing waits for the new disclosure, and a bill that goes 10% past the estimate is refused.
- **Billing:** *Invoice Unbilled Time* (hourly) or *Invoice Fixed Fee* (once; time absorbed); *Billed to Date*
  follows issued invoices; principals write time off with a reason.
- **Trust ledger:** append-only (*Manage Trust Account*), never overdrawn per matter (row lock), no cash or
  card payments out, transfers to office only against an issued, unpaid invoice on the same matter; a cash
  receipt at or over the significant cash threshold ($10,000) creates an AUSTRAC task and stays editable
  for its report reference only; on-screen trust statement.
- **Monthly reconciliation:** one per month end, ledger total and difference calculated, signed off by a
  principal only at a $0 difference, then locked; reminder from the 10th.
- **Closing** needs no unbilled time and a $0 trust balance. Matters with time or trust records are kept
  (7 years), and so are their clients' personal data.
- **Reminders:** limitation dates (90/30/7 days), court dates (7/1 days), trust reconciliation.

**Profiles:** Principal, Solicitor, Paralegal, Trust Accountant, External Examiner.

## Migration Agency

**Objects:** Visa Type, Matter (MAT-YYYY-0000; stages Consultation → Service Agreement → Document Collection
→ Preparation → Ready to Lodge → Lodged → Further Information → Decision), Matter Applicant, Checklist Item,
Service Agreement, Client Account Transaction. Extra fields on contacts (passport (encrypted), visas,
Privacy Act consent) and accounts (sponsorship).

**Rules**
- **Service agreement (Code of Conduct):** Consumer Guide confirmed; the agent and their MARN recorded on
  sending (a MARN is required); client e-mailed; client-only e-signature; no stage past Service Agreement
  without a signed agreement unless a Practice Manager overrides with a reason.
- **Documents:** checklist from the visa type; the client marks items uploaded (case officer notified);
  *Send Document Reminder*.
- **Lodging** (*Lodge Applications*): ImmiAccount TRN; refused after the lodge-by date, or for an employer
  sponsored visa without the sponsor and nomination TRN.
- **Further information (s 56):** the information due date is required; reminders 7/2/0 days.
- **Decision** only once lodged; it closes the matter and calculates the processing time.
- **Client account:** append-only, never negative, transfers only against the same client's issued invoice;
  client account statement; 7-year retention (matters and personal data).
- **Reminders:** lodge-by (14/7/2), information due (7/2/0), visa, passport and sponsorship expiry (90/30).

**Profiles:** Practice Manager, Registered Migration Agent, Case Officer, Intake Consultant, Accounts,
Practice Auditor.

## Accounting Practice

**Objects:** Engagement (JOB-YYYY-0000; stages Not Started → Awaiting Information → In Progress → Review →
Ready to Lodge → Lodged → Complete), Engagement Letter, Lodgement Deadline, Document Request, Time Entry
(`engagement_time_entry`). Entity fields on accounts: entity type, TFN (encrypted, hidden by default), GST,
BAS frequency, client manager, identity verified, agent nominated.

**Rules**
- **Identifiers:** TFN and ABN check digits.
- **New engagements:** financial year (FBT: the year to 31 March) and a due date from the practice's
  `return_due` settings; a document checklist for the type; a lodgement deadline that follows the
  engagement.
- **Engagement letter (APES 305):** records the practitioner and tax agent number (theirs, else the
  practice's; required); client e-mailed; client-only e-signature, or a partner records a paper signature;
  no In Progress until signed.
- **Review:** a reviewer who isn't the preparer; only the reviewer or a partner signs off.
- **SMSF audit independence:** the auditor didn't prepare the fund's return or bookkeeping that year.
- **Lodging** (*Lodge Returns*): the client's identity verified and, for a business, the practice nominated
  as its agent.
- **BAS deadlines:** standard ATO dates (quarterly 28 Oct / 28 Feb / 28 Apr / 28 Jul; monthly the 21st,
  December 21 January; annual 31 October) or the registered agent lodgment program (quarterly 25 Nov /
  28 Feb / 26 May / 25 Aug; December monthly 21 February), set in Practice Settings.
- **Deadlines** turn Overdue automatically, with reminders 14, 3 and 0 days before.
- **Time and WIP:** time cost, unbilled WIP and recoverability; *Invoice Engagement* bills the fixed fee
  once, or each unbilled entry.

**Profiles:** Partner, Accountant, Bookkeeper, Practice Administrator.

## Loan Broker

**Objects:** Loan Application (LA-YYYY-0000; stages Enquiry → Fact Find → Preliminary Assessment → Lodged →
Conditional Approval → Valuation → Unconditional → Settlement → Settled / Declined), Lender, Fact Find,
Commission. Borrower fields on contacts (residency, first home buyer, ID check, licence number encrypted).

**Rules (NCCP and Best Interests Duty)**
- **Before credit assistance:** credit guide, privacy and credit-check consent, and a credit quote when the
  client pays a fee (s 114).
- **Preliminary assessment:** a completed, verified fact find, the BID record, and the repayment at the
  assessment rate (rate + 3% buffer, or the floor) within the monthly surplus; locks the BID record and is
  audited. A material change before lodging clears it.
- **Lodging:** a current assessment (within 90 days; 120 for a residential purchase, s 115 and the
  regulations), a lender, the credit proposal disclosure (s 121) and *Submit to Lender*.
- **Final stages:** a settled or declined application's stage can't change (a principal can correct it).
- **Settlement:** settlement date, a rate review a year later and the expected upfront commission.
- **Discharge:** within the lender's clawback period, an expected clawback (all, or half after the halving
  point).
- **Commission ledger:** *Manage Commissions*; amounts can't be edited; clawbacks are negative; brokers read
  their own loans' commission.
- **Calculations:** LVR and the LMI flag (above 80%); fact find net position and monthly surplus.
- **Retention:** applications with an assessment can't be deleted for 7 years.
- **Reminders:** settlement, approval expiry, fixed-rate expiry and rate review.

**Profiles:** Principal Broker, Broker, Loan Processor, Commissions Administrator.
