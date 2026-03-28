import { useEffect, useState } from "react";

import DashboardPage from "./pages/DashboardPage";
import DiagramPage from "./pages/DiagramPage";
import ExecutionPage from "./pages/ExecutionPage";
import FlowPage from "./pages/FlowPage";

function getRouteFromHash() {
  const route = window.location.hash.replace("#/", "");
  if (route === "execution") {
    return "execution";
  }
  if (route === "flow") {
    return "flow";
  }
  if (route === "diagram") {
    return "diagram";
  }
  return "dashboard";
}

export default function App() {
  const [route, setRoute] = useState(getRouteFromHash);

  useEffect(() => {
    const handleHashChange = () => setRoute(getRouteFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return (
    <div>
      <header className="top-nav">
        <div className="top-nav__brand">
          <span className="eyebrow">Email agent</span>
          <strong>Ops Console</strong>
        </div>
        <nav className="top-nav__links" aria-label="Primary">
          <a
            className={`top-nav__link ${route === "dashboard" ? "top-nav__link--active" : ""}`}
            href="#/dashboard"
          >
            Dashboard
          </a>
          <a
            className={`top-nav__link ${route === "execution" ? "top-nav__link--active" : ""}`}
            href="#/execution"
          >
            Execution
          </a>
          <a
            className={`top-nav__link ${route === "flow" ? "top-nav__link--active" : ""}`}
            href="#/flow"
          >
            Flow
          </a>
          <a
            className={`top-nav__link ${route === "diagram" ? "top-nav__link--active" : ""}`}
            href="#/diagram"
          >
            Diagram
          </a>
        </nav>
      </header>

      {route === "execution" ? (
        <ExecutionPage />
      ) : route === "diagram" ? (
        <DiagramPage />
      ) : route === "flow" ? (
        <FlowPage />
      ) : (
        <DashboardPage />
      )}
    </div>
  );
}
