import { getItemKey } from "../lib/api";

export default function EmailList({
  title,
  subtitle,
  items,
  emptyMessage,
  renderMeta,
  onSelect,
  selectedKey,
}) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <span className="pill">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">{emptyMessage}</div>
      ) : (
        <div className="list">
          {items.map((item) => (
            <article
              className={`list-item ${
                selectedKey === getItemKey(item) ? "list-item--selected" : ""
              }`}
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
              <div className="list-item__main">
                <h3>{item.subject}</h3>
                <p>{item.from_address || item.to_address || "Unknown sender"}</p>
              </div>
              <div className="list-item__meta">{renderMeta(item)}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
