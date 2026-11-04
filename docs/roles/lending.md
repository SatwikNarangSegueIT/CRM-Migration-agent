# Loan Broking roles and permissions

Who can see and do what in a Loan Broking workspace of Meridian CRM, and how to set people up: principal brokers, brokers, loan processors and commissions administrators.
Administrators change everything here in **Setup**; nothing needs a developer.

**Contents**

1. x

---

## 1. How access works

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


## 2. Profiles: what someone can do

Every user has exactly one profile: object permissions (which records), system permissions (workspace-wide
abilities) and profession permissions (regulated steps).

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

**The System Administrator profile.** Has every permission, sees and edits everything, and can't be edited or deleted. The person who signs up
a firm is its first System Administrator. Keep at least two administrators so you're never locked out,
and give the profile only to people who run the workspace.

**Making your own profile.** Open **Setup → Profiles** → **New Profile**, give it a name and choose the closest existing profile under
**Copy permissions from**. Adjust the copy, then assign it in **Setup → Users**. Changes take effect on the person's next click; they don't need to
sign out.


## 3. The Loan Broking profiles

Each profile starts as a copy of a general profile (*based on*) and adds the profession's records.

| Profile | Based on | Loan applications | Fact finds | Lenders | Commissions | Clients & Organisations |
|---|---|---|---|---|---|---|
| **Principal Broker** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA |
| **Broker** | Sales Representative | RCE | RCED | R | R (their loans) | RCE |
| **Loan Processor** | Service Agent | RE VA | RCE VA | R | - | RE / RCE |
| **Commissions Administrator** | Finance | R VA | - | RCE | RCE VA MA | R |

**Extra permissions by profile**

| Profile | Extra permissions |
|---|---|
| **Principal Broker** | Submit to Lender, Manage Commissions, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Broker** | Submit to Lender, Portal Users |
| **Loan Processor** | - |
| **Commissions Administrator** | Manage Commissions, Import, Export, Billing Settings, Public Reports |

The commission ledger can't be edited: clawbacks and corrections are new entries.

**Good to know**

- Brokers read the commission on their own loans; only Manage Commissions can record or change it.
- The Loan Processor sees every application and works the ones they're assigned to as processor.
- Settled and declined applications are final for brokers and processors; a principal can correct a mistake.
- Changing the amount, purpose, borrower or lender after the preliminary assessment means recording the assessment again before lodging.
- Clients see their application and their lender's name in the portal, not commission, rates or the products comparison.

## 4. Profession permissions

Regulated steps are guarded by their own permission, so only the right people can do them.

| Permission | Held by default | Guards |
|---|---|---|
| Submit to Lender | Principal Broker, Broker | Moving an application to Lodged with a lender. |
| Manage Commissions | Principal Broker, Commissions Administrator | Recording and changing entries in the commission ledger. |

Grant or remove them in **Setup → Profiles → (profile)**.

## 5. Roles: whose loan applications someone can see

Roles form a tree that mirrors your reporting lines. With *Grant access using hierarchies* switched on (the
default), a person sees every record owned by people below them. Roles never give access to a type of record
the profile doesn't allow. The person who signs up is placed at the top (CEO). Rename and arrange the roles in
**Setup → Roles** to match your firm, for example:

```
Principal Broker
└── Senior Broker
    └── Broker
        └── Loan Processor
Commissions Administrator (under Principal Broker)
```

**Profile vs role.** The profile is *what kind of work* someone does; the role is *where they sit*. Two people
can share a profile and sit in different roles.

## 6. Sharing: who can see a loan application

Default access for this module's records (Setup → Sharing Settings):

| Record | Default |
|---|---|
| Loan Application | Private |
| Commission | Private |
| Fact Find | Controlled by parent (the application) |
| Lenders | Public Read Only |
| Clients, Organisations | Public Read Only |

*Private* means only the owner, people above them in the role tree, profiles with View All, and anyone it's
shared with. *Public Read Only* means everyone whose profile can read the record type sees all of them.

**Team fields share automatically.** On a loan application, the **Broker** and **Loan Processor** get read/write access as soon as
they're set, and lose it when they're changed.

- **Sharing rules** (Setup → Sharing Settings → Sharing rules) share records automatically, for example
  "matters owned by the Family team are shared read/write with the Family group".
- **Public groups** (Setup → Public Groups & Queues) are named sets of people, roles or other groups, used
  as the target of sharing rules.
- **Queues** hold unassigned work (for example new cases) for a group to pick up.
- **Manual sharing**: on any record, open the **⌄ More actions** menu → **Sharing** → add a person or group
  with Read or Read/Write.
- **Team fields share automatically.** In a migration agency, the *Case Officer* and *Responsible RMA* on a
  matter get read/write access to it as soon as they're set, and lose it when they're changed.

**Owner.** Each record has an owner (the person who created it, unless changed). **Change Owner** (record menu) or **Change owner** (select
records in a list) moves them to someone else; it needs edit access, and *Transfer Records*
for records you don't own.


## 7. Field-level security

For each profile and field: **Hidden**, **Read only** or **Edit** (Setup → Profiles → (profile) → Field
access). A hidden field disappears from pages, lists, reports, search, exports and the API.

| Field | Default access |
|---|---|
| Client: Driver Licence Number (encrypted) | Edit: Principal Broker, Broker, Loan Processor. Hidden from everyone else. |

Fields the system fills in (numbers, balances, dates, signatures) are read-only for everyone.

## 8. Client portal

Clients sign in to a simplified portal with the **Customer Portal User** profile and only see records linked
to themselves. In Loan Broking they see: Their loan applications and progress, their invoices, and requests/messages.

Invite a client from their record (**⌄ More actions → Invite to Customer Portal**) or in **Setup → Portal Users
→ Invite contact**; it needs *Manage Portal Users*.

## 9. System permissions reference

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

## 10. Common set-ups

**A new credit representative joins.** Setup → Users → New user. Profile *Broker*, role under the principal broker. They see their own clients and applications and can submit to lenders.

**A processor supports several brokers.** Use *Loan Processor*: they see every application (View All) and fact find, and get read/write access where they're set as Loan Processor.

**Reconciling lender statements.** Use *Commissions Administrator*: manage the commission ledger and lender panel; read every application.

**A broker shouldn't change commission.** Default: Brokers can read commissions but not record or change them (Manage Commissions).

**Someone has left.** Deactivate them (Setup → Users → Deactivate) so their records and audit trail stay,
then reassign their open loan applications with **Change owner**.

## 11. Security controls you don't configure

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
