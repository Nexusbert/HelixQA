"""
GitHub webhook handler. Processes events from GitHub:
- push: creates new builds
- pull_request: tracks PR state
- workflow_run: processes test/security results from CI

Validates webhook signature against GITHUB_WEBHOOK_SECRET.
"""
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings


def verify_github_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """
    Verify GitHub webhook signature.
    
    GitHub sends X-Hub-Signature-256 header with HMAC-SHA256 of payload.
    Format: sha256=<hash>
    """
    if not signature_header or not settings.GITHUB_WEBHOOK_SECRET:
        return False

    expected_signature = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    # Compare as hex digests
    provided_signature = signature_header.replace("sha256=", "")
    return hmac.compare_digest(expected_signature, provided_signature)


def parse_webhook_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse GitHub webhook event into internal HelixQA format.
    
    Returns event dict or None if not relevant.
    """
    if event_type == "push":
        return parse_push_event(payload)
    elif event_type == "pull_request":
        return parse_pull_request_event(payload)
    elif event_type == "workflow_run":
        return parse_workflow_run_event(payload)
    return None


def parse_push_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse push event.
    
    Creates a Build entry for tracking.
    """
    repo = payload.get("repository", {})
    ref = payload.get("ref", "")
    pusher = payload.get("pusher", {})

    # Only track pushes to main/develop branches (configurable)
    branch = ref.split("/")[-1]
    if branch not in ("main", "develop", "master"):
        return None

    commits = payload.get("commits", [])
    if not commits:
        return None

    commit = commits[0]

    return {
        "event_type": "push",
        "repo": {
            "provider": "github",
            "external_id": str(repo.get("id")),
            "full_name": repo.get("full_name"),
        },
        "build": {
            "commit_sha": commit.get("id"),
            "branch": branch,
            "message": commit.get("message", ""),
            "author": pusher.get("name", "unknown"),
        },
    }


def parse_pull_request_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse pull_request event.
    
    Tracks PR state and head commit for comparison.
    """
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return None

    repo = payload.get("repository", {})
    pr = payload.get("pull_request", {})

    return {
        "event_type": "pull_request",
        "action": action,
        "repo": {
            "provider": "github",
            "external_id": str(repo.get("id")),
            "full_name": repo.get("full_name"),
        },
        "pull_request": {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "author": pr.get("user", {}).get("login"),
            "source_branch": pr.get("head", {}).get("ref"),
            "target_branch": pr.get("base", {}).get("ref"),
            "head_commit_sha": pr.get("head", {}).get("sha"),
            "state": pr.get("state"),
        },
    }


def parse_workflow_run_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse workflow_run event.
    
    Occurs when a GitHub Actions workflow completes.
    Includes link to workflow logs for ingestion.
    """
    action = payload.get("action")
    if action != "completed":
        return None

    workflow_run = payload.get("workflow_run", {})
    repo = payload.get("repository", {})

    return {
        "event_type": "workflow_run",
        "repo": {
            "provider": "github",
            "external_id": str(repo.get("id")),
            "full_name": repo.get("full_name"),
        },
        "build": {
            "commit_sha": workflow_run.get("head_sha"),
            "branch": workflow_run.get("head_branch"),
            "ci_provider": "github_actions",
            "external_build_id": str(workflow_run.get("id")),
            "status": workflow_run.get("conclusion"),  # success, failure, cancelled, etc.
            "logs_url": workflow_run.get("logs_url"),
        },
    }


class GithubWebhookHandler:
    """Processes GitHub webhook events and enqueues Celery tasks."""

    @staticmethod
    async def handle_webhook(
        event_type: str,
        payload: dict[str, Any],
        db_session,  # AsyncSession
    ) -> dict[str, Any]:
        """
        Handle incoming webhook event.
        
        Enqueues appropriate Celery tasks based on event type.
        """
        from app.models.repository import Build, PullRequest, Repository
        from sqlalchemy import select

        parsed = parse_webhook_event(event_type, payload)
        if not parsed:
            return {"status": "ignored", "reason": "not_applicable"}

        repo_info = parsed.get("repo", {})
        repo_external_id = repo_info.get("external_id")
        repo_full_name = repo_info.get("full_name")

        # Find or create repository
        repo_result = await db_session.execute(
            select(Repository).where(Repository.external_id == repo_external_id)
        )
        repo = repo_result.scalar_one_or_none()

        if not repo:
            # Repository not yet linked in HelixQA; ignore
            return {
                "status": "ignored",
                "reason": "repo_not_linked",
                "repo": repo_full_name,
            }

        if parsed["event_type"] == "push":
            build_info = parsed.get("build", {})
            build = Build(
                repository_id=repo.id,
                commit_sha=build_info.get("commit_sha"),
                branch=build_info.get("branch"),
                ci_provider="github_actions",
            )
            db_session.add(build)
            await db_session.commit()
            await db_session.refresh(build)

            return {
                "status": "created",
                "event_type": "push",
                "build_id": str(build.id),
                "commit_sha": build.commit_sha,
                "branch": build.branch,
            }

        elif parsed["event_type"] == "pull_request":
            pr_info = parsed.get("pull_request", {})
            pr = PullRequest(
                repository_id=repo.id,
                number=pr_info.get("number"),
                title=pr_info.get("title"),
                author=pr_info.get("author"),
                source_branch=pr_info.get("source_branch"),
                target_branch=pr_info.get("target_branch"),
                head_commit_sha=pr_info.get("head_commit_sha"),
                state=pr_info.get("state"),
            )
            db_session.add(pr)
            await db_session.commit()
            await db_session.refresh(pr)

            return {
                "status": "created",
                "event_type": "pull_request",
                "pr_id": str(pr.id),
                "pr_number": pr.number,
                "head_commit_sha": pr.head_commit_sha,
            }

        elif parsed["event_type"] == "workflow_run":
            build_info = parsed.get("build", {})
            # Find build by commit SHA
            build_result = await db_session.execute(
                select(Build).where(
                    Build.repository_id == repo.id,
                    Build.commit_sha == build_info.get("commit_sha"),
                )
            )
            build = build_result.scalar_one_or_none()

            if not build:
                # Create new build if not exists
                build = Build(
                    repository_id=repo.id,
                    commit_sha=build_info.get("commit_sha"),
                    branch=build_info.get("branch"),
                    ci_provider=build_info.get("ci_provider"),
                    external_build_id=build_info.get("external_build_id"),
                    logs_url=build_info.get("logs_url"),
                )
                db_session.add(build)
                await db_session.commit()
                await db_session.refresh(build)

            return {
                "status": "queued",
                "event_type": "workflow_run",
                "build_id": str(build.id),
                "external_build_id": build_info.get("external_build_id"),
                "logs_url": build_info.get("logs_url"),
                "note": "Workflow results can be ingested via /builds/{id}/ingest/* endpoints",
            }

        return {"status": "unknown"}
