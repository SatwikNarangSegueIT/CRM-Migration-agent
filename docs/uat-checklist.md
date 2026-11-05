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
- [ ] Install an industry pack from Setup → Industry Packs; its app appears.

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

## Profession workspaces (sign up one firm per profession)
- [ ] The profession's app opens first, with its words (Clients, Matters / Engagements / Loan Applications),
      enquiry question, role names and colour; the general Sales, Service, Marketing and Billing apps are hidden.
- [ ] Setup → Settings → Practice Settings shows the profession's settings; a change is saved, validated
      (e.g. a 7-digit tax agent number is refused) and recorded in the audit log.
- [ ] Setup → Users asks for the profession's registration number (MARN, tax agent number, credit
      representative number, practising certificate number) and refuses a badly formed one.
- [ ] Issuing a tax invoice without the firm's ABN is refused with a message naming Company & Branding.
- [ ] The calendar shows the profession's key dates in amber; **Only mine** narrows them.
- [ ] A client e-mail (agreement or letter to sign, document reminder) arrives from the firm's name; with
      no portal user, the sender gets a notification instead.
- [ ] Staff never see a *Sign* action; the client signs in the portal.

## Law firm
- [ ] A matter with a matching party shows Potential Conflict; only a principal clears it, with notes.
- [ ] Engaging needs the conflict cleared and costs disclosure (not for ≤ $750, pro bono or a commercial
      client); the standard disclosure form is refused above $3,000.
- [ ] A conveyancing matter can't be engaged until the client's identity is verified; a litigation matter
      needs a limitation date.
- [ ] Raising the estimate by 10% after disclosure sets Updated Disclosure Due and blocks billing until the
      new disclosure date is recorded.
- [ ] Invoice Unbilled Time and Invoice Fixed Fee create the right invoice; time becomes Billed and locked.
- [ ] Trust: a cash payment out is refused; an overdraw is refused; a $10,000 cash receipt creates an
      AUSTRAC task and accepts its report reference; other edits are refused.
- [ ] Trust Statement prints with running balances.
- [ ] Monthly reconciliation: the difference is calculated; a non-principal can't sign off; a principal
      signs off at $0 and the record locks.
- [ ] Closing is refused with unbilled time or money in trust.

## Migration agency
- [ ] A new agency has the starter visa types; a matter from a visa type gets its checklist and fees.
- [ ] Sending an agreement needs the Consumer Guide ticked and the RMA's MARN; the agreement shows the agent
      and MARN; the client is e-mailed.
- [ ] The matter can't pass Service Agreement until the client signs (or a Practice Manager overrides
      with a reason).
- [ ] The client presses I've Uploaded This; the case officer is notified; Send Document Reminder lists
      what's outstanding.
- [ ] Lodging needs Lodge Applications and the TRN; it's refused after the lodge-by date, and for an
      employer sponsored visa without the nomination TRN.
- [ ] Further Information needs the information due date; a decision can't be recorded before lodging and
      closes the matter.
- [ ] Client account: a withdrawal larger than the balance is refused; a transfer to office pays only the
      same client's issued invoice; the Client Account Statement prints.

## Accounting practice
- [ ] A typo in a TFN or ABN is refused.
- [ ] A new FBT engagement gets the last FBT year and a 21 May due date; an individual return 31 October.
- [ ] Sending a letter needs a tax agent number (the accountant's or the practice's); the letter shows it.
- [ ] Work can't start before the letter is signed; a partner can record a paper signature.
- [ ] The preparer can't sign off their own review; the reviewer (or a partner) can.
- [ ] Lodging needs Lodge Returns, Identity Verified and (for a company) Agent Nominated.
- [ ] An SMSF audit can't go to the person who prepared the fund's return that year.
- [ ] Generate BAS Deadlines gives the standard dates, and the lodgment program dates once that's chosen in
      Practice Settings (Q1 25 November; December monthly 21 February).

## Loan broking
- [ ] Past Fact Find needs the credit guide and consent, and a credit quote when there's a broker fee.
- [ ] Record Preliminary Assessment needs a verified fact find, the BID fields, rate and term, and refuses a
      loan whose repayments at the assessment rate exceed the surplus.
- [ ] Changing the loan amount after the assessment means recording it again before lodging.
- [ ] Lodging needs the credit proposal disclosure date and Submit to Lender, and an assessment made in the
      last 90 days (120 for a home purchase); an expired one can be recorded again.
- [ ] Settling creates the expected upfront commission; Record Discharge within the clawback period creates
      the expected clawback.
- [ ] A broker reads, but can't change, the commission on their own loans.

## Non-functional
- [ ] Keyboard only: sign in, open a list, open a record, edit and save.
- [ ] Mobile width (≤ 768 px): app menu collapses, records are usable.
- [ ] Load test (operations.md) meets p95 < 400 ms for list views.
- [ ] Restore drill completed (operations.md).
