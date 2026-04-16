/* Compact status summary component for backend mode and runtime flags. */
export default function StatusStrip({ dashboard }) {
  return (
    <section className="status-strip">
      <div className="status-chip">
        <span>Backend</span>
        <strong>{dashboard.backend}</strong>
      </div>
      <div className="status-chip">
        <span>Auto send</span>
        <strong>{dashboard.auto_send ? "Enabled" : "Draft-first"}</strong>
      </div>
      <div className="status-chip">
        <span>Memory</span>
        <strong>{dashboard.mongodb_enabled ? "Mongo on" : "Mongo off"}</strong>
      </div>
      <div className="status-chip">
        <span>Provider</span>
        <strong>Gmail only</strong>
      </div>
    </section>
  );
}

