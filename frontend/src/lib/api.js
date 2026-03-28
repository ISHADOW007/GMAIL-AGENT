export const emptyDashboard = {
  backend: "unknown",
  auto_send: false,
  gmail_mode: false,
  mongodb_enabled: false,
  stats: {
    unread_count: 0,
    outbox_count: 0,
    review_count: 0,
    last_run_processed: 0,
  },
  unread_emails: [],
  outbox_items: [],
  review_items: [],
  last_run: { results: [] },
};

export const emptyProgress = {
  status: "idle",
  backend: null,
  total_emails: 0,
  processed_count: 0,
  percent_complete: 0,
  current_email: null,
  email_runs: [],
  recent_results: [],
  started_at: null,
  updated_at: null,
  error_message: null,
};

export function getItemKey(item) {
  return item?.review_id || item?.id || item?.email_id || item?.subject || "item";
}

export async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}
