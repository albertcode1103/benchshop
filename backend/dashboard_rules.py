"""Shared read-only work queue predicates. SQLite timestamps without offsets are UTC."""

from datetime import datetime, timezone


INQUIRY_BUSINESS_SQL = """CASE WHEN i.status IN ('closed','cancelled') THEN i.status
    WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='sent') THEN 'sent'
    WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='draft') THEN 'pending'
    WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='archived') THEN 'archived'
    WHEN i.status='quoted' THEN 'pending' ELSE i.status END"""


def utc_now():
    return datetime.now(timezone.utc)


def inquiry_queue_clause(actor_id, actor_role, queue, now):
    if queue not in ('followup', 'stale'):
        return '', ()
    clause = " AND (" + INQUIRY_BUSINESS_SQL + ") IN ('new','assigned','contacted')"
    params = []
    if actor_role != 'admin':
        clause += ' AND i.assigned_to = ?'
        params.append(actor_id)
    if queue == 'stale':
        clause += " AND julianday(COALESCE(NULLIF(i.updated_at,''),i.created_at)) < julianday(?) - 3"
        params.append(now.isoformat())
    return clause, tuple(params)


# A date-only validity includes the whole Beijing calendar day. Offset timestamps
# represent exact instants. Both the dashboard and quote list use this expression.
QUOTE_EXPIRY_SQL = """CASE WHEN length(valid_until)=10
    THEN julianday(valid_until, '+1 day', '-8 hours')
    ELSE julianday(valid_until) END"""
QUOTE_DUE_SQL = "lifecycle_status='sent' AND (" + QUOTE_EXPIRY_SQL + ") > julianday(?) AND (" + QUOTE_EXPIRY_SQL + ") <= julianday(?) + 7"


def due_quote_order(db, now):
    rows = db.execute(
        'SELECT id FROM commerce_quotes WHERE ' + QUOTE_DUE_SQL + ' ORDER BY (' + QUOTE_EXPIRY_SQL + '), id',
        (now.isoformat(), now.isoformat()),
    )
    return {row[0]: index for index, row in enumerate(rows)}
