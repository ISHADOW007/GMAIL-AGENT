import { getItemKey } from "../lib/api";

export default function ActivityFeed({ lastRun, items, onSelect, selectedKey }) {
  return (
    <section className="panel panel--activity">
      <div className="panel__header">
        <div>
          <h2>Last run activity</h2>
          <p>
            {lastRun?.ran_at
              ? `Most recent execution at ${new Date(lastRun.ran_at).toLocaleString()}`
              : "Run the agent to populate live activity here."}
          </p>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">No recent execution results yet.</div>
      ) : (
        <div className="activity-list">
          {items.map((item) => (
            <article
              className={`activity-card ${selectedKey === getItemKey(item) ? "activity-card--selected" : ""}`}
              key={getItemKey(item)}
              onClick={() => onSelect?.(item)}
              role={onSelect ? "button" : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onKeyDown={(event) => {
                if (!onSelect) {
                  return;
                }
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(item);
                }
              }}
            >
              <div className="activity-card__top">
                <h3>{item.subject}</h3>
                <span className={`pill pill--${item.delivery_status}`}>
                  {item.delivery_status}
                </span>
              </div>
              <p>{item.reason}</p>
              <div className="activity-card__meta">
                <span>{item.intent}</span>
                <span>{item.urgency}</span>
                <span>{item.risk}</span>
                <span>{item.action}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
