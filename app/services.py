import time

from sqlalchemy import delete

from .extensions import db
from .models import EvaluationDraft, StudentImportBatch


def cleanup_expired_previews():
    now = int(time.time())
    imports = db.session.execute(
        delete(StudentImportBatch).where(StudentImportBatch.expires_at <= now)
    )
    fiaps = db.session.execute(
        delete(EvaluationDraft).where(EvaluationDraft.expires_at <= now)
    )
    db.session.commit()
    return imports.rowcount or 0, fiaps.rowcount or 0
