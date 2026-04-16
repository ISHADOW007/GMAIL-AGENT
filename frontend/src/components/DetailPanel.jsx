/* Context panel that shows the full details of the selected dashboard item. */
function renderLines(value) {
  if (!value) {
    return "No details available yet.";
  }
  return value;
}

function renderThreadMessages(messages = []) {
  if (!messages.length) {
    return "No thread history captured.";
  }

  return messages
    .map(
      (message) =>
        `${message.received_at}\n${message.from_address}\n${message.summary || "No summary"}`
    )
    .join("\n\n");
}

function renderReviewHistory(history = []) {
  if (!history.length) {
    return "No review history yet.";
  }

  return history
    .map((entry) => {
      const parts = [
        `${entry.created_at || "Unknown time"} - ${entry.reviewer || "reviewer"} chose ${entry.decision}`,
      ];
      if (entry.comments) {
        parts.push(`Comments: ${entry.comments}`);
      }
      if (entry.updated_draft?.body) {
        parts.push(`Updated draft: ${entry.updated_draft.body}`);
      }
      return parts.join("\n");
    })
    .join("\n\n");
}

export default function DetailPanel({ item }) {
  return (
    <section className="panel panel--detail">
      <div className="panel__header">
        <div>
          <h2>Detail panel</h2>
          <p>
            {item
              ? "Inspect the selected email, draft, thread context, or review state."
              : "Select an unread email, review item, or activity card to inspect it here."}
          </p>
        </div>
      </div>

      {!item ? (
        <div className="empty-state">Nothing selected yet.</div>
      ) : (
        <div className="detail-panel">
          <div className="detail-panel__header">
            <div>
              <span className="eyebrow">{item.kind || "item"}</span>
              <h3>{item.subject}</h3>
              <p>{item.from_address || item.to_address || "Unknown sender"}</p>
            </div>
            <div className="detail-panel__badges">
              {item.received_at ? (
                <span className="pill">{new Date(item.received_at).toLocaleString()}</span>
              ) : null}
              {item.delivery_status ? (
                <span className={`pill pill--${item.delivery_status}`}>{item.delivery_status}</span>
              ) : null}
              {item.status ? <span className="pill pill--soft">{item.status}</span> : null}
              {typeof item.resumable === "boolean" ? (
                <span className={`pill ${item.resumable ? "pill--resumable" : "pill--legacy"}`}>
                  {item.resumable ? "Resumable" : "Legacy"}
                </span>
              ) : null}
            </div>
          </div>

          <div className="detail-grid">
            <div className="detail-card">
              <h4>Summary</h4>
              <p>{item.summary || item.reason || "No summary available."}</p>
            </div>

            <div className="detail-card">
              <h4>Body / Notes</h4>
              <pre>{renderLines(item.body || item.comments || item.resume_note)}</pre>
            </div>

            <div className="detail-card">
              <h4>Draft</h4>
              {item.draft ? (
                <>
                  <p><strong>{item.draft.subject}</strong></p>
                  <pre>{renderLines(item.draft.body)}</pre>
                </>
              ) : (
                <p>No draft attached.</p>
              )}
            </div>

            <div className="detail-card">
              <h4>Decision data</h4>
              <div className="detail-tags">
                {item.intent ? <span className="pill pill--soft">{item.intent}</span> : null}
                {item.urgency ? <span className="pill pill--soft">{item.urgency}</span> : null}
                {item.risk ? <span className="pill pill--soft">{item.risk}</span> : null}
                {item.action ? <span className="pill pill--soft">{item.action}</span> : null}
              </div>
              <p>{item.reason || item.resume_note || "No decision notes available."}</p>
            </div>

            <div className="detail-card">
              <h4>Thread history</h4>
              <pre>{renderThreadMessages(item.state_snapshot?.thread_messages)}</pre>
            </div>

            <div className="detail-card">
              <h4>Review history</h4>
              <pre>{renderReviewHistory(item.review_history)}</pre>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

