export default function HeroPanel({ loading, running, progress, onRefresh, onRun }) {
  const status = progress?.status || "idle";
  const currentEmail = progress?.current_email;
  const totalEmails = progress?.total_emails || 0;
  const processedCount = progress?.processed_count || 0;
  const percentComplete = Math.max(0, Math.min(100, progress?.percent_complete || 0));

  const statusLabel = {
    idle: "Idle",
    running: "Running",
    completed: "Completed",
    error: "Needs attention",
  }[status] || "Idle";

  const helperCopy = (() => {
    if (status === "running" && currentEmail?.subject) {
      return `Working on: ${currentEmail.subject}`;
    }
    if (status === "completed") {
      return totalEmails > 0
        ? `Finished processing ${processedCount} of ${totalEmails} email${totalEmails === 1 ? "" : "s"}.`
        : "Run finished with no unread emails to process.";
    }
    if (status === "error") {
      return progress?.error_message || "The last run hit an error before finishing.";
    }
    return "Ready to process the next unread batch.";
  })();

  return (
    <div className="hero">
      <div className="hero__copy">
        <span className="eyebrow">React control room</span>
        <h1>Email Agent Mission Desk</h1>
        <p>
          Watch unread emails, drafts, review pressure, and the last agent run
          from one place. This UI is backed by the Python agent API, not mock data.
        </p>
      </div>
      <div className="hero__actions">
        <div className="hero__progress">
          <div className="hero__progress-header">
            <span className={`pill pill--soft hero__status hero__status--${status}`}>
              {statusLabel}
            </span>
            <strong>
              {processedCount}/{totalEmails}
            </strong>
          </div>
          <div className="progress-track" aria-hidden="true">
            <div className="progress-track__fill" style={{ width: `${percentComplete}%` }} />
          </div>
          <p className="hero__progress-copy">{helperCopy}</p>
        </div>
        <button className="button button--primary" onClick={onRun} disabled={running}>
          {running ? "Running agent..." : "Process unread emails"}
        </button>
        <button className="button button--ghost" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh dashboard"}
        </button>
      </div>
    </div>
  );
}
