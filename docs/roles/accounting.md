# Accounting Practice roles and permissions

Who can see and do what in a Accounting Practice workspace of Meridian CRM, and how to set people up: partners, accountants, bookkeepers and practice administrators.
Administrators change everything here in **Setup**; nothing needs a developer.

**Contents**

1. How access works
2. Profiles: what someone can do
3. The Accounting Practice profiles
4. Profession permissions
5. Roles: whose engagements someone can see
6. Sharing: who can see a engagement
7. Field-level security
8. Client portal
9. System permissions and Practice Settings
10. Common set-ups
11. Security controls you don't configure

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


## 3. The Accounting Practice profiles

Each profile starts as a copy of a general profile (*based on*) and adds the profession's records.

| Profile | Based on | Engagements | Engagement letters | Lodgement deadlines | Document requests | Time entries | Invoices | Clients |
|---|---|---|---|---|---|---|---|---|
| **Partner** | Sales Manager | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCED VA MA | RCE VA MA | RCED VA MA |
| **Accountant** | Sales Representative | RCE | RCE | RCE | RCED | RCE | RCE | RCE |
| **Bookkeeper** | Service Agent | RE | - | RE | RCE | RCE | R | RE |
| **Practice Administrator** | Finance | RC VA | RCE VA | RCE VA | RCE VA | R VA | RCE VA MA | RCE VA |

**Extra permissions by profile**

| Profile | Extra permissions |
|---|---|
| **Partner** | Lodge Returns, Import, Export, Transfer Records, Portal Users, Public Reports |
| **Accountant** | Lodge Returns, Portal Users |
| **Bookkeeper** | - |
| **Practice Administrator** | Portal Users, Import, Export, Billing Settings, Public Reports |

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

## 4. Profession permissions

Regulated steps are guarded by their own permission, so only the right people can do them.

| Permission | Held by default | Guards |
|---|---|---|
| Lodge Returns (registered tax agent) | Partner, Accountant | Moving returns, BAS, IAS and FBT to Lodged, once the client's identity is verified and, for a business, the practice is its nominated agent. |

Grant or remove them in **Setup → Profiles → (profile)**.

## 5. Roles: whose engagements someone can see

Roles form a tree that mirrors your reporting lines. With *Grant access using hierarchies* switched on (the
default), a person sees every record owned by people below them. Roles never give access to a type of record
the profile doesn't allow. The workspace starts with roles named for the profession, and the person who signs
up is placed at the top (**Managing Partner**):

```
Managing Partner
├── Partner
│   └── Client Manager
│       └── Accountant
├── Bookkeeping Manager
│   └── Bookkeeper
├── Client Services Manager
│   └── Client Services Coordinator
└── Practice Manager
    └── Practice Administrator
```

Rename, add or rearrange roles in **Setup → Roles** to match your firm; a role you've renamed is never
renamed back.

**Profile vs role.** The profile is *what kind of work* someone does; the role is *where they sit*. Two people
can share a profile and sit in different roles.

## 6. Sharing: who can see a engagement

Default access for this module's records (Setup → Sharing Settings):

| Record | Default |
|---|---|
| Engagement | Private |
| Lodgement Deadline | Private |
| Time Entry | Private |
| Engagement Letter, Document Request | Controlled by parent (the engagement) |
| Clients, Contact People | Public Read Only (the Client Manager can edit their clients) |
| Invoices | Private |

*Private* means only the owner, people above them in the role tree, profiles with View All, and anyone it's
shared with. *Public Read Only* means everyone whose profile can read the record type sees all of them.

**Team fields share automatically.** On a engagement, the **Responsible Accountant** and **Reviewer** get read/write access as soon as
they're set, and lose it when they're changed. *My Engagements* and the home page list the engagements you own or
are named on.

- **Sharing rules** (Setup → Sharing Settings → Sharing rules) share records automatically, for example
  "matters owned by the Family team are shared read/write with the Family group".
- **Public groups** (Setup → Public Groups & Queues) are named sets of people, roles or other groups, used
  as the target of sharing rules.
- **Queues** hold unassigned work (for example new cases) for a group to pick up.
- **Manual sharing**: on any record, open the **⌄ More actions** menu → **Sharing** → add a person or group
  with Read or Read/Write.

**Owner.** Each record has an owner (the person who created it, unless changed). **Change Owner** (record menu) or **Change owner** (select
records in a list) moves them to someone else; it needs edit access, and *Transfer Records*
for records you don't own.


## 7. Field-level security

For each profile and field: **Hidden**, **Read only** or **Edit** (Setup → Profiles → (profile) → Field
access). A hidden field disappears from pages, lists, reports, search, exports and the API.

| Field | Default access |
|---|---|
| Client: Tax File Number (encrypted) | Edit: Partner, Accountant, Practice Administrator. Hidden from everyone else. |
| Engagement: Reviewer, Time Cost, Unbilled Time, Recoverability, Scope Notes | Hidden from clients in the portal |
| Engagement letter: Signed From IP | Hidden from clients in the portal |

Fields the system fills in (numbers, balances, dates, signatures) are read-only for everyone. Records that are
final (signed agreements and letters, billed time, ledger entries) show without Edit or Delete for every
profile.

## 8. Client portal

Clients sign in to a simplified portal with the **Customer Portal User** profile and only see records linked
to themselves. In Accounting Practice they see their engagements (not the reviewer, time cost, WIP, recoverability or scope notes), engagement letters with the practitioner and tax agent number to sign, document requests to upload against and mark uploaded, their invoices, and Client Requests with messages and files.

Signing is the client's own act: the *Sign* actions appear only in the portal, never to staff. Clients are
e-mailed, from the firm's name, when something is waiting for them; if nobody at the client can sign in yet,
the person who sent it is notified instead.

Invite a client from their record (**⌄ More actions → Invite to Client Portal**) or in **Setup → Portal Users
→ Invite contact**; it needs *Manage Portal Users*.

## 9. System permissions and Practice Settings

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

**Practice Settings** (Setup → Settings → Practice Settings) hold the profession's thresholds, rates, due dates
and reminder lead times. Anyone with *View Setup* can read them; changing them needs *Customize Application*
(System Administrators by default). Changes are recorded in the audit log.

**Professional registration.** Each user record holds the person's **Tax agent number (8 digits)** (Setup → Users),
checked when it's saved.

## 10. Common set-ups

**A new accountant joins.** Setup → Users → New user. Profile *Accountant*, role under their partner, and their tax agent number (8 digits) if they're registered. Letters they send show it; otherwise the practice's number (Practice Settings) is used.

**A graduate accountant who isn't a registered agent yet.** Copy the *Accountant* profile (New Profile → Copy permissions from Accountant) and remove *Lodge Returns*. They can prepare and review but not lodge.

**Independent review.** Set a Reviewer on each engagement. The system refuses a reviewer who is the preparer, and only the reviewer (or a Partner) can move it to Ready to Lodge.

**A bookkeeper works on a few clients only.** Use *Bookkeeper* (no View All) and set them as Responsible Accountant on those engagements, or share the engagements with them.

**Reception onboards clients and sends letters.** Use *Practice Administrator*: clients, engagement letters, document requests, deadlines and invoices across the practice.

**Someone has left.** Deactivate them (Setup → Users → Deactivate) so their records and audit trail stay,
then reassign their open engagements with **Change owner**.

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
