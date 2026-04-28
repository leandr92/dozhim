from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import Campaign, CampaignMessage, Import, Job, OperatorQueueItem, Person
from app.db.session import get_db
from app.schemas.common import JobAccepted
from app.services.imports import read_rows, validate_and_diff
from app.services.jobs import new_job_id as generate_job_id

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(
    page: int = 1,
    page_size: int = 50,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Campaign).order_by(Campaign.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "status": row.status,
                "project_id": row.project_id,
                "import_id": row.import_id,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{campaign_id}/messages")
def list_campaign_messages(
    campaign_id: str,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    rows = (
        db.query(CampaignMessage)
        .filter(CampaignMessage.campaign_id == campaign_id)
        .order_by(CampaignMessage.created_at.asc())
        .all()
    )
    counters = {"ready": 0, "sent": 0, "blocked": 0, "review_required": 0}
    for row in rows:
        if row.status == "sent":
            counters["sent"] += 1
        elif row.status == "failed":
            counters["blocked"] += 1
        elif row.status == "review_required":
            counters["review_required"] += 1
        else:
            counters["ready"] += 1

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "project_id": campaign.project_id,
            "import_id": campaign.import_id,
        },
        "counters": counters,
        "items": [
            {
                "id": row.id,
                "to_email": row.to_email,
                "cc_emails": row.cc_emails or [],
                "subject": row.subject or "",
                "body": row.body or "",
                "status": row.status,
                "is_payload_immutable": row.is_payload_immutable,
                "email_sent_flag": row.email_sent_flag,
                "manual_fallback_comment": row.manual_fallback_comment,
                "revision": row.revision,
            }
            for row in rows
        ],
    }


@router.post(
    "/personalized/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAccepted,
)
async def upload_campaign_file(
    response: Response,
    file: UploadFile = File(...),
    dry_run: bool = Form(...),
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="File is required")
    content = await file.read()
    try:
        rows = read_rows(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    now = datetime.utcnow()
    import_version = f"imp-{int(now.timestamp())}-{uuid4().hex[:8]}"
    validation = validate_and_diff(db=db, project_id="system-project", rows=rows)
    import_status = "validated" if validation.is_valid else "failed"
    imported = Import(
        project_id="system-project",
        import_version=import_version,
        imported_by="api-user",
        imported_at=now,
        status=import_status,
        dry_run=dry_run,
        source_rows=rows,
        diff=validation.diff,
        errors={"messages": validation.errors},
    )
    db.add(imported)
    db.flush()
    if not validation.is_valid:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "message": "Импорт не прошел валидацию",
                "details": {"errors": validation.errors, "diff": validation.diff},
                "retryable": False,
                "correlation_id": "import-validation",
            },
        )

    campaign = Campaign(
        project_id="system-project",
        import_id=imported.id,
        name=f"Campaign {import_version}",
        status="ready_for_review",
    )
    db.add(campaign)
    db.flush()

    for row in rows:
        key = (row.get("Ссылка на проект") or "").strip()
        project_name = (row.get("Проект") or "").strip()
        recipient = (row.get("РП") or "").strip()
        owner = db.query(Person).filter(Person.email == recipient).first()
        message_status = "draft" if owner else "review_required"
        if not owner:
            db.add(
                OperatorQueueItem(
                    assignment_id=None,
                    type="owner_review",
                    reason="owner_not_found",
                    payload={"email": recipient, "target_object_external_key": key, "campaign_id": campaign.id},
                    status="new",
                )
            )
        db.add(
            CampaignMessage(
                campaign_id=campaign.id,
                to_email=recipient,
                subject=f"[Dozhim] Актуализация: {project_name}",
                body=f"Объект: {project_name}\nКлюч: {key}",
                status=message_status,
            )
        )

    job_id = generate_job_id()
    db.add(
        Job(
            id=job_id,
            kind="campaign_import",
            status="queued",
            payload={
                "filename": file.filename,
                "dry_run": dry_run,
                "import_version": import_version,
                "rows": len(rows),
            },
        )
    )
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return JobAccepted(job_id=job_id)


@router.patch("/{campaign_id}/messages/{message_id}")
def patch_campaign_message(
    campaign_id: str,
    message_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    message = db.get(CampaignMessage, message_id)
    if message is None or message.campaign_id != campaign_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.is_payload_immutable:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payload is immutable")

    message.subject = payload.get("subject", message.subject)
    message.body = payload.get("body", message.body)
    message.to_email = payload.get("to_email", message.to_email)
    if "cc_emails" in payload:
        message.cc_emails = payload.get("cc_emails") or []
    if "attachments" in payload:
        message.attachments = payload.get("attachments")
    message.revision += 1
    message.updated_at = datetime.utcnow()
    db.add(message)
    db.commit()
    return {"id": message.id, "revision": message.revision, "updated": True}


@router.post("/{campaign_id}/messages/{message_id}/manual-sent-flag")
def set_manual_sent_flag(
    campaign_id: str,
    message_id: str,
    payload: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    message = db.get(CampaignMessage, message_id)
    if message is None or message.campaign_id != campaign_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.is_payload_immutable:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payload is immutable")

    comment = (payload.get("comment") or "").strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Fallback comment is required")

    message.email_sent_flag = True
    message.manual_fallback_comment = comment
    message.status = "sent"
    message.is_payload_immutable = True
    message.revision += 1
    message.updated_at = datetime.utcnow()
    db.add(message)
    db.commit()
    return {"id": message.id, "status": message.status, "email_sent_flag": message.email_sent_flag}


@router.post("/{campaign_id}/approve-send", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def approve_send_campaign(
    campaign_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    campaign.status = "sending"
    db.add(campaign)

    job_id = generate_job_id()
    db.add(Job(id=job_id, kind="campaign_approve_send", status="queued", payload={"campaign_id": campaign_id}))
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return JobAccepted(job_id=job_id)


@router.post("/{campaign_id}/retry-failed", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def retry_failed_campaign_messages(
    campaign_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    job_id = generate_job_id()
    db.add(Job(id=job_id, kind="campaign_retry_failed", status="queued", payload={"campaign_id": campaign_id}))
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return JobAccepted(job_id=job_id)
