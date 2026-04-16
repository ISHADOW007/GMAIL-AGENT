/* Operational dashboard page that ties together stats, review actions, and detail views. */
import { startTransition, useEffect, useMemo, useState } from "react";

import ActivityFeed from "../components/ActivityFeed";
import DetailPanel from "../components/DetailPanel";
import EmailList from "../components/EmailList";
import HeroPanel from "../components/HeroPanel";
import ReviewQueuePanel from "../components/ReviewQueuePanel";
import StatCard from "../components/StatCard";
import StatusStrip from "../components/StatusStrip";
import { emptyDashboard, emptyProgress, getItemKey, requestJson } from "../lib/api";

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [progress, setProgress] = useState(emptyProgress);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [selectedItem, setSelectedItem] = useState(null);

  const activityFeed = useMemo(
    () => dashboard.last_run?.results?.slice(0, 6) ?? [],
    [dashboard.last_run],
  );

  const refreshDashboard = async () => {
    setError("");
    setLoading(true);
    try {
      const payload = await requestJson("/api/dashboard");
      startTransition(() => {
        setDashboard(payload);
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

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
    refreshDashboard();
    refreshProgress();
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      refreshProgress();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (selectedItem) {
      const allItems = [
        ...dashboard.review_items,
        ...dashboard.unread_emails,
        ...(dashboard.last_run?.results || []),
      ];
      const updatedSelection = allItems.find(
        (item) => getItemKey(item) === getItemKey(selectedItem),
      );
      if (updatedSelection) {
        setSelectedItem(updatedSelection);
        return;
      }
      return;
    }
    if (dashboard.review_items.length > 0) {
      setSelectedItem(dashboard.review_items[0]);
      return;
    }
    if (dashboard.unread_emails.length > 0) {
      setSelectedItem(dashboard.unread_emails[0]);
    }
  }, [dashboard, selectedItem]);

  const effectiveRunning = running || progress.status === "running";

  const runAgent = async () => {
    setRunning(true);
    setError("");
    try {
      await refreshProgress();
      await requestJson("/api/run", {
        method: "POST",
        body: JSON.stringify({}),
      });
      await refreshProgress();
      await refreshDashboard();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  };

  const reviewAction = async (reviewId, decision, comments) => {
    setError("");
    try {
      await requestJson(`/api/reviews/${reviewId}/${decision}`, {
        method: "POST",
        body: JSON.stringify({
          comments: comments || null,
          reviewer: "dashboard",
        }),
      });
      await refreshDashboard();
    } catch (requestError) {
      setError(requestError.message);
      throw requestError;
    }
  };

  return (
    <main className="app-shell">
      <HeroPanel
        loading={loading}
        running={effectiveRunning}
        progress={progress}
        onRefresh={refreshDashboard}
        onRun={runAgent}
      />

      <StatusStrip dashboard={dashboard} />

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="stats-grid">
        <StatCard label="Unread preview" value={dashboard.stats.unread_count} tone="sun" />
        <StatCard label="Human review" value={dashboard.stats.review_count} tone="coral" />
        <StatCard
          label="Processed last run"
          value={dashboard.stats.last_run_processed}
          tone="mint"
        />
      </section>

      <section className="content-grid">
        <div className="content-grid__left">
          <EmailList
            title="Unread radar"
            subtitle="Newest emails waiting for the next agent pass."
            items={dashboard.unread_emails}
            emptyMessage="Inbox is calm right now."
            onSelect={setSelectedItem}
            selectedKey={getItemKey(selectedItem)}
            renderMeta={(item) => (
              <>
                <span>{new Date(item.received_at).toLocaleString()}</span>
                <span className="pill pill--soft">{item.thread_id || "single"}</span>
              </>
            )}
          />

          <ReviewQueuePanel
            items={dashboard.review_items}
            onAction={reviewAction}
            onSelect={setSelectedItem}
            selectedKey={getItemKey(selectedItem)}
          />
        </div>

        <div className="content-grid__right">
          <ActivityFeed
            lastRun={dashboard.last_run}
            items={activityFeed}
            onSelect={setSelectedItem}
            selectedKey={getItemKey(selectedItem)}
          />

          <DetailPanel item={selectedItem} />
        </div>
      </section>
    </main>
  );
}

