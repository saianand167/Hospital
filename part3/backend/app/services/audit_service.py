from sqlalchemy.orm import Session
from app import models
import logging

logger = logging.getLogger(__name__)

def log_audit_event(
    db: Session,
    user_id: str,
    action: str,
    target_id: str = None,
    details: dict = None
) -> models.AuditLog:
    """
    Log audit events (patient_created, visit_created, document_uploaded, document_verified, 
    doctor_viewed_record, prescription_created, prescription_confirmed, etc.)
    No sensitive raw payload logged unnecessarily.
    """
    try:
        log_entry = models.AuditLog(
            user_id=user_id,
            action=action,
            target_id=target_id,
            details=details or {}
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record audit log: {str(e)}")
        return None
