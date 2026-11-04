"""Professions a workspace can be set up for (plan v4, section 5).

Sign-up offers one card per domain. Provisioning calls ``apply_domain``, which installs the domain's pack
and its domain-first navigation (step 4 adds the Legal, Accounting and Loan Broker packs).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

DomainKey = Literal["legal", "migration", "accounting", "lending"]


@dataclass(frozen=True)
class Domain:
    key: DomainKey
    label: str
    profession: str
    description: str
    includes: tuple[str, ...]
    pack_key: str | None


DOMAINS: dict[str, Domain] = {
    d.key: d
    for d in (
        Domain(
            "legal",
            "Law firm",
            "Lawyers and legal practices",
            "Matters, parties, conflict checks, time recording, court dates and trust accounting.",
            ("Matters", "Conflict checks", "Time entries", "Court dates", "Trust ledger", "Costs disclosure"),
            "legal_practice",
        ),
        Domain(
            "migration",
            "Migration agency",
            "Registered migration agents",
            "Visa matters, client documents, application stages, deadlines and Code of Conduct compliance.",
            ("Visa matters", "Document checklists", "Stages and deadlines", "Agreements", "Client portal"),
            "migration_agency",
        ),
        Domain(
            "accounting",
            "Accounting practice",
            "Chartered accountants and tax agents",
            "Client entities, engagements, engagement letters, lodgement deadlines and document requests.",
            ("Engagements", "Engagement letters", "Lodgement deadlines", "Document requests", "Time entries"),
            "accounting_practice",
        ),
        Domain(
            "lending",
            "Loan broking",
            "Mortgage and finance brokers",
            "Loan applications from fact find to settlement, lenders, commissions and credit compliance.",
            ("Loan applications", "Fact finds", "Lender panel", "Commissions", "Credit guide and BID"),
            "loan_broker",
        ),
    )
}


def apply_domain(db: Session, domain: str, actor_id: uuid.UUID | None) -> None:
    """Install the domain's pack (when available) into the session's tenant. Caller commits."""
    from app import packs

    spec = DOMAINS.get(domain)
    if spec is None or spec.pack_key is None:
        return
    if spec.pack_key not in {p.key for p in packs.available()}:
        return
    packs.install(db, spec.pack_key, actor_id)
