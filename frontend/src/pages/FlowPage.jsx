/* Explanation-focused page describing how the workflow behaves conceptually. */
const FLOW_STEPS = [
  {
    id: "fetch",
    title: "1. Fetch unread emails",
    reason:
      "The mailbox layer pulls unread messages from Gmail and normalizes the provider response before the graph starts.",
    outputs: ["email.id", "thread_id", "subject", "body", "received_at"],
  },
  {
    id: "normalize",
    title: "2. Normalize email",
    reason:
      "The agent cleans body text, standardizes sender and thread fields, and prepares a consistent state object for later nodes.",
    outputs: ["normalized_email", "email_id", "thread_id"],
  },
  {
    id: "thread",
    title: "3. Load thread history",
    reason:
      "Previous messages in the same thread are loaded so the model can avoid repeating answers and can understand follow-up context.",
    outputs: ["thread_messages", "thread_summary"],
  },
  {
    id: "memory",
    title: "4. Load memory",
    reason:
      "Mongo-backed contact and thread memory gives the classifier and drafter extra context such as VIP status, prior summaries, and known facts.",
    outputs: ["memory.contact", "memory.thread", "memory.business_facts"],
  },
  {
    id: "classify",
    title: "5. Classify intent, urgency, risk",
    reason:
      "The classifier decides what the message is about and what the safest next action is. Low confidence or VIP rules can force human review.",
    outputs: ["classification.intent", "classification.action", "classification.risk"],
  },
  {
    id: "route",
    title: "6. Route by action",
    reason:
      "This is the top-level routing split. The graph chooses one of three branches only: ignore, draft, or human review. Auto-send is not its own branch. It is a delivery outcome inside the draft branch.",
    outputs: ["ignore path", "draft path", "human review path"],
  },
  {
    id: "context",
    title: "7. Retrieve context",
    reason:
      "For replyable emails, the graph collects grounded context before drafting so responses are based on memory, thread state, and business facts.",
    outputs: ["retrieved_context"],
  },
  {
    id: "draft",
    title: "8. Draft reply",
    reason:
      "The model produces a structured reply draft using the normalized email, thread history, and retrieved context.",
    outputs: ["draft.subject", "draft.body"],
  },
  {
    id: "safety",
    title: "9. Safety check",
    reason:
      "A rule-based safety gate blocks risky replies and sends uncertain messages to human review before delivery can happen.",
    outputs: ["safety_result.safe_to_send", "safety_result.needs_human"],
  },
  {
    id: "review",
    title: "10. Human review",
    reason:
      "Sensitive or uncertain emails are paused with a saved state snapshot so a reviewer can approve, revise, or reject them later.",
    outputs: ["review_id", "human_decision", "state_snapshot"],
  },
  {
    id: "deliver",
    title: "11. Send or save",
    reason:
      "This node is the final delivery gate. It first blocks anything whose final action or classification says ignore. Then it checks the safety result and the AUTO_SEND setting. If AUTO_SEND=true and safety says safe_to_send, it sends the reply through the mailbox backend. Otherwise it saves a draft so a human can review it before sending.",
    outputs: [
      "final_action ignore => delivery blocked",
      "AUTO_SEND + safe_to_send => send_email()",
      "otherwise => save_draft()",
      "delivery_status",
      "final_action",
    ],
  },
  {
    id: "persist",
    title: "12. Update memory and mark processed",
    reason:
      "The run result is persisted, the unread flag is cleared, and Gmail labels such as AI-Sent or AI-Ignored can be applied for auditability.",
    outputs: ["memory updates", "processed mailbox state"],
  },
];

const ROUTE_CASES = [
  {
    title: "Ignore path",
    tone: "coral",
    reason:
      "Newsletters, spam, and anything classified with action=ignore go straight to ignore_email, then update_memory, then mark_processed.",
  },
  {
    title: "Draft path",
    tone: "sea",
    reason:
      "Normal low-risk emails continue through retrieve_context, draft_reply, and safety_check. Inside this branch, the send_or_save node then decides between auto send and save draft.",
  },
  {
    title: "Human review path",
    tone: "mint",
    reason:
      "Low confidence, VIP senders, safety failures, and sensitive topics route to human_review where the workflow can pause and resume.",
  },
];

const BRANCH_COLUMNS = [
  {
    title: "Ignore path",
    tone: "coral",
    nodes: ["ignore_email", "update_memory", "mark_processed"],
    note: "Used for newsletters, spam, and any message explicitly classified with action=ignore.",
  },
  {
    title: "Draft path",
    tone: "sea",
    nodes: [
      "retrieve_context",
      "draft_reply",
      "safety_check",
      "send_or_save",
      "delivery outcome: auto send or save draft",
      "update_memory",
      "mark_processed",
    ],
    note: "Used for normal low-risk emails. This is one branch, and inside it the delivery gate chooses auto send or save draft.",
  },
  {
    title: "Human review path",
    tone: "mint",
    nodes: ["human_review", "revise_reply", "send_or_save", "update_memory", "mark_processed"],
    note: "Used for low-confidence, VIP, or policy-sensitive messages that need a person in the loop.",
  },
];

const ARCHITECTURE_BLOCKS = [
  {
    title: "Mailbox layer",
    text: "Handles Gmail transport, threading, drafting, sending, labels, and review queue handoff.",
  },
  {
    title: "LangGraph workflow",
    text: "Runs the state machine of nodes and conditional edges that decide how each email is processed.",
  },
  {
    title: "Memory layer",
    text: "Stores contacts, threads, review records, and reusable context that improve future runs.",
  },
  {
    title: "FastAPI backend",
    text: "Exposes dashboard, review, and progress APIs for the frontend and any external control surface.",
  },
  {
    title: "React frontend",
    text: "Provides the operator-facing dashboard, execution page, detail panels, and review controls.",
  },
];

export default function FlowPage() {
  return (
    <main className="app-shell">
      <section className="hero hero--compact">
        <div className="hero__copy">
          <span className="eyebrow">System flow</span>
          <h1>Complete execution diagram with reasoning</h1>
          <p>
            This page explains the full project flow from inbox fetch through LangGraph routing,
            review, delivery, and memory updates. It is designed to help you demo the product and
            explain the codebase in interviews.
          </p>
        </div>
      </section>

      <section className="panel panel--flow">
        <div className="panel__header">
          <div>
            <h2>Architecture map</h2>
            <p>How the major layers of the project connect during a run.</p>
          </div>
        </div>
        <div className="architecture-strip">
          {ARCHITECTURE_BLOCKS.map((block, index) => (
            <div className="architecture-block" key={block.title}>
              <h3>{block.title}</h3>
              <p>{block.text}</p>
              {index < ARCHITECTURE_BLOCKS.length - 1 ? (
                <span className="architecture-arrow" aria-hidden="true">
                  â†’
                </span>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="panel panel--flow">
        <div className="panel__header">
          <div>
            <h2>Execution flow</h2>
            <p>Step-by-step node flow with the reason each stage exists.</p>
          </div>
        </div>
        <div className="flow-timeline">
          {FLOW_STEPS.map((step, index) => (
            <article className="flow-step" key={step.id}>
              <div className="flow-step__index">{index + 1}</div>
              <div className="flow-step__content">
                <h3>{step.title}</h3>
                <p>{step.reason}</p>
                <div className="detail-tags">
                  {step.outputs.map((output) => (
                    <span className="pill pill--soft" key={output}>
                      {output}
                    </span>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel panel--flow">
        <div className="panel__header">
          <div>
            <h2>Branch diagram</h2>
            <p>How the project splits after classification and rejoins before completion.</p>
          </div>
        </div>
        <div className="branch-diagram">
          <div className="branch-diagram__spine">
            <div className="branch-spine-card">
              <span className="eyebrow">shared spine</span>
              <h3>{"fetch -> normalize -> load_thread -> load_memory -> classify_email"}</h3>
              <p>
                Every message starts through the same preparation and classification flow before
                the graph chooses one of the only three top-level branches: ignore, draft, or
                human review.
              </p>
            </div>
          </div>
          <div className="branch-diagram__columns">
            {BRANCH_COLUMNS.map((branch) => (
              <article className={`branch-column branch-column--${branch.tone}`} key={branch.title}>
                <div className="branch-column__header">
                  <h3>{branch.title}</h3>
                  <p>{branch.note}</p>
                </div>
                <div className="branch-node-list">
                  {branch.nodes.map((nodeName, index) => (
                    <div className="branch-node" key={nodeName}>
                      <span className="pill pill--soft">{nodeName}</span>
                      {index < branch.nodes.length - 1 ? (
                        <span className="branch-node__arrow" aria-hidden="true">
                          â†“
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
          <div className="branch-diagram__spine">
            <div className="branch-spine-card">
              <span className="eyebrow">shared finish</span>
              <h3>{"memory update -> processed mailbox -> dashboard visibility"}</h3>
              <p>
                Regardless of branch, the result is persisted, the mailbox is updated, and the
                operator can inspect it in the UI.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="flow-grid">
        <section className="panel panel--flow">
          <div className="panel__header">
            <div>
              <h2>Routing reasoning</h2>
              <p>Why the graph branches the way it does.</p>
            </div>
          </div>
          <div className="route-card-list">
            {ROUTE_CASES.map((route) => (
              <article className={`route-card route-card--${route.tone}`} key={route.title}>
                <h3>{route.title}</h3>
                <p>{route.reason}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel--flow">
          <div className="panel__header">
            <div>
              <h2>Interview summary</h2>
              <p>A short way to explain the project flow clearly.</p>
            </div>
          </div>
          <div className="detail-panel">
            <div className="detail-card">
              <h4>30 second version</h4>
              <p>
                The mailbox layer fetches unread Gmail messages, LangGraph runs a stateful email
                workflow, memory and thread history add context, the classifier decides the safest
                branch, and then the flow goes into one of three top-level routes: ignore, draft,
                or human review. Inside the draft route, send_or_save decides whether to auto send
                or save a draft. The final result is then persisted and surfaced in the dashboard.
              </p>
            </div>
            <div className="detail-card">
              <h4>Why this design</h4>
              <p>
                I separated transport, workflow, memory, API, and UI so the agent is easier to
                test, safer to operate, and simpler to extend with live execution tracing and
                review resume behavior.
              </p>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

