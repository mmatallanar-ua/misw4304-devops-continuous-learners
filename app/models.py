import uuid
from datetime import datetime, timezone

from .extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class BlacklistEntry(db.Model):
    __tablename__ = "blacklist_entries"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    app_uuid = db.Column(db.Uuid(as_uuid=True), nullable=False, default=uuid.uuid4)
    blocked_reason = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)  # 45 = IPv6 máximo
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
