# Accounting Practice roles and permissions

Who can see and do what in a Accounting Practice workspace of Meridian CRM, and how to set people up: partners, accountants, bookkeepers and practice administrators.
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

Reviewer sign-off is enforced separately: only the engagement's assigned reviewer (or someone with Lodge
Returns) can move it past Review, and the reviewer can't be the preparer.

**Good to know**

- The review is signed off by the engagement's **Reviewer** (or a partner). Lodging rights don't let the preparer sign off their own work.
- Only the client can sign an engagement letter, from the client portal. For a letter signed on paper, a partner uses **Record Paper Signature** (who signed and where the copy is kept; audited).
- The **Client Manager** on a client can work that client's file (for example generate BAS deadlines) without owning it.
- Tax File Numbers and ABNs are checked against the ATO check digits when saved.
- An engagement's lodgement deadline follows its due date and responsible accountant.

## 4. Profession permissions

Regulated steps are guarded by their own permission, so only the right people can do them.

| Permission | Held by default | Guards |
|---|---|---|
| Lodge Returns (registered tax agent) | Partner, Accountant | Moving returns, BAS, IAS and FBT to Lodged; signing off review in place of the reviewer. |

Grant or remove them in **Setup → Profiles → (profile)**.

## 5. Roles: whose engagements someone can see

Roles form a tree that mirrors your reporting lines. With *Grant access using hierarchies* switched on (the
default), a person sees every record owned by people below them. Roles never give access to a type of record
the profile doesn't allow. The person who signs up is placed at the top (CEO). Rename and arrange the roles in
**Setup → Roles** to match your firm, for example:

```
Managing Partner
└── Client Manager
    └── Accountant
        └── Bookkeeper
Practice Administrator (under Managing Partner)
```

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
| Clients, Contact People | Public Read Only |
| Invoices | Private |

*Private* means only the owner, people above them in the role tree, profiles with View All, and anyone it's
shared with. *Public Read Only* means everyone whose profile can read the record type sees all of them.

**Team fields share automatically.** On a engagement, the **Responsible Accountant** and **Reviewer** get read/write access as soon as
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
| Client: Tax File Number (encrypted) | Edit: Partner, Accountant, Practice Administrator. Hidden from everyone else. |
| Engagement letter: Signed From IP | Hidden from clients in the portal |

Fields the system fills in (numbers, balances, dates, signatures) are read-only for everyone.

## 8. Client portal

Clients sign in to a simplified portal with the **Customer Portal User** profile and only see records linked
to themselves. In Accounting Practice they see: Their engagements, engagement letters to sign, document requests to mark uploaded, their invoices, and requests/messages.

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

**A graduate accountant who isn't a registered agent yet.** Copy the *Accountant* profile (New Profile → Copy permissions from Accountant) and remove *Lodge Returns*. They can prepare and review but not lodge.

**Independent review.** Set a Reviewer on each engagement. The system refuses a reviewer who is the preparer, and only the reviewer (or a Lodge Returns holder) can move it to Ready to Lodge.

**A bookkeeper works on a few clients only.** Use *Bookkeeper* (no View All) and set them as Responsible Accountant on those engagements, or share the engagements with them.

**Reception onboards clients and sends letters.** Use *Practice Administrator*: engagement letters, document requests, deadlines and invoices across the practice.

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
