"""Marketing app business logic (plan v3, section 8): campaign members, segments, consent, e-mail sends.

E-mail sends go to segment or campaign members, minus anyone without e-mail opt-in (or opted out),
hard-bounced or duplicated. Every message carries an unsubscribe link and the sender's identity and
postal address (Spam Act 2003); opens and clicks are tracked; unsubscribing updates consent at once.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import secrets
import uuid
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import false, func, select, update
from sqlalchemy.orm import Session

from app.apps.sales import BusinessRuleError, ensure_unique, rule
from app.auth.security import _secret
from app.engine.filters import compile_filter
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.types import format_datetime, parse_datetime
from app.models import EmailDelivery, Record
from app.services.email import app_link
from app.services.settings import get_setting

PERSON_OBJECTS = ("contact", "lead")
MERGE_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
HREF_RE = re.compile(r'href="(https?://[^"]+)"', re.IGNORECASE)


# ------------------------------------------------------------------ campaign members


@on("campaign_member", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def member_rules(change: Change) -> None:
    data = change.data
    lead, contact = data.get("lead"), data.get("contact")
    if not lead and not contact:
        raise rule("Choose a lead or a contact.", "contact")
    if change.record is None:
        campaign = str(data.get("campaign"))
        key = (
            {"campaign": campaign, "contact": str(contact)}
            if contact
            else {"campaign": campaign, "lead": str(lead)}
        )
        ensure_unique(
            change.svc, "campaign_member", key, None, "This person is already a member of the campaign."
        )
    person = change.svc.db.get(Record, ref(contact or lead))
    if person is not None:
        change.system["name"] = person.name
    if data.get("status") in ("Responded", "Registered", "Attended") and not data.get("has_responded"):
        data["has_responded"] = True
        data["first_responded_date"] = date.today().isoformat()


@action("campaign", "add_members", "Add Members", requires_edit=False)
def add_members(svc: RecordService, campaign: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """payload: {"record_ids": [...]} (leads/contacts) or {"segment_id": uuid}; optional "status"."""
    if not svc.policy.object("campaign_member").create:
        raise rule("You don't have permission to add campaign members.")
    status = payload.get("status") or "Planned"
    ids: list[uuid.UUID] = [uuid.UUID(str(i)) for i in payload.get("record_ids") or []]
    if payload.get("segment_id"):
        segment = svc.get("segment", uuid.UUID(str(payload["segment_id"])))
        ids += [r.id for r in segment_members(svc, segment, limit=10_000)]
    added = skipped = 0
    for rid in dict.fromkeys(ids):
        person = svc.db.get(Record, rid)
        if (
            person is None
            or person.object_api_name not in PERSON_OBJECTS
            or not svc.visible_ids(person.object_api_name, [rid])
        ):
            skipped += 1
            continue
        try:
            with svc.db.begin_nested():
                svc.create(
                    "campaign_member",
                    {"campaign": str(campaign.id), person.object_api_name: str(rid), "status": status},
                )
            added += 1
        except Exception:
            skipped += 1
    return {"added": added, "skipped": skipped}


# ------------------------------------------------------------------ segments


def segment_filter(segment: Record) -> dict[str, Any] | None:
    raw = segment.data.get("criteria")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise BusinessRuleError(
            "Segment criteria must be valid JSON.", fields={"criteria": "Invalid JSON"}
        ) from exc
    if not isinstance(parsed, dict):
        raise BusinessRuleError(
            "Segment criteria must be a filter object.", fields={"criteria": "Invalid filter"}
        )
    return parsed


def segment_members(svc: RecordService, segment: Record, *, limit: int = 50_000) -> list[Record]:
    target = segment.data.get("target_object") or "contact"
    filters = segment_filter(segment)
    meta = svc.registry.get(target)
    stmt = svc.base_query(meta)
    if filters:
        stmt = stmt.where(compile_filter(meta, filters, Record, None, user_id=svc.user_id))
    return list(svc.db.scalars(stmt.order_by(Record.created_at).limit(limit)))


@on("segment", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def segment_rules(change: Change) -> None:
    target = change.data.get("target_object") or "contact"
    if target not in PERSON_OBJECTS:
        raise rule("Segments contain contacts or leads.", "target_object")
    if change.record is not None and change.is_changed("target_object") and change.data.get("criteria"):
        change.data["criteria"] = None
    filters = None
    raw = change.data.get("criteria")
    if raw:
        try:
            filters = json.loads(raw)
        except ValueError as exc:
            raise BusinessRuleError(
                "Segment criteria must be valid JSON.", fields={"criteria": "Invalid JSON"}
            ) from exc
    meta = change.svc.registry.get(target)
    if filters:
        compile_filter(meta, filters, Record, None, user_id=change.svc.user_id)
    count_stmt = change.svc.elevated().base_query(meta)
    if filters:
        count_stmt = count_stmt.where(compile_filter(meta, filters, Record, None, user_id=change.svc.user_id))
    change.data["member_count"] = int(
        change.svc.db.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
    )
    change.data["counted_at"] = format_datetime(datetime.now(UTC))


@action("segment", "refresh_count", "Refresh Count")
def refresh_segment(svc: RecordService, segment: Record, payload: dict[str, Any]) -> dict[str, Any]:
    svc.elevated().update(
        "segment", segment.id, {"counted_at": format_datetime(datetime.now(UTC))}, record=segment
    )
    return svc.serialize(segment)


# ------------------------------------------------------------------ consent


@on("consent", Event.BEFORE_CREATE)
def consent_rules(change: Change) -> None:
    if not change.data.get("contact") and not change.data.get("lead"):
        raise rule("Consent belongs to a contact or a lead.", "contact")


@on("consent", Event.BEFORE_UPDATE, Event.BEFORE_DELETE)
def consent_history_is_kept(change: Change) -> None:
    if not change.svc.system and (
        change.changed - {"notes", "contact"} or (change.record is not None and not change.changed)
    ):
        raise rule("Consent records are a history; add a new consent record instead.")


@on("consent", Event.AFTER_CREATE)
def consent_applies(change: Change) -> None:
    """The latest e-mail consent drives the person's E-mail Opt-in flag."""
    if change.data.get("channel") != "Email":
        return
    opted_in = change.data.get("status") == "Opted In"
    sys = change.svc.elevated()
    for obj in PERSON_OBJECTS:
        rid = ref(change.data.get(obj))
        if rid is None:
            continue
        person = sys.db.get(Record, rid)
        if person is not None and not person.is_deleted and bool(person.data.get("email_opt_in")) != opted_in:
            sys.update(obj, person.id, {"email_opt_in": opted_in}, record=person)


def record_consent(
    svc: RecordService,
    person: Record,
    status: str,
    source: str,
    ip: str | None = None,
    notes: str | None = None,
) -> Record:
    return svc.elevated().create(
        "consent",
        {
            person.object_api_name: str(person.id),
            "channel": "Email",
            "status": status,
            "source": source,
            "ip_address": ip,
            "notes": notes,
            "captured_at": format_datetime(datetime.now(UTC)),
        },
    )


# ------------------------------------------------------------------ e-mail sends


@on("email_send", Event.BEFORE_CREATE)
def send_defaults(change: Change) -> None:
    data = change.data
    settings = get_setting(change.svc.db, "marketing") or {}
    data["status"] = "Draft"
    data.setdefault("from_name", settings.get("from_name"))
    if settings.get("from_email"):
        data.setdefault("from_email", settings.get("from_email"))
    template = change.svc.db.get(Record, ref(data.get("template"))) if data.get("template") else None
    if template is not None:
        data.setdefault("html_body", template.data.get("html_body"))
        data.setdefault("text_body", template.data.get("text_body"))
        if not data.get("subject"):
            data["subject"] = template.data.get("subject")


@on("email_send", Event.BEFORE_UPDATE)
def send_locked(change: Change) -> None:
    if change.old.get("status") not in ("Draft", "Scheduled") and not change.svc.system:
        raise rule("E-mails that are sending or sent can't be changed.")
    if change.is_changed("template") and change.data.get("template"):
        template = change.svc.db.get(Record, ref(change.data["template"]))
        if template is not None:
            change.data["html_body"] = template.data.get("html_body")
            change.data["text_body"] = template.data.get("text_body")


def _require_mass_email(svc: RecordService) -> None:
    from app.security.catalog import SystemPermission

    if not svc.system and not svc.policy.has(SystemPermission.SEND_MASS_EMAIL):
        raise rule("Sending e-mails to segments and campaigns needs the Send Mass Email permission.")


def _check_ready(send: Record) -> None:
    if not send.data.get("segment") and not send.data.get("campaign"):
        raise BusinessRuleError("Choose a segment or a campaign.", fields={"segment": "Required"})
    if not (send.data.get("html_body") or send.data.get("text_body")):
        raise BusinessRuleError("Add content to the e-mail.", fields={"html_body": "Required"})
    if not send.data.get("subject"):
        raise BusinessRuleError("Enter a subject.", fields={"subject": "Required"})


@action("email_send", "schedule", "Schedule", visible=lambda r: r.data.get("status") == "Draft")
def schedule_send(svc: RecordService, send: Record, payload: dict[str, Any]) -> dict[str, Any]:
    _require_mass_email(svc)
    if send.data.get("status") != "Draft":
        raise rule("Only draft e-mails can be scheduled.")
    _check_ready(send)
    when = payload.get("scheduled_at") or send.data.get("scheduled_at")
    when_dt = parse_datetime(when) if when else datetime.now(UTC)
    svc.elevated().update(
        "email_send", send.id, {"status": "Scheduled", "scheduled_at": format_datetime(when_dt)}, record=send
    )
    if when_dt <= datetime.now(UTC):
        from app.worker.tasks import enqueue_email_send

        enqueue_email_send(send.id)
    return svc.serialize(send)


@action("email_send", "cancel", "Cancel", visible=lambda r: r.data.get("status") == "Scheduled")
def cancel_send(svc: RecordService, send: Record, payload: dict[str, Any]) -> dict[str, Any]:
    if send.data.get("status") != "Scheduled":
        raise rule("Only scheduled e-mails can be cancelled.")
    svc.elevated().update("email_send", send.id, {"status": "Cancelled"}, record=send)
    return svc.serialize(send)


def _latest_email_consent(db: Session, obj: str, person_id: uuid.UUID) -> str | None:
    row = db.scalar(
        select(Record)
        .where(
            Record.object_api_name == "consent",
            Record.is_deleted == false(),
            Record.data[obj].astext == str(person_id),
            Record.data["channel"].astext == "Email",
        )
        .order_by(Record.created_at.desc())
        .limit(1)
    )
    return row.data.get("status") if row else None


def build_recipients(db: Session, send: Record) -> list[EmailDelivery]:
    """Resolve recipients and create delivery rows (skipped ones keep the reason)."""
    svc = RecordService.as_system(db, send.owner_id)
    people: list[Record] = []
    if send.data.get("segment"):
        segment = db.get(Record, ref(send.data["segment"]))
        if segment is not None:
            people += segment_members(svc, segment)
    if send.data.get("campaign"):
        members = db.scalars(
            select(Record).where(
                Record.object_api_name == "campaign_member",
                Record.is_deleted == false(),
                Record.data["campaign"].astext == str(send.data["campaign"]),
            )
        ).all()
        for m in members:
            person = db.get(Record, ref(m.data.get("contact") or m.data.get("lead")))
            if person is not None and not person.is_deleted:
                people.append(person)
    seen: set[str] = set()
    out: list[EmailDelivery] = []
    for person in people:
        email = (person.data.get("email") or "").strip().lower()
        reason = None
        if not email:
            reason = "no_email"
        elif email in seen:
            reason = "duplicate"
        elif person.data.get("email_bounced"):
            reason = "bounced"
        elif (
            not person.data.get("email_opt_in")
            or _latest_email_consent(db, person.object_api_name, person.id) == "Opted Out"
        ):
            reason = "no_consent"
        if email:
            seen.add(email)
        delivery = EmailDelivery(
            send_record_id=send.id,
            recipient_record_id=person.id,
            email=email or "-",
            status="skipped" if reason else "queued",
            skip_reason=reason,
            tracking_token=secrets.token_urlsafe(24),
        )
        db.add(delivery)
        out.append(delivery)
    db.flush()
    return out


def _sign(token: str, url: str) -> str:
    return hmac.new(_secret().encode(), f"{token}|{url}".encode(), hashlib.sha256).hexdigest()[:32]


def click_link(token: str, url: str) -> str:
    return app_link(f"/api/v1/public/e/{token}/click?" + urlencode({"u": url, "s": _sign(token, url)}))


def verify_click(token: str, url: str, signature: str) -> bool:
    return hmac.compare_digest(_sign(token, url), signature)


def render_message(
    send: Record,
    person: Record | None,
    delivery: EmailDelivery,
    company: dict[str, Any],
    marketing: dict[str, Any],
) -> tuple[str, str, str]:
    """(subject, text, html) with merge fields, tracked links, open pixel, unsubscribe and sender identity."""
    data = person.data if person else {}
    merge = {
        "first_name": data.get("first_name") or "",
        "last_name": data.get("last_name") or "",
        "name": person.name if person else "",
        "email": delivery.email,
        "company": data.get("company") or "",
        "unsubscribe_url": app_link(f"/unsubscribe/{delivery.tracking_token}"),
    }

    def fill(text: str, escape: bool) -> str:
        return MERGE_RE.sub(
            lambda m: html.escape(merge.get(m.group(1), "")) if escape else merge.get(m.group(1), ""), text
        )

    subject = fill(str(send.data.get("subject") or ""), False)
    sender = marketing.get("from_name") or company.get("legal_name") or "Us"
    address = marketing.get("postal_address") or company.get("address") or ""
    sender_line = f"Sent by {sender}{', ' + address if address else ''}."
    footer_text = f"\n\n--\n{sender_line}\nUnsubscribe: {merge['unsubscribe_url']}\n"
    text = (
        fill(
            str(send.data.get("text_body") or re.sub(r"<[^>]+>", "", str(send.data.get("html_body") or ""))),
            False,
        )
        + footer_text
    )
    body_html = fill(
        str(
            send.data.get("html_body")
            or html.escape(str(send.data.get("text_body") or "")).replace("\n", "<br>")
        ),
        True,
    )
    body_html = HREF_RE.sub(
        lambda m: f'href="{html.escape(click_link(delivery.tracking_token, html.unescape(m.group(1))))}"',
        body_html,
    )
    pixel = app_link(f"/api/v1/public/e/{delivery.tracking_token}/open.gif")
    body_html += (
        f'<hr><p style="font-size:12px;color:#64748b">Sent by {html.escape(sender)}'
        f"{', ' + html.escape(address) if address else ''}. "
        f'<a href="{html.escape(merge["unsubscribe_url"])}">Unsubscribe</a></p>'
        f'<img src="{html.escape(pixel)}" width="1" height="1" alt="">'
    )
    return subject, text, body_html


def process_send(db: Session, send_id: uuid.UUID) -> dict[str, int]:
    """Worker job: resolve recipients and deliver in batches, then roll up the counts."""
    from app.services.email import deliver_message

    send = db.scalar(select(Record).where(Record.id == send_id).with_for_update())
    if send is None or send.data.get("status") not in ("Scheduled", "Sending"):
        return {}
    svc = RecordService.as_system(db, send.owner_id)
    if send.data.get("status") == "Scheduled":
        svc.update("email_send", send.id, {"status": "Sending"}, record=send)
        build_recipients(db, send)
        db.commit()
    company = get_setting(db, "company") or {}
    marketing = get_setting(db, "marketing") or {}
    batch = int(marketing.get("batch_size") or 200)
    while True:
        rows = db.scalars(
            select(EmailDelivery)
            .where(EmailDelivery.send_record_id == send.id, EmailDelivery.status == "queued")
            .limit(batch)
            .with_for_update(skip_locked=True)
        ).all()
        if not rows:
            break
        for d in rows:
            person = db.get(Record, d.recipient_record_id) if d.recipient_record_id else None
            subject, text, body_html = render_message(send, person, d, company, marketing)
            try:
                deliver_message(
                    d.email,
                    subject,
                    text,
                    html_body=body_html,
                    from_name=send.data.get("from_name"),
                    from_email=send.data.get("from_email"),
                    headers={"List-Unsubscribe": f"<{app_link('/unsubscribe/' + d.tracking_token)}>"},
                )
                d.status = "sent"
                d.sent_at = datetime.now(UTC)
            except Exception as exc:
                d.status = "failed"
                d.error = str(exc)[:500]
        db.commit()
    rollup_send(db, send.id)
    send = db.get(Record, send_id)
    assert send is not None
    RecordService.as_system(db, send.owner_id).update(
        "email_send", send.id, {"status": "Sent", "sent_at": format_datetime(datetime.now(UTC))}, record=send
    )
    db.commit()
    return {"sent": int(send.data.get("delivered_count") or 0)}


def rollup_send(db: Session, send_id: uuid.UUID) -> None:
    counts = dict(
        db.execute(
            select(EmailDelivery.status, func.count())
            .where(EmailDelivery.send_record_id == send_id)
            .group_by(EmailDelivery.status)
        ).all()
    )
    opened = (
        db.scalar(
            select(func.count()).where(
                EmailDelivery.send_record_id == send_id, EmailDelivery.opened_at.is_not(None)
            )
        )
        or 0
    )
    clicked = (
        db.scalar(
            select(func.count()).where(
                EmailDelivery.send_record_id == send_id, EmailDelivery.clicked_at.is_not(None)
            )
        )
        or 0
    )
    unsub = (
        db.scalar(
            select(func.count()).where(
                EmailDelivery.send_record_id == send_id, EmailDelivery.unsubscribed_at.is_not(None)
            )
        )
        or 0
    )
    send = db.get(Record, send_id)
    if send is None:
        return
    values = {
        "recipients_count": sum(counts.values()),
        "delivered_count": counts.get("sent", 0),
        "opened_count": int(opened),
        "clicked_count": int(clicked),
        "bounced_count": counts.get("bounced", 0),
        "unsubscribed_count": int(unsub),
        "skipped_count": counts.get("skipped", 0),
    }
    if any(send.data.get(k) != v for k, v in values.items()):
        RecordService.as_system(db).update("email_send", send.id, values, record=send)


def due_sends(db: Session) -> list[uuid.UUID]:
    now = format_datetime(datetime.now(UTC))
    return list(
        db.scalars(
            select(Record.id).where(
                Record.object_api_name == "email_send",
                Record.is_deleted == false(),
                Record.data["status"].astext == "Scheduled",
                Record.data["scheduled_at"].astext <= now,
            )
        )
    )


# ------------------------------------------------------------------ tracking & unsubscribe (public)


def delivery_by_token(db: Session, token: str) -> EmailDelivery | None:
    if not token or len(token) > 64:
        return None
    return db.scalar(select(EmailDelivery).where(EmailDelivery.tracking_token == token))


def track_open(db: Session, token: str) -> None:
    d = delivery_by_token(db, token)
    if d is None:
        return
    now = datetime.now(UTC)
    db.execute(
        update(EmailDelivery)
        .where(EmailDelivery.id == d.id)
        .values(
            open_count=EmailDelivery.open_count + 1, opened_at=func.coalesce(EmailDelivery.opened_at, now)
        )
    )
    db.commit()


def track_click(db: Session, token: str) -> None:
    d = delivery_by_token(db, token)
    if d is None:
        return
    now = datetime.now(UTC)
    db.execute(
        update(EmailDelivery)
        .where(EmailDelivery.id == d.id)
        .values(
            click_count=EmailDelivery.click_count + 1,
            clicked_at=func.coalesce(EmailDelivery.clicked_at, now),
            opened_at=func.coalesce(EmailDelivery.opened_at, now),
        )
    )
    db.commit()


def unsubscribe(db: Session, token: str, ip: str | None) -> bool:
    d = delivery_by_token(db, token)
    if d is None:
        return False
    if d.unsubscribed_at is None:
        d.unsubscribed_at = datetime.now(UTC)
        person = db.get(Record, d.recipient_record_id) if d.recipient_record_id else None
        if person is not None and not person.is_deleted:
            record_consent(
                RecordService.as_system(db),
                person,
                "Opted Out",
                "Unsubscribe Link",
                ip,
                f"Unsubscribed from send {d.send_record_id}",
            )
        db.flush()
        rollup_send(db, d.send_record_id)
    db.commit()
    return True


def web_to_lead(db: Session, payload: dict[str, Any], ip: str | None) -> Record:
    svc = RecordService.as_system(db)
    values = {
        k: payload.get(k)
        for k in ("first_name", "last_name", "company", "email", "phone", "title", "description")
        if payload.get(k)
    }
    values.setdefault("company", payload.get("last_name") or "Unknown")
    values["lead_source"] = "Web"
    opt_in = bool(payload.get("email_opt_in"))
    values["email_opt_in"] = opt_in
    lead = svc.create("lead", values)
    if opt_in:
        record_consent(svc, lead, "Opted In", "Web Form", ip)
    db.commit()
    return lead


__all__ = ["quote"]
