/* Live execution board showing per-email node progress and result previews. */
import { useEffect, useMemo, useState } from "react";

function formatDuration(durationMs) {
  if (durationMs == null) {
    return "";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(1)} s`;
}

export default function ExecutionPanel({ progress }) {
  const emailRuns = progress?.email_runs || [];
  const [selectedRunId, setSelectedRunId] = useState("");

  useEffect(() => {
    if (!emailRuns.length) {
      setSelectedRunId("");
      return;
    }

    const stillExists = emailRuns.some((run) => run.id === selectedRunId);
    if (stillExists) {
      return;
    }

    const runningRun = emailRuns.find((run) => run.status === "running");
    setSelectedRunId(runningRun?.id || emailRuns[emailRuns.length - 1]?.id || "");
  }, [emailRuns, selectedRunId]);

  const selectedRun = useMemo(
    () => emailRuns.find((run) => run.id === selectedRunId) || emailRuns[emailRuns.length - 1],
    [emailRuns, selectedRunId],
  );

  return (
    <section className="panel panel--execution">
      <div className="panel__header">
        <div>
          <h2>Live graph execution</h2>
          <p>
            Pick any message run to inspect every node execution, the returned state, and the
            delivery outcome in one place.
          </p>
        </div>
        <span className="pill">{emailRuns.length}</span>
      </div>

      {emailRuns.length === 0 ? (
        <div className="empty-state">
          No live execution yet. Start a run to watch node-by-node progress here.
        </div>
      ) : (
        <div className="execution-workspace">
          <div className="execution-sidebar">
            {emailRuns.map((emailRun) => (
              <article
                className={`execution-run-tile ${
                  emailRun.id === selectedRun?.id ? "execution-run-tile--selected" : ""
                }`}
                key={emailRun.id || emailRun.subject}
              >
                <div className="execution-run-tile__copy">
                  <span className="eyebrow">message</span>
                  <h3>{emailRun.subject}</h3>
                  <p>{emailRun.from_address || "Unknown sender"}</p>
                </div>
                <div className="execution-run-tile__meta">
                  <span className={`pill execution-pill execution-pill--${emailRun.status}`}>
                    {emailRun.status}
                  </span>
                  <button
                    className="button button--tiny button--ghost"
                    onClick={() => setSelectedRunId(emailRun.id)}
                  >
                    {emailRun.id === selectedRun?.id ? "Opened" : "Open"}
                  </button>
                </div>
              </article>
            ))}
          </div>

          {selectedRun ? (
            <div className="execution-detail">
              <div className="execution-card execution-card--detail">
                <div className="execution-card__header">
                  <div>
                    <span className="eyebrow">selected message</span>
                    <h3>{selectedRun.subject}</h3>
                    <p>{selectedRun.from_address || "Unknown sender"}</p>
                  </div>
                  <div className="execution-card__badges">
                    <span className={`pill execution-pill execution-pill--${selectedRun.status}`}>
                      {selectedRun.status}
                    </span>
                    {selectedRun.delivery_status ? (
                      <span className={`pill pill--${selectedRun.delivery_status}`}>
                        {selectedRun.delivery_status}
                      </span>
                    ) : null}
                    {selectedRun.final_action ? (
                      <span className="pill pill--soft">{selectedRun.final_action}</span>
                    ) : null}
                  </div>
                </div>

                <div className="execution-run-summary">
                  <div className="detail-card">
                    <h4>Run summary</h4>
                    <p>
                      {selectedRun.status === "running"
                        ? `Currently working on ${selectedRun.active_node || "the next node"}.`
                        : "Execution finished for this message."}
                    </p>
                  </div>
                  <div className="detail-card">
                    <h4>Received</h4>
                    <p>
                      {selectedRun.received_at
                        ? new Date(selectedRun.received_at).toLocaleString()
                        : "Unknown"}
                    </p>
                  </div>
                </div>

                <div className="node-step-list">
                  {(selectedRun.node_executions || []).map((node) => (
                    <div className={`node-step node-step--${node.status}`} key={node.node_name}>
                      <div className="node-step__header">
                        <div>
                          <strong>{node.node_name}</strong>
                          <p>{node.summary}</p>
                        </div>
                        <div className="node-step__meta">
                          <span className={`pill execution-pill execution-pill--${node.status}`}>
                            {node.status}
                          </span>
                          {node.duration_ms != null ? (
                            <span className="pill pill--soft">{formatDuration(node.duration_ms)}</span>
                          ) : null}
                        </div>
                      </div>
                      {node.result_preview ? (
                        <pre className="node-step__code">{node.result_preview}</pre>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

