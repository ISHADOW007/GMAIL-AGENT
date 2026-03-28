import { useState } from "react";

import EmailList from "./EmailList";

export default function ReviewQueuePanel({ items, onAction, onSelect, selectedKey }) {
  const [notes, setNotes] = useState({});
  const [busyId, setBusyId] = useState("");

  const runAction = async (reviewId, decision) => {
    setBusyId(`${reviewId}:${decision}`);
    try {
      await onAction(reviewId, decision, notes[reviewId] || "");
      setNotes((current) => ({ ...current, [reviewId]: "" }));
    } finally {
      setBusyId("");
    }
  };

  return (
    <EmailList
      title="Human review queue"
      subtitle="Messages the agent deliberately held back for a person."
      items={items}
      emptyMessage="No manual reviews are waiting."
      onSelect={onSelect}
      selectedKey={selectedKey}
      renderMeta={(item) => (
        <div className="review-card">
          <div className="review-card__topline">
            <span>{new Date(item.created_at).toLocaleString()}</span>
            <span className={`pill ${item.resumable ? "pill--resumable" : "pill--legacy"}`}>
              {item.resumable ? "Resumable" : "Legacy"}
            </span>
          </div>
          <span className="reason">{item.reason}</span>
          {!item.resumable ? (
            <span className="review-card__hint">
              Legacy item: status can be updated, but full graph resume is not available.
            </span>
          ) : null}
          <textarea
            className="review-card__notes"
            rows={3}
            placeholder="Add review notes for approve, revise, or reject..."
            value={notes[item.review_id] || ""}
            onChange={(event) =>
              setNotes((current) => ({
                ...current,
                [item.review_id]: event.target.value,
              }))
            }
          />
          <div className="review-card__actions">
            <button
              className="button button--tiny button--approve"
              onClick={() => runAction(item.review_id, "approve")}
              disabled={Boolean(busyId) || !item.resumable}
            >
              {busyId === `${item.review_id}:approve` ? "Approving..." : "Approve"}
            </button>
            <button
              className="button button--tiny button--revise"
              onClick={() => runAction(item.review_id, "revise")}
              disabled={Boolean(busyId) || !item.resumable}
            >
              {busyId === `${item.review_id}:revise` ? "Saving..." : "Revise"}
            </button>
            <button
              className="button button--tiny button--reject"
              onClick={() => runAction(item.review_id, "reject")}
              disabled={Boolean(busyId)}
            >
              {busyId === `${item.review_id}:reject` ? "Rejecting..." : "Reject"}
            </button>
          </div>
        </div>
      )}
    />
  );
}
