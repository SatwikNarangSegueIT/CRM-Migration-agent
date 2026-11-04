"""Sample business data for demos and UAT (development/test only), and bulk rows for load tests.

Sample data goes through the record engine as named demo users, so every validation rule and object hook
runs (prices, totals, SLAs, stage probabilities...). Load data is inserted directly for speed.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.engine.records import RecordService
from app.models import Record, User
from app.security.policy import load_policy

ACCOUNTS = [
    ("Harbour Logistics Pty Ltd", "Transport", "Customer", "+61290000001", "Sydney", "NSW"),
    ("Southern Cross Health", "Healthcare", "Customer", "+61390000002", "Melbourne", "VIC"),
    ("Kookaburra Software", "Technology", "Prospect", "+61730000003", "Brisbane", "QLD"),
    ("Banksia Building Group", "Construction", "Customer", "+61880000004", "Adelaide", "SA"),
    ("Swan River Retail", "Retail", "Partner", "+61890000005", "Perth", "WA"),
    ("Tasman Education Trust", "Education", "Prospect", "+61360000006", "Hobart", "TAS"),
]
PEOPLE = [
    ("Olivia", "Nguyen", "CEO"), ("Jack", "Smith", "Operations Manager"), ("Charlotte", "Williams", "CFO"),
    ("Noah", "Brown", "IT Director"), ("Amelia", "Jones", "Procurement Lead"), ("Liam", "Taylor", "Head of Sales"),
    ("Isla", "Wilson", "Practice Manager"), ("William", "Chen", "Facilities Manager"), ("Mia", "Patel", "COO"),
    ("Henry", "Singh", "Finance Manager"),
]  # fmt: skip
PRODUCTS = [
    ("CONSULT-HR", "Consulting (hourly)", "Services", 220),
    ("IMPL-STD", "Standard implementation", "Services", 9500),
    ("SUB-PRO", "Pro subscription (annual)", "Subscription", 4800),
    ("TRAIN-DAY", "Training day", "Services", 1800),
]
STAGES = [
    "Prospecting",
    "Qualification",
    "Needs Analysis",
    "Proposal",
    "Negotiation",
    "Closed Won",
    "Proposal",
    "Qualification",
]


def _svc(db: Session, email: str) -> RecordService:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise RuntimeError(f"Demo user {email} is missing; seed the demo users first.")
    return RecordService.for_user(db, user, load_policy(db, user))


def seed_sample_data(db: Session) -> int:
    """Create sample records once. Returns the number of records created (0 when data already exists)."""
    if db.scalar(select(func.count()).select_from(Record).where(Record.object_api_name == "account")):
        return 0
    rnd = random.Random(42)  # noqa: S311 - deterministic demo data, not security relevant
    admin = _svc(db, "admin@demo.example.com")
    sales = _svc(db, "sales@demo.example.com")
    manager = _svc(db, "salesmanager@demo.example.com")
    service = _svc(db, "service@demo.example.com")
    marketing = _svc(db, "marketing@demo.example.com")
    finance = _svc(db, "finance@demo.example.com")
    count = 0
    today = date.today()

    products = []
    for code, name, family, price in PRODUCTS:
        products.append(
            finance.create(
                "product", {"name": name, "product_code": code, "family": family, "standard_price": price}
            )
        )
        count += 1

    accounts, contacts = [], []
    for i, (name, industry, kind, phone, city, state) in enumerate(ACCOUNTS):
        owner = sales if i % 2 == 0 else manager
        acct = owner.create(
            "account",
            {
                "name": name,
                "industry": industry,
                "type": kind,
                "phone": phone,
                "website": f"{name.split()[0].lower()}.example.com",
                "abn": f"5{i}1 824 753 55{i}",
                "annual_revenue": rnd.randint(2, 90) * 100_000,
                "employees": rnd.randint(20, 900),
                "billing_address": {
                    "street": f"{10 + i} Example St",
                    "city": city,
                    "state": state,
                    "postcode": f"{2000 + i * 900}",
                    "country": "Australia",
                },
            },
        )
        accounts.append(acct)
        count += 1
        for first, last, title in PEOPLE[i * 2 % len(PEOPLE) : i * 2 % len(PEOPLE) + 2]:
            contacts.append(
                owner.create(
                    "contact",
                    {
                        "first_name": first,
                        "last_name": last,
                        "title": title,
                        "account": str(acct.id),
                        "email": f"{first.lower()}.{last.lower()}@{name.split()[0].lower()}.example.com",
                        "phone": f"+614{rnd.randint(10000000, 99999999)}",
                        "email_opt_in": i % 3 != 0,
                        "lead_source": "Partner Referral",
                    },
                )
            )
            count += 1

    for i, stage in enumerate(STAGES):
        acct = accounts[i % len(accounts)]
        owner = sales if i % 3 else manager
        opp = owner.create(
            "opportunity",
            {
                "name": f"{acct.name.split()[0]} - {['Expansion', 'New platform', 'Renewal', 'Training'][i % 4]}",
                "account": str(acct.id),
                "stage": stage,
                "close_date": (today + timedelta(days=15 * (i - 2))).isoformat(),
                "type": "New Business" if i % 2 else "Existing Business",
                "lead_source": "Web",
            },
        )
        count += 1
        for p in products[: 1 + i % 3]:
            owner.create(
                "opportunity_product",
                {"opportunity": str(opp.id), "product": str(p.id), "quantity": 1 + i % 4},
            )
            count += 1

    for i in range(8):
        first, last, _ = PEOPLE[(i + 3) % len(PEOPLE)]
        marketing.create(
            "lead",
            {
                "first_name": first,
                "last_name": f"{last}-{i}",
                "company": f"Prospect Co {i + 1}",
                "email": f"lead{i}@prospect{i}.example.com",
                "status": ["New", "Contacted", "Nurturing", "New"][i % 4],
                "lead_source": ["Web", "Event", "Advertisement", "Social Media"][i % 4],
                "rating": ["Hot", "Warm", "Cold"][i % 3],
                "email_opt_in": i % 2 == 0,
            },
        )
        count += 1

    for i, (subject, priority) in enumerate(
        [
            ("Cannot log in to portal", "High"),
            ("Invoice query", "Medium"),
            ("Feature request: export", "Low"),
            ("Outage at Sydney office", "Critical"),
            ("Change billing contact", "Low"),
            ("Training booking", "Medium"),
        ]
    ):
        contact = contacts[i % len(contacts)]
        service.create(
            "case",
            {
                "subject": subject,
                "priority": priority,
                "contact": str(contact.id),
                "origin": ["Email", "Phone", "Web"][i % 3],
                "description": f"{subject}. Reported by {contact.name}.",
            },
        )
        count += 1

    campaign = marketing.create(
        "campaign",
        {
            "name": "Spring Expo 2026",
            "type": "Event",
            "status": "In Progress",
            "start_date": (today - timedelta(days=10)).isoformat(),
            "end_date": (today + timedelta(days=20)).isoformat(),
            "budgeted_cost": 15000,
            "actual_cost": 9200,
            "expected_revenue": 120000,
        },
    )
    count += 1
    for c in contacts[:5]:
        marketing.create(
            "campaign_member", {"campaign": str(campaign.id), "contact": str(c.id), "status": "Sent"}
        )
        count += 1
    marketing.create(
        "email_template",
        {
            "name": "Monthly newsletter",
            "subject": "News from us, {{first_name}}",
            "html_body": "<p>Hi {{first_name}},</p><p>Here's what's new this month.</p>",
            "category": "Newsletter",
        },
    )
    count += 1

    quote = sales.create(
        "quote",
        {"title": "Implementation proposal", "account": str(accounts[0].id), "contact": str(contacts[0].id)},
    )
    sales.create("quote_line", {"quote": str(quote.id), "product": str(products[1].id), "quantity": 1})
    sales.create(
        "quote_line", {"quote": str(quote.id), "product": str(products[3].id), "quantity": 2, "discount": 300}
    )
    count += 3
    invoice = finance.create("invoice", {"account": str(accounts[1].id), "contact": str(contacts[2].id)})
    finance.create(
        "invoice_line", {"invoice": str(invoice.id), "product": str(products[2].id), "quantity": 1}
    )
    count += 2
    from app.apps.billing import issue_invoice

    issue_invoice(finance, invoice, {})
    finance.create(
        "payment",
        {"invoice": str(invoice.id), "amount": 2000, "method": "Bank Transfer", "reference": "EFT-0001"},
    )
    count += 1

    for i, c in enumerate(contacts[:6]):
        owner = sales if i % 2 else manager
        owner.create(
            "task",
            {
                "name": ["Follow up call", "Send proposal", "Book demo"][i % 3],
                "related_to": str(c.id),
                "who": str(c.id),
                "due_date": (today + timedelta(days=i - 2)).isoformat(),
                "priority": "High" if i == 0 else "Normal",
            },
        )
        count += 1
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    sales.create(
        "event",
        {
            "name": "Quarterly business review",
            "related_to": str(accounts[0].id),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
            "location": "Teams",
        },
    )
    count += 1
    _ = admin
    db.commit()
    return count


def seed_load_data(db: Session, object_api_name: str, count: int, owner_ids: list[uuid.UUID]) -> int:
    """Bulk rows for performance tests (bypasses hooks; only for disposable databases)."""
    rnd = random.Random(7)  # noqa: S311 - synthetic test data
    industries = ["Retail", "Finance", "Technology", "Healthcare", "Education", "Transport"]
    batch = 5000
    done = 0
    while done < count:
        n = min(batch, count - done)
        rows = []
        for i in range(n):
            k = done + i
            data: dict[str, Any] = {
                "industry": rnd.choice(industries),
                "type": rnd.choice(["Customer", "Prospect", "Partner"]),
                "annual_revenue": rnd.randint(1, 5000) * 1000,
                "phone": f"+6129{k % 10_000_000:07d}",
            }
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "obj": object_api_name,
                    "name": f"Load {object_api_name} {k:07d}",
                    "owner": rnd.choice(owner_ids),
                    "data": json.dumps(data),
                    "search": f"Load {object_api_name} {k:07d}",
                }
            )
        db.execute(
            text(
                "INSERT INTO records (id, object_api_name, name, owner_id, data, created_at, updated_at, is_deleted, version, search_vector) "
                "VALUES (:id, :obj, :name, :owner, CAST(:data AS jsonb), now(), now(), false, 1, to_tsvector('simple', :search))"
            ),
            rows,
        )
        db.commit()
        done += n
    return done
