"""Service d'écriture du journal d'audit métier."""
from sqlalchemy.orm import Session
from app.models.entities import AuditLog, User


def record_action(db: Session, user: User, action: str, entity: str, entity_id: object = None, details: str | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=str(entity_id) if entity_id is not None else None, details=details, ip_address=ip))

