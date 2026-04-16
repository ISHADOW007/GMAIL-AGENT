/* Frontend API helpers and shared empty-state structures. */
export const emptyDashboard = {
  backend: "gmail",
  auto_send: false,
  mongodb_enabled: false,
  stats: {
    unread_count: 0,
    review_count: 0,
    last_run_processed: 0,
  },
  unread_emails: [],
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
    const raw = await response.text();
    let message = raw || `Request failed: ${response.status}`;
    try {
      const parsed = JSON.parse(raw);
      if (parsed?.detail) {
        message = parsed.detail;
      }
    } catch {
      // Keep the raw text when the backend response is not JSON.
    }
    throw new Error(message);
  }

  return response.json();
}

