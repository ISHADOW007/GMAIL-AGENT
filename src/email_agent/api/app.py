"""FastAPI application exposing dashboard, review, run, and progress endpoints."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from email_agent.services.agent_service import (
    collect_dashboard_snapshot,
    collect_progress_snapshot,
    run_agent,
)
from email_agent.services.review_resume_service import (
    approve_review as approve_review_action,
    reject_review as reject_review_action,
    revise_review as revise_review_action,
)
from email_agent.services.review_service import list_review_items


class RunRequest(BaseModel):
    limit: int | None = None


class ReviewDecisionRequest(BaseModel):
    comments: str | None = None
    reviewer: str | None = "dashboard"


app = FastAPI(title="Email Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard(limit: int = 5) -> dict:
    return collect_dashboard_snapshot(limit=limit)


@app.get("/api/progress")
def progress() -> dict:
    return collect_progress_snapshot()


@app.get("/api/reviews")
def reviews(status: str = "pending", limit: int = 20) -> dict:
    return {"items": list_review_items(status=status or None, limit=limit)}


def _resolve_review_decision(review_id: str, decision: str, payload: ReviewDecisionRequest) -> dict:
    try:
        if decision == "approve":
            item = approve_review_action(
                review_id,
                comments=payload.comments,
                reviewer=payload.reviewer,
            )
        elif decision == "revise":
            item = revise_review_action(
                review_id,
                comments=payload.comments,
                reviewer=payload.reviewer,
            )
        else:
            item = reject_review_action(
                review_id,
                comments=payload.comments,
                reviewer=payload.reviewer,
            )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"item": item}


@app.post("/api/reviews/{review_id}/approve")
def approve_review(review_id: str, payload: ReviewDecisionRequest) -> dict:
    return _resolve_review_decision(review_id, "approve", payload)


@app.post("/api/reviews/{review_id}/revise")
def revise_review(review_id: str, payload: ReviewDecisionRequest) -> dict:
    return _resolve_review_decision(review_id, "revise", payload)


@app.post("/api/reviews/{review_id}/reject")
def reject_review(review_id: str, payload: ReviewDecisionRequest) -> dict:
    return _resolve_review_decision(review_id, "reject", payload)


@app.post("/api/run")
def trigger_run(payload: RunRequest) -> dict:
    return run_agent(limit=payload.limit, include_draft_body=True)


def main() -> None:
    uvicorn.run(
        "email_agent.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()

