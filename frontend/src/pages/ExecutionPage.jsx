/* Page dedicated to live node-by-node execution visibility. */
import { startTransition, useEffect, useState } from "react";

import ExecutionPanel from "../components/ExecutionPanel";
import { emptyProgress, requestJson } from "../lib/api";

export default function ExecutionPage() {
  const [progress, setProgress] = useState(emptyProgress);
  const [error, setError] = useState("");

  const refreshProgress = async () => {
    try {
      const payload = await requestJson("/api/progress");
      startTransition(() => {
        setProgress(payload);
      });
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  useEffect(() => {
    refreshProgress();
    const intervalId = window.setInterval(() => {
      refreshProgress();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, []);

  return (
    <main className="app-shell">
      <section className="hero hero--compact">
        <div className="hero__copy">
          <span className="eyebrow">Execution explorer</span>
          <h1>Node-by-node AI run viewer</h1>
          <p>
            Open each processed message and inspect the exact LangGraph nodes, status changes,
            and returned state diffs as the agent works.
          </p>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <ExecutionPanel progress={progress} />
    </main>
  );
}

