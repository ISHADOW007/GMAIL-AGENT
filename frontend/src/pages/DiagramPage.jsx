const CORE_FLOW = [
  "Fetch unread emails",
  "Normalize email",
  "Load thread history",
  "Load memory",
  "Classify intent, urgency, risk",
];

const BRANCHES = [
  {
    title: "Ignore lane",
    tone: "coral",
    steps: ["Route to ignore_email", "Update memory", "Mark processed"],
  },
  {
    title: "Draft lane",
    tone: "sea",
    steps: ["Retrieve context", "Draft reply", "Safety check", "Update memory", "Mark processed"],
  },
  {
    title: "Human review lane",
    tone: "mint",
    steps: ["Queue human review", "Approve / revise / reject", "Resume if approved", "Update memory", "Mark processed"],
  },
];

const SYSTEM_FLOW = [
  {
    title: "Frontend",
    text: "React dashboard starts runs, shows node progress, review queue, and execution details.",
  },
  {
    title: "FastAPI API",
    text: "Receives run requests, dashboard requests, progress polling, and review actions.",
  },
  {
    title: "LangGraph workflow",
    text: "Runs the node-based state machine for each email and controls branching decisions.",
  },
  {
    title: "Mailbox layer",
    text: "Talks to Gmail, local JSON, or IMAP/SMTP for fetch, send, draft, labels, and processed state.",
  },
  {
    title: "Memory and review stores",
    text: "Persist contact/thread memory, run results, review records, and resumable state snapshots.",
  },
];

function FlowBox({ children, tone = "neutral", diamond = false }) {
  return (
    <div
      className={`diagram-box diagram-box--${tone} ${diamond ? "diagram-box--diamond" : ""}`}
    >
      <span>{children}</span>
    </div>
  );
}

export default function DiagramPage() {
  return (
    <main className="app-shell">
      <section className="hero hero--compact">
        <div className="hero__copy">
          <span className="eyebrow">Full diagram</span>
          <h1>Complete project flowchart</h1>
          <p>
            This page isolates the full project execution diagram so you can walk through the
            system visually during demos, documentation, and interviews.
          </p>
        </div>
      </section>

      <section className="panel panel--flow">
        <div className="panel__header">
          <div>
            <h2>System-level flow</h2>
            <p>How the main layers of the product connect end to end.</p>
          </div>
        </div>
        <div className="system-diagram">
          {SYSTEM_FLOW.map((item, index) => (
            <div className="system-diagram__item" key={item.title}>
              <FlowBox tone="neutral">{item.title}</FlowBox>
              <p>{item.text}</p>
              {index < SYSTEM_FLOW.length - 1 ? (
                <div className="diagram-arrow diagram-arrow--horizontal" aria-hidden="true">
                  →
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="panel panel--flow">
        <div className="panel__header">
          <div>
            <h2>Email execution flowchart</h2>
            <p>
              The full node-level path from inbox fetch to final completion. The graph has three
              top-level routes only: ignore, draft, and human review.
            </p>
          </div>
        </div>

        <div className="flowchart-page">
          <div className="flowchart-page__center">
            <FlowBox tone="neutral">START</FlowBox>
            <div className="diagram-arrow">↓</div>
            {CORE_FLOW.map((step) => (
              <div className="flowchart-page__stack-item" key={step}>
                <FlowBox tone="neutral">{step}</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
            ))}
            <FlowBox tone="sun" diamond>
              Route decision
            </FlowBox>
          </div>

          <div className="flowchart-branches">
            <section className="flowchart-lane flowchart-lane--coral">
              <div className="flowchart-lane__header">
                <h3>Ignore lane</h3>
              </div>
              <div className="diagram-arrow">↓</div>
              {BRANCHES[0].steps.map((step, index) => (
                <div className="flowchart-lane__step" key={step}>
                  <FlowBox tone="coral">{step}</FlowBox>
                  {index < BRANCHES[0].steps.length - 1 ? (
                    <div className="diagram-arrow">↓</div>
                  ) : null}
                </div>
              ))}
            </section>

            <section className="flowchart-lane flowchart-lane--sea">
              <div className="flowchart-lane__header">
                <h3>Draft lane</h3>
              </div>
              <div className="diagram-arrow">↓</div>
              <div className="flowchart-lane__step">
                <FlowBox tone="sea">Retrieve context</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="sea">Draft reply</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="sea">Safety check</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>

              <div className="delivery-branch">
                <FlowBox tone="sun" diamond>
                  Delivery decision
                </FlowBox>
                <div className="delivery-branch__fanout">
                  <div className="delivery-branch__path">
                    <span className="delivery-branch__label">AUTO_SEND=true and safe</span>
                    <div className="diagram-arrow">↓</div>
                    <FlowBox tone="sea">Auto send</FlowBox>
                  </div>
                  <div className="delivery-branch__path">
                    <span className="delivery-branch__label">Otherwise</span>
                    <div className="diagram-arrow">↓</div>
                    <FlowBox tone="sea">Save draft</FlowBox>
                  </div>
                </div>
                <div className="diagram-arrow">↓</div>
              </div>

              <div className="flowchart-lane__step">
                <FlowBox tone="sea">Update memory</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="sea">Mark processed</FlowBox>
              </div>
            </section>

            <section className="flowchart-lane flowchart-lane--mint">
              <div className="flowchart-lane__header">
                <h3>Human review lane</h3>
              </div>
              <div className="diagram-arrow">↓</div>
              <div className="flowchart-lane__step">
                <FlowBox tone="mint">Queue human review</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="mint">Approve / revise / reject</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="mint">Resume if approved</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>

              <div className="delivery-branch">
                <FlowBox tone="sun" diamond>
                  Delivery decision
                </FlowBox>
                <div className="delivery-branch__fanout">
                  <div className="delivery-branch__path">
                    <span className="delivery-branch__label">AUTO_SEND=true and safe</span>
                    <div className="diagram-arrow">↓</div>
                    <FlowBox tone="mint">Auto send</FlowBox>
                  </div>
                  <div className="delivery-branch__path">
                    <span className="delivery-branch__label">Otherwise</span>
                    <div className="diagram-arrow">↓</div>
                    <FlowBox tone="mint">Save draft</FlowBox>
                  </div>
                </div>
                <div className="diagram-arrow">↓</div>
              </div>

              <div className="flowchart-lane__step">
                <FlowBox tone="mint">Update memory</FlowBox>
                <div className="diagram-arrow">↓</div>
              </div>
              <div className="flowchart-lane__step">
                <FlowBox tone="mint">Mark processed</FlowBox>
              </div>
            </section>
          </div>

          <div className="flowchart-page__center flowchart-page__center--end">
            <FlowBox tone="mint">END</FlowBox>
          </div>
        </div>
      </section>

      <section className="flow-grid">
        <section className="panel panel--flow">
          <div className="panel__header">
            <div>
              <h2>Reasoning behind branches</h2>
              <p>Why the workflow separates into different lanes.</p>
            </div>
          </div>
          <div className="route-card-list">
            <article className="route-card route-card--coral">
              <h3>Ignore lane</h3>
              <p>
                Used for newsletters, spam, and any email explicitly marked as ignore so the agent
                never drafts or sends an unnecessary reply.
              </p>
            </article>
            <article className="route-card route-card--sea">
              <h3>Draft lane</h3>
              <p>
                This is one top-level route. Inside it, send_or_save chooses between auto send and
                save draft based on AUTO_SEND and safe_to_send.
              </p>
            </article>
            <article className="route-card route-card--mint">
              <h3>Human review lane</h3>
              <p>
                Used for low-confidence, VIP, or sensitive emails where the graph pauses and asks
                for human approval or revision before continuing into the same send_or_save gate.
              </p>
            </article>
          </div>
        </section>

        <section className="panel panel--flow">
          <div className="panel__header">
            <div>
              <h2>Interview line</h2>
              <p>A concise explanation you can say while showing the page.</p>
            </div>
          </div>
          <div className="detail-panel">
            <div className="detail-card">
              <h4>Suggested explanation</h4>
              <p>
                Every email enters through a shared preparation pipeline, then LangGraph routes it
                into one of three top-level branches: ignore, draft, or human review. Auto send is
                not its own branch. It is one possible outcome inside the draft branch before the
                workflow rejoins for memory update and processed-state handling.
              </p>
            </div>
            <div className="detail-card">
              <h4>send_or_save node</h4>
              <p>
                This node is the final delivery checkpoint. It refuses ignored messages, sends only
                when AUTO_SEND is enabled and the safety node marked the draft as safe, and saves a
                draft in all other normal reply cases.
              </p>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
