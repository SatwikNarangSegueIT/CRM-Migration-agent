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

The person who signs up a firm is placed at **CEO**. The default names are generic; rename them in
**Setup → Roles** to match your firm, for example:

| Law firm | Migration agency | Accounting practice | Loan broking |
|---|---|---|---|
| Managing Partner | Principal | Managing Partner | Principal Broker |
| └ Senior Associate | └ Senior RMA | └ Client Manager | └ Senior Broker |
| &nbsp;&nbsp;└ Solicitor | &nbsp;&nbsp;└ RMA | &nbsp;&nbsp;└ Accountant | &nbsp;&nbsp;└ Broker |
| &nbsp;&nbsp;&nbsp;&nbsp;└ Paralegal | &nbsp;&nbsp;&nbsp;&nbsp;└ Case Officer | &nbsp;&nbsp;&nbsp;&nbsp;└ Bookkeeper | &nbsp;&nbsp;&nbsp;&nbsp;└ Loan Processor |

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
| Enquiries (leads), Opportunities, Cases, Quotes, Invoices, E-mail sends, Reports, Dashboards, **all matters / engagements / loan applications**, time entries, trust and client-account ledgers, lodgement deadlines, commissions | Clients and Organisations (contacts and accounts), Campaigns, Products, Price books, Templates, Segments, Tax rates, Visa types, Lenders | Line items, Payments, Consent, Tasks, Events, Notes, Files, Parties, Conflict checks, Court dates, Applicants, Checklist items, Service agreements, Engagement letters, Document requests, Fact finds |

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
- **Team fields share automatically.** In a migration agency, the *Case Officer* and *Responsible RMA* on a
  matter get read/write access to it as soon as they're set, and lose it when they're changed.

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

---

## Permissions reference

### System permissions

| Permission | Allows |
|---|---|
| Manage Users | Invite, deactivate and unlock users; reset sign-in and two-step verification; assign profiles and roles. |
| Customize Application | Object Manager (fields, layouts, validation), App Manager, company and branding settings. |
| Manage Profiles & Sharing | Profiles, roles, sharing defaults and rules, groups and queues. |
| Manage Billing Settings | Invoice numbering, payment terms and tax rates. |
| Manage Industry Packs | Install another practice area into the workspace. |
| View Setup | Read-only access to Setup (useful for auditors and examiners). |
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
| Law firm | **Clear Conflicts** | Clearing a conflict check that found matches (with notes, audited). |
| Law firm | **Manage Trust Account** | Recording receipts, payments and transfers in the trust ledger. |
| Migration agency | **Lodge Applications** | Moving a matter to Lodged or beyond, the *Lodge Application* action, recording the decision. |
| Migration agency | **Override Agreement Gate** | Letting a matter proceed without a signed service agreement (reason required, audited). |
| Accounting practice | **Lodge Returns** (registered tax agent) | Moving an engagement to Lodged; signing off review in place of the reviewer. |
| Loan broking | **Submit to Lender** | Moving an application to Lodged with a lender. |
| Loan broking | **Manage Commissions** | Recording and changing entries in the commission ledger. |

---

## Default profiles by profession

Each profession installs its own profiles. Each one starts as a copy of a general profile (shown as
*based on*) and adds the profession's records. The general profiles (Sales Manager, Service Agent and so
on) remain available for firms that use the general apps.

### Law firm

| Profile | Based on | Matters | Parties, Court dates | Conflict checks | Time entries | Trust ledger | Invoices | Clients & Organisations | Extra permissions |
|---|---|---|---|---|---|---|---|---|---|
| **Principal** | Sales Manager | RCED VA | RCED VA | RCED VA | RCED VA | RC VA | RCE VA | RCED VA | Clear Conflicts, Manage Trust Account, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Solicitor** | Sales Representative | RCE | RCED | RCE | RCE | R | RCE | RCE | Portal Users |
| **Paralegal** | Service Agent | RE | RCED | RC | RCE | - | R | RCE / RE | - |
| **Trust Accountant** | Finance | R VA | - | - | R VA | RC VA | RCE VA MA | R | Manage Trust Account, Import, Export, Billing Settings, Public Reports |
| **External Examiner** | Read Only | R VA | R VA | R VA | R VA | R VA | R VA | R VA | View Setup, View Audit Log, Export |

The trust ledger is append-only for everyone: there is no edit or delete, corrections are new entries.

### Migration agency

| Profile | Based on | Matters | Applicants, Checklist | Service agreements | Visa types | Client account | Invoices | Extra permissions |
|---|---|---|---|---|---|---|---|---|
| **Practice Manager** | Sales Manager | RCED VA | RCED VA | RCED VA | RCED | R VA | R VA | Lodge Applications, Override Agreement Gate, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Registered Migration Agent** | Sales Representative | RCE VA | RCED VA | RCE VA | R | R | RCE | Lodge Applications, Portal Users |
| **Case Officer** | Service Agent | RE (their matters) | RCE / RCED | R | R | - | R | - |
| **Intake Consultant** | Sales Representative | RC | - | - | R | - | R | - (works enquiries and converts them) |
| **Accounts** | Finance | R VA | - | - | R | RCE VA | RCE VA MA | Import, Export, Billing Settings, Public Reports |
| **Practice Auditor** | Read Only | R VA | R VA | R VA | R VA | R VA | R VA | View Setup, View Audit Log, Export |

Case officers see a matter when they are its *Case Officer* or *Responsible RMA* (automatic sharing).

### Accounting practice

| Profile | Based on | Engagements | Engagement letters | Lodgement deadlines | Document requests | Time entries | Invoices | Clients | Extra permissions |
|---|---|---|---|---|---|---|---|---|---|
| **Partner** | Sales Manager | RCED VA | RCED VA | RCED VA | RCED VA | RCED VA | RCE VA | RCED VA | Lodge Returns, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Accountant** | Sales Representative | RCE | RCE | RCE | RCED | RCE | RCE | RCE | Lodge Returns, Portal Users |
| **Bookkeeper** | Service Agent | RE | - | RE | RCE | RCE | R | RE | - |
| **Practice Administrator** | Finance | RC VA | RCE VA | RCE VA | RCE VA | R VA | RCE VA MA | R | Portal Users, Import, Export, Billing Settings, Public Reports |

Reviewer sign-off is enforced separately: only the engagement's assigned reviewer (or someone with Lodge
Returns) can move it past Review, and the reviewer can't be the preparer.

### Loan broking

| Profile | Based on | Loan applications | Fact finds | Lenders | Commissions | Clients & Organisations | Extra permissions |
|---|---|---|---|---|---|---|---|
| **Principal Broker** | Sales Manager | RCED VA | RCED VA | RCED VA | RCED VA | RCED VA | Submit to Lender, Manage Commissions, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Broker** | Sales Representative | RCE | RCED | R | R | RCE | Submit to Lender, Portal Users |
| **Loan Processor** | Service Agent | RE VA | RCE VA | R | - | RE / RCE | - |
| **Commissions Administrator** | Finance | R VA | - | RCE | RCE VA | R | Manage Commissions, Import, Export, Billing Settings, Public Reports |

The commission ledger can't be edited: clawbacks and corrections are new entries.

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
| Law firm | Their matters (stage, key dates; not rates, WIP, supervising principal or internal notes) and court dates marked *Visible to client*. |
| Migration agency | Their matters (not fees, team or internal notes), their document checklist (and upload against it), and service agreements to read and **sign**. |
| Accounting practice | Their engagements, engagement letters to **sign**, and document requests to mark *uploaded*. |
| Loan broking | Their loan applications and progress. |
| All | Their invoices, and support requests (cases) with comments and files. |

Invite a client from their record (**⌄ More actions → Invite to Customer Portal**) or in **Setup → Portal
Users → Invite contact**; it needs *Manage Portal Users*. Removing access takes effect immediately.

---

## Common set-ups

**A new solicitor joins.** Setup → Users → New user. Profile *Solicitor*, role under their supervising
partner. They get an e-mail invitation, set a password and enrol two-step verification.

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
