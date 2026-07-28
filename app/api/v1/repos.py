import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.org import User
from app.models.repository import Repository
from app.schemas.common import RepositoryCreate, RepositoryOut

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.get("", response_model=list[RepositoryOut])
async def list_repos(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Repository]:
    result = await db.execute(
        select(Repository).where(Repository.organization_id == organization_id)
    )
    return list(result.scalars().all())


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
async def link_repo(
    organization_id: uuid.UUID,
    payload: RepositoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Repository:
    repo = Repository(organization_id=organization_id, **payload.model_dump())
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepositoryOut)
async def get_repo(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Repository:
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found")
    return repo


@router.post("/{repo_id}/webhook", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receives GitHub webhook events (push, pull_request, workflow_run).
    
    Validates HMAC-SHA256 signature against GITHUB_WEBHOOK_SECRET.
    Parses event and enqueues Celery tasks for processing.
    
    GitHub sends:
    - X-Hub-Signature-256: sha256=<hmac>
    - X-GitHub-Event: <event_type>
    """
    from app.services.github_webhook import GithubWebhookHandler, verify_github_signature

    # Validate webhook signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(await request.body(), signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    # Parse event
    event_type = request.headers.get("X-GitHub-Event", "")
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid JSON: {str(e)}")

    # Process webhook
    handler = GithubWebhookHandler()
    result = await handler.handle_webhook(event_type, payload, db)

    return result
