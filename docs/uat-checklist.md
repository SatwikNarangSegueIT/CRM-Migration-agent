# User acceptance test checklist

Prepare a staging environment, then `python -m app.cli seed-demo` (staging must run with
`APP_ENV=development` for this command, or create users through Setup → Users). Demo users share the
password printed by the command:

| User | Profile |
|---|---|
| admin@demo.example.com | System Administrator |
| salesmanager@demo.example.com | Sales Manager |
| sales@demo.example.com | Sales Representative |
| service@demo.example.com | Service Agent |
| marketing@demo.example.com | Marketing User |
| finance@demo.example.com | Finance |
| auditor@demo.example.com | Read Only (Auditor) |

Tick each item and note the tester and date. Raise a defect for anything that fails.

## Security and administration (admin)
- [ ] Invite a user; the invitation e-mail arrives; the user sets a password and enrols MFA.
- [ ] Five wrong passwords lock the account; Unlock in Setup → Users works.
- [ ] Change a user's profile; they are signed out.
- [ ] Create a custom profile from Sales Representative, grant an extra object, verify the user sees it.
- [ ] Set Leads to Private; a rep can't see another rep's lead; their manager can.
- [ ] Add a sharing rule; the target role sees the records.
- [ ] Hide a field for a profile; it disappears from list, record, report and export.
- [ ] Audit log shows each of the above.

## Customisation
- [ ] Create a custom object with an auto-number, a picklist and a lookup; add it to an app.
- [ ] Rearrange the page layout; the record page follows it.
- [ ] Delete a custom field and restore it within 15 days.
- [ ] Install the Migration Agency pack; the Migration Practice app appears.

## Sales
- [ ] Create a lead, log a call, convert it (account, contact, opportunity); the call moves to the contact.
- [ ] Move an opportunity along the path; probability updates; Closed Lost asks for a reason.
- [ ] Add products to an opportunity; the amount is the product total.
- [ ] Kanban view: drag an opportunity to another stage.
- [ ] Import contacts from CSV with duplicate matching on e-mail; review the error file.

## Billing (finance)
- [ ] Quote with two lines and a discount; totals and GST are correct; download the PDF.
- [ ] Accept the quote → Create Invoice → Issue; number INV-… assigned; lines locked.
- [ ] Record a partial payment, then the rest; status Partially Paid → Paid; over-payment refused.
- [ ] Reverse a payment; void an unpaid invoice with a reason.

## Service
- [ ] A web-to-case submission lands in the Customer Support queue; accept it from My Queues.
- [ ] Close a case without a resolution (refused), then with one.
- [ ] An overdue case is escalated and the owner is notified.
- [ ] Invite a contact to the portal; they log a case, comment, upload a file and see their invoices only.

## Marketing
- [ ] Build a segment; the member count updates.
- [ ] Schedule an e-mail send; contacts without consent are skipped; the e-mail has an unsubscribe link.
- [ ] Unsubscribing updates the contact's consent immediately.

## Analytics
- [ ] Run the standard reports and dashboards; a rep only sees their own data.
- [ ] Build a summary report with a chart, save it to a folder, subscribe to it weekly.
- [ ] Export a report to CSV (needs Export Data).

## Privacy and data management
- [ ] Export Personal Data for a contact; the JSON contains the record, history, cases and consents.
- [ ] Erase Personal Data; personal fields, notes and files are gone; cases and invoices remain.
- [ ] Set a retention policy for Leads; old leads move to the recycle bin after the nightly job.
- [ ] Restore a deleted record from the recycle bin.

## Migration Agency pack
- [ ] Create a matter from a visa type; the checklist is generated.
- [ ] The matter can't pass Service Agreement until the client signs the agreement in the portal.
- [ ] Only users with Lodge Applications can lodge.
- [ ] Client account: a withdrawal larger than the balance is refused; a transfer to office pays an issued invoice.

## Non-functional
- [ ] Keyboard only: sign in, open a list, open a record, edit and save.
- [ ] Mobile width (≤ 768 px): app menu collapses, records are usable.
- [ ] Load test (operations.md) meets p95 < 400 ms for list views.
- [ ] Restore drill completed (operations.md).
