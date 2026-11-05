# Roles and permissions

This document explains who can see and do what in Meridian CRM, how to set people up, and the defaults
each profession's workspace starts with. Administrators change all of it in **Setup**; nothing here needs
a developer.

- [How access works](#how-access-works)
- [Profiles](#profiles-what-someone-can-do)
- [Roles](#roles-whose-records-someone-can-see)
- [Sharing](#sharing-who-can-see-a-record)
- [Field-level security](#field-level-security)
- [Permissions reference](#permissions-reference)
- [Default profiles by profession](#default-profiles-by-profession)
- [Client portal](#client-portal)
- [Common set-ups](#common-set-ups)
- [Security controls you don't configure](#security-controls-you-dont-configure)

---

## How access works

Every request is checked on the server against four layers. A person needs all four to allow something.

| Layer | Question it answers | Where you change it |
|---|---|---|
| **Profile** | What *kind* of records can this person read, create, edit or delete? Which special actions can they take? | Setup → Profiles |
| **Role** | Whose records can this person see, through the reporting line? | Setup → Roles |
| **Sharing** | Which individual records are visible to whom, beyond ownership? | Setup → Sharing Settings, and the **Sharing** button on a record |
| **Field-level security** | Which fields on a record can this person see or edit? | Setup → Profiles → (profile) → Field access |

Rules of thumb:

- A **profile** opens the door to a *type* of record ("can work matters"). **Sharing** decides *which*
  matters. You need both: a Solicitor profile with no shared matters sees an empty list.
- The person who owns a record can always see it (if their profile can read that type of record).
- Hiding something in the screens is never what protects it: the server enforces every rule, so the same
  limits apply to exports, reports, search and the API.

---

## Profiles: what someone can do

Every user has exactly one profile. A profile has three parts.

### 1. Object permissions

For each type of record (Client, Matter, Invoice…):

| Letter | Permission | Meaning |
|---|---|---|
| **R** | Read | See records they have access to through ownership, role or sharing. |
| **C** | Create | Add new records. |
| **E** | Edit | Change records they can see. |
| **D** | Delete | Move records to the Recycle Bin. |
| **VA** | View All | See *every* record of this type, ignoring sharing. |
| **MA** | Modify All | Edit and delete *every* record of this type, ignoring sharing. |

Codes in this document combine the letters: `RCE VA` = read, create and edit, and see every record.
A dash (`-`) means no access: the tab and the related list disappear.

### 2. System permissions

Workspace-wide abilities that aren't tied to one record type (for example *Export Data* or *Manage Users*).
See [Permissions reference](#permissions-reference).

### 3. Profession permissions

Regulated steps in each profession are guarded by their own permission, so only the right people can do
them (for example *Lodge Applications* for registered migration agents, *Manage Trust Account* for law
firms). Listed under each profession below.

### The System Administrator profile

Has every permission, sees and edits everything, and can't be edited or deleted. The person who signs up
a firm is its first System Administrator. Keep at least two administrators so you're never locked out,
and give the profile only to people who run the workspace.

### Making your own profile

Open **Setup → Profiles** → **New Profile**, give it a name and choose the closest existing profile under
**Copy permissions from**. Adjust the copy, then assign it in **Setup → Users**. Changes take effect on the person's next click; they don't need to
sign out.

---

## Roles: whose records someone can see

Roles form a tree that mirrors your reporting lines. With *Grant access using hierarchies* switched on (the
default for every record type), **a person can see every record owned by people below them in the tree**.
Roles never give access to a type of record the profile doesn't allow.

The starting tree:

```
CEO
├── Sales Director
│   └── Sales Manager
│       └── Sales Representative
├── Service Manager
│   └── Service Agent
├── Marketing Manager
│   └── Marketing User
└── Finance Manager
    └── Finance Officer
```

The person who signs up a firm is placed at the top of the tree. A profession's workspace names the roles
for the profession when it's set up (a role an administrator has already renamed is left alone):

| Starting role | Law firm | Migration agency | Accounting practice | Loan broking |
|---|---|---|---|---|
| CEO | Managing Principal | Principal | Managing Partner | Principal Broker |
| └ Sales Director | Principal | Practice Manager | Partner | Broking Manager |
| &nbsp;&nbsp;└ Sales Manager | Senior Associate | Senior Migration Agent | Client Manager | Senior Broker |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Sales Representative | Solicitor | Registered Migration Agent | Accountant | Broker |
| └ Service Manager | Practice Manager | Case Manager | Bookkeeping Manager | Processing Manager |
| &nbsp;&nbsp;└ Service Agent | Paralegal | Case Officer | Bookkeeper | Loan Processor |
| └ Marketing Manager | Business Development Manager | Client Services Manager | Client Services Manager | Marketing Manager |
| &nbsp;&nbsp;└ Marketing User | Business Development Coordinator | Intake Consultant | Client Services Coordinator | Marketing Coordinator |
| └ Finance Manager | Finance Manager | Accounts Manager | Practice Manager | Finance Manager |
| &nbsp;&nbsp;└ Finance Officer | Trust Accountant | Accounts Officer | Practice Administrator | Commissions Administrator |

Rename, add or rearrange roles in **Setup → Roles** to match your firm.

**Profile vs role.** The profile is *what kind of work* (a Solicitor can create time entries). The role is
*where they sit* (a Senior Associate sees the matters of the solicitors who report to them). Two people
can share a profile and sit in different roles.

---

## Sharing: who can see a record

### Organisation-wide defaults

Each type of record has a baseline, set in **Setup → Sharing Settings**:

| Default | Meaning |
|---|---|
| **Private** | Only the owner, people above them in the role tree, and anyone it's shared with. |
| **Public Read Only** | Everyone whose profile can read the type sees every record; only the owner and those above can edit. |
| **Public Read/Write** | Everyone whose profile allows it can see and edit every record. |
| **Controlled by Parent** | Follows the record it belongs to (a Party follows its Matter; a Note follows the record it's on). |

Defaults in every workspace:

| Private | Public Read Only | Controlled by parent |
|---|---|---|
| Enquiries (leads), Opportunities, Client Requests (cases), Quotes, Invoices, E-mail sends, Reports, Dashboards, **all matters / engagements / loan applications**, time entries, trust and client-account ledgers, lodgement deadlines, commissions | Clients and Organisations (contacts and accounts), Campaigns, Products, Price books, Templates, Segments, Tax rates, Visa types, Lenders, Trust reconciliations | Line items, Payments, Consent, Tasks, Events, Notes, Files, Parties, Conflict checks, Court dates, Applicants, Checklist items, Service agreements, Engagement letters, Document requests, Fact finds |

Client confidentiality is the reason the main work records are private: a solicitor doesn't see another
solicitor's matter unless they're above them, it's shared, or their profile has View All.

### Opening up access

- **Sharing rules** (Setup → Sharing Settings → Sharing rules) share records automatically, for example
  "matters owned by the Family team are shared read/write with the Family group".
- **Public groups** (Setup → Public Groups & Queues) are named sets of people, roles or other groups, used
  as the target of sharing rules.
- **Queues** hold unassigned work (for example new cases) for a group to pick up.
- **Manual sharing**: on any record, open the **⌄ More actions** menu → **Sharing** → add a person or group
  with Read or Read/Write.
- **Team fields share automatically.** The people named on a work record get read/write access to it as
  soon as they're set, and lose it when they're changed: the *Responsible Solicitor* and *Supervising
  Principal* on a matter (law firm), the *Responsible RMA* and *Case Officer* (migration agency), the
  *Responsible Accountant* and *Reviewer* on an engagement, and the *Client Manager* on a client
  (accounting practice), the *Broker* and *Loan Processor* on an application (loan broking). A broker also
  gets read access to the commission on their own loans. **My …** list views include the records you're
  named on.

### Owner

Each record has an owner (the person who created it, unless changed). **Change Owner** (record menu) or **Change owner** (select
records in a list) moves them to someone else; it needs edit access, and *Transfer Records*
for records you don't own.

---

## Field-level security

For each profile and field: **Hidden**, **Read only** or **Edit**. A hidden field disappears from pages,
lists, reports, search, exports and the API for that profile.

Sensitive identifiers are encrypted in the database and hidden unless a profile is given access:

| Profession | Field | Who can see it by default |
|---|---|---|
| Migration agency | Passport number (client) | Practice Manager, Registered Migration Agent, Accounts (edit); Practice Auditor (read) |
| Accounting practice | Tax File Number (client) | Partner, Accountant, Practice Administrator |
| Loan broking | Driver's licence number (client) | Principal Broker, Broker, Loan Processor |

Fields filled in by the system (matter numbers, balances, lodgement dates, signatures) are read-only for
everyone.

**Locked records.** Some records can't change once they're final, whatever the profile: signed service
agreements and engagement letters, billed or written-off time, trust and client-account entries (a cash
receipt stays open only for its AUSTRAC report reference) and signed-off trust reconciliations. They show
without Edit or Delete; corrections are new records.

---

## Permissions reference

### System permissions

| Permission | Allows |
|---|---|
| Manage Users | Invite, deactivate and unlock users; reset sign-in and two-step verification; assign profiles and roles. |
| Customize Application | Object Manager (fields, layouts, validation), App Manager, company and branding settings, and changing Practice Settings. |
| Manage Profiles & Sharing | Profiles, roles, sharing defaults and rules, groups and queues. |
| Manage Billing Settings | Invoice numbering, payment terms and tax rates. |
| Manage Industry Packs | Install another practice area into the workspace. |
| View Setup | Read-only access to Setup, including Practice Settings (useful for auditors and examiners). |
| View Audit Log | The log of sign-ins, changes, exports and permission changes. |
| Import Data | CSV import into any record type the profile can create. |
| Export Data | CSV export from lists and reports. |
| Send Mass Email | Send marketing e-mails to segments (consent is always enforced). |
| Manage Public Reports & Dashboards | Create and change reports and dashboards in shared folders. |
| Transfer Records | Change the owner of records they don't own. |
| Manage Portal Users | Invite clients to the client portal and remove their access. |
| API Access | Use the REST API with their own credentials. |

### Profession permissions

| Profession | Permission | Guards |
|---|---|---|
| Law firm | **Clear Conflicts** | Clearing a conflict check that found matches (with notes, audited); writing off time; signing off the monthly trust reconciliation. |
| Law firm | **Manage Trust Account** | Recording receipts, payments and transfers in the trust ledger; preparing the monthly trust reconciliation. |
| Migration agency | **Lodge Applications** | Moving a matter to Lodged or beyond, the *Lodge Application* action, recording the decision. |
| Migration agency | **Override Agreement Gate** | Letting a matter proceed without a signed service agreement (reason required, audited). |
| Accounting practice | **Lodge Returns** (registered tax agent) | Moving a return, BAS, IAS or FBT engagement to Lodged (once the client's identity is verified and, for a business, the practice is its nominated agent). |
| Loan broking | **Submit to Lender** | Moving an application to Lodged with a lender. |
| Loan broking | **Manage Commissions** | Recording and changing entries in the commission ledger, including the expected commissions and clawbacks the system creates. |

---

## Default profiles by profession

Each profession installs its own profiles. Each one starts as a copy of a general profile (shown as
*based on*) and adds the profession's records. The general profiles (Sales Manager, Service Agent and so
on) remain available for firms that use the general apps.

### Law firm

| Profile | Based on | Matters | Parties, Court dates | Conflict checks | Time entries | Trust ledger | Trust reconciliations | Invoices | Clients & Organisations | Extra permissions |
|---|---|---|---|---|---|---|---|---|---|---|
| **Principal** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RC VA | RCE VA MA | RCE VA MA | RCED VA MA | Clear Conflicts, Manage Trust Account, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Solicitor** | Sales Representative | RCE | RCED | RCE | RCE | R | - | RCE | RCE | Portal Users |
| **Paralegal** | Service Agent | RE | RCED | RC | RCE | - | - | R | RCE / RE | - |
| **Trust Accountant** | Finance | R VA | - | - | R VA | RC VA | RCE VA | RCE VA MA | R | Manage Trust Account, Import, Export, Billing Settings, Public Reports |
| **External Examiner** | Read Only | R VA | R VA | R VA | R VA | R VA | R VA | R VA | R VA | View Setup, View Audit Log, Export |

The trust ledger is append-only for everyone: there is no edit or delete, corrections are new entries.

**Good to know**

- A principal can update any solicitor's matters, time and invoices (Modify All), for example to take over a file.
- "My Matters" and the home page list the matters you're the responsible solicitor or supervising principal on, not only the ones you created.
- The monthly trust reconciliation is prepared by a Trust Accountant (or Principal) and signed off by a Principal; a signed-off month can't be changed.
- Records that can no longer change (billed or written-off time, trust ledger entries, signed-off reconciliations) show without Edit or Delete.
- Billing an individual client creates one billing organisation in their name, linked to them and reused on their later matters.

### Migration agency

| Profile | Based on | Matters | Applicants, Checklist | Service agreements | Visa types | Client account | Invoices | Extra permissions |
|---|---|---|---|---|---|---|---|---|
| **Practice Manager** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | R VA | R VA | Lodge Applications, Override Agreement Gate, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Registered Migration Agent** | Sales Representative | RCE VA | RCED VA | RCE VA | R | R VA | RCE (with lines) | Lodge Applications, Portal Users |
| **Case Officer** | Service Agent | RE (their matters) | RCE / RCED | R | R | - | R | - |
| **Intake Consultant** | Sales Representative | RC | - | - | R | - | R | - (works enquiries and converts them) |
| **Accounts** | Finance | R VA | - | - | R | RCE VA | RCE VA MA | Import, Export, Billing Settings, Public Reports |
| **Practice Auditor** | Read Only | R VA | R VA | R VA | R VA | R VA | R VA | View Setup, View Audit Log, Export |

Case officers see a matter when they are its *Case Officer* or *Responsible RMA* (automatic sharing). The
client account ledger is append-only for everyone.

**Good to know**

- Registered Migration Agents and Practice Managers can edit every client's details (passport, visa, sponsorship), whoever created the client.
- A service agreement can only be sent once the agent responsible for it has their MARN on their user record; the agreement records the agent and MARN.
- Only the client can sign a service agreement, from the client portal; staff don't see a Sign action. If the agreement exists only on paper, the Practice Manager uses **Override Agreement Gate** with a reason.
- A decision (outcome) can only be recorded once the application has been lodged; recording it closes the matter.
- Client money can only pay that client's own invoice. An individual is invoiced without an organisation: the system keeps one billing record in their name.
- "My Matters" lists the matters you're the responsible RMA or case officer on.
- New agencies start with common visa subclasses and document checklists; set your fees on each visa type.

### Accounting practice

| Profile | Based on | Engagements | Engagement letters | Lodgement deadlines | Document requests | Time entries | Invoices | Clients | Extra permissions |
|---|---|---|---|---|---|---|---|---|---|
| **Partner** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCE VA MA | RCED VA MA | Lodge Returns, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Accountant** | Sales Representative | RCE | RCE | RCE | RCED | RCE | RCE | RCE | Lodge Returns, Portal Users |
| **Bookkeeper** | Service Agent | RE | - | RE | RCE | RCE | R | RE | - |
| **Practice Administrator** | Finance | RC VA | RCE VA | RCE VA | RCE VA | R VA | RCE VA MA | RCE VA | Portal Users, Import, Export, Billing Settings, Public Reports |

Reviewer sign-off is enforced separately: only the engagement's assigned reviewer (or a partner) can move it
past Review, and the reviewer can't be the preparer.

**Good to know**

- Lodging rights don't let the preparer sign off their own work; the reviewer (or a partner) does.
- Lodging for a client needs its identity verified and, for a business, the practice nominated as its agent in ATO Online services (ticked on the client).
- An engagement letter can only be sent once the practitioner (or the practice) has a tax agent number; the letter records both.
- Only the client can sign an engagement letter, from the client portal. For a letter signed on paper, a partner uses **Record Paper Signature** (who signed and where the copy is kept; audited).
- The **Client Manager** on a client can work that client's file (for example generate BAS deadlines) without owning it.
- An SMSF audit can't be given to someone who prepared the fund's return or bookkeeping for the same year.
- Tax File Numbers and ABNs are checked against the ATO check digits when saved.
- An engagement's lodgement deadline follows its due date and responsible accountant.

### Loan broking

| Profile | Based on | Loan applications | Fact finds | Lenders | Commissions | Clients & Organisations | Extra permissions |
|---|---|---|---|---|---|---|---|
| **Principal Broker** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | Submit to Lender, Manage Commissions, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Broker** | Sales Representative | RCE | RCED | R | R (their loans) | RCE | Submit to Lender, Portal Users |
| **Loan Processor** | Service Agent | RE VA | RCE VA | R | - | RE / RCE | - |
| **Commissions Administrator** | Finance | R VA | - | RCE | RCE VA MA | R | Manage Commissions, Import, Export, Billing Settings, Public Reports |

Commission amounts can't be edited: clawbacks and corrections are new entries.

**Good to know**

- Brokers read the commission on their own loans; only Manage Commissions can record or change it.
- The Loan Processor sees every application and works the ones they're assigned to as processor.
- Settled and declined applications are final for brokers and processors; a principal can correct a mistake.
- Changing the amount, purpose, borrower or lender after the preliminary assessment means recording the assessment again before lodging.
- Recording a discharge on a settled loan creates the expected clawback for the Commissions Administrator to reconcile.
- Clients see their application and their lender's name in the portal, not commission, rates or the products comparison.

### General profiles (every workspace)

Used by firms that switch on the general Sales, Service, Marketing or Billing apps.

| Record | System Admin | Sales Manager | Sales Rep | Service Agent | Marketing User | Finance | Read Only | Portal User |
|---|---|---|---|---|---|---|---|---|
| Organisations (accounts) | RCED VA MA | RCED | RCE | RE | R | R | R VA | R |
| Clients (contacts) | RCED VA MA | RCED | RCE | RCE | RCE | R | R VA | RE |
| Enquiries (leads) | RCED VA MA | RCED | RCE | - | RCED | - | R VA | - |
| Opportunities | RCED VA MA | RCED | RCE | R | R | R VA | R VA | - |
| Products, Price books | RCED VA MA | R | R | R | R | RCED | R VA | - |
| Quotes | RCED VA MA | RCED | RCE | - | - | R VA | R VA | - |
| Invoices, Payments | RCED VA MA | R | R | R | - | RCE VA MA | R VA | R |
| Tax rates | RCED VA MA | R | R | - | - | RCED | R VA | - |
| Cases | RCED VA MA | R | R | RCE | - | R | R VA | RC |
| Campaigns, Segments, Templates | RCED VA MA | R | R | - | RCED | - | R VA | - |
| E-mail sends, Consent | RCED VA MA | R | - | - | RCE | - | R VA | - |
| Tasks, Events, Notes, Files | RCED VA MA | RCED | RCED | RCED | RCED | RCED | R VA | Notes, Files: RC |
| Reports, Dashboards | RCED VA MA | RCED | RC | RC | RCED | RCED | R VA | - |

| System permission | Sales Manager | Sales Rep | Service Agent | Marketing User | Finance | Read Only |
|---|---|---|---|---|---|---|
| Import / Export Data | ✓ / ✓ | | | ✓ / ✓ | ✓ / ✓ | – / ✓ |
| Manage Public Reports | ✓ | | | ✓ | ✓ | |
| Transfer Records | ✓ | | | | | |
| Send Mass Email | | | | ✓ | | |
| Manage Billing Settings | | | | | ✓ | |
| Manage Portal Users | | | ✓ | | | |
| View Setup, View Audit Log | | | | | | ✓ |

---

## Client portal

Clients sign in to a separate, simplified portal with the **Customer Portal User** profile. They only ever
see records linked to themselves, and internal fields are hidden.

| Profession | What clients see and do |
|---|---|
| Law firm | Their matters (stage, key dates, the estimate and trust balance; not the rate, WIP, billed to date, conflict status, supervising principal or internal notes) and court dates marked *Visible to client*. |
| Migration agency | Their matters (not fees, the team, the override, processing time or internal notes), their document checklist (to upload and press *I've Uploaded This*), and service agreements with the agent's name and MARN to read and **sign**. |
| Accounting practice | Their engagements (not the reviewer, time cost, WIP or recoverability), engagement letters with the practitioner and tax agent number to **sign**, and document requests to mark *uploaded*. |
| Loan broking | Their loan applications and progress, with the lender's name (not commission, rates, the products comparison or the lender reference). |
| All | Their invoices, and Client Requests with comments and files. |

Signing is the client's own act: the *Sign* actions appear only in the portal, never to staff. Clients are
e-mailed, from the firm's name, when something is waiting for them; if nobody at the client can sign in yet,
the person who sent it is notified instead.

Invite a client from their record (**⌄ More actions → Invite to Client Portal**) or in **Setup → Portal
Users → Invite contact**; it needs *Manage Portal Users*. Removing access takes effect immediately.

---

## Common set-ups

**A new solicitor joins.** Setup → Users → New user. Profile *Solicitor*, role under their supervising
principal, and their practising certificate number. They get an e-mail invitation from the firm, set a
password and enrol two-step verification.

**Professional registration numbers.** Each user record holds the person's registration, named and checked
for the profession: *Practising certificate number* (law firm), *MARN* (7 digits, migration agency), *Tax
agent number* (8 digits, accounting practice), *Credit representative number* (6 or 7 digits, loan broking).
Service agreements and engagement letters record the practitioner's number and can't be sent without one.

**Someone covers for a colleague on leave.** Share the colleague's open matters with them (on each matter,
**⌄ More actions → Sharing**), or add both to a group and create a sharing rule. Remove it when they return. Avoid
changing the owner unless the work is moving permanently.

**A paralegal should only see the Family team's matters.** Create a public group *Family team*, add a
sharing rule "Matters where Practice Area = Family → share read/write with Family team", and keep the
Paralegal profile without View All.

**An external examiner or auditor needs access for a week.** Create a user with *External Examiner* /
*Practice Auditor* / *Read Only*. They can read and export, see Setup and the audit log, and change
nothing. Deactivate the user afterwards (Setup → Users → Deactivate); their history stays in the audit log.

**A receptionist books appointments but shouldn't see files.** Create a profile copied from *Intake
Consultant* (or *Service Agent*), remove Files and Notes, and set matters to `-`.

**Someone has left.** Deactivate them (don't delete) so their records and audit trail stay intact, then
reassign their open work with **Change owner**.

---

## Security controls you don't configure

- **Two-step verification** (authenticator app) is required for all staff in production.
- **Passwords**: at least 12 characters; common, breached and personal passwords (containing your name or
  e-mail) are refused.
- **Sign-in protection**: accounts lock for 15 minutes after 5 failed attempts; sessions end after 60
  minutes idle or 12 hours.
- **Audit log**: sign-ins, record changes on tracked fields, exports, permission changes, conflict
  clearances, gate overrides and signatures are recorded with who, when and from where. It can't be edited.
- **Privacy**: on a client's record, **⌄ More actions → Export Personal Data** (subject access request)
  or **Erase Personal Data**. Retention periods are in Setup → Data Retention; records that
  must be kept (trust, client-account and BID records: 7 years) can't be deleted early.
- **Data location**: all client data is stored in Australia.
