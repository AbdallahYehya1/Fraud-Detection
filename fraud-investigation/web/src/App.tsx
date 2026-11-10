import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import { CaseView } from "./CaseView";
import { OverviewView } from "./Overview";
import { QueueView } from "./Queue";

export type Route =
  | { view: "overview" }
  | { view: "queue"; run?: string; day?: string; status?: string }
  | { view: "case"; id: string };

function parse(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const q = new URLSearchParams(query);
  if (path.startsWith("case/")) return { view: "case", id: decodeURIComponent(path.slice(5)) };
  if (path === "queue") return { view: "queue", run: q.get("run") ?? undefined, day: q.get("day") ?? undefined, status: q.get("status") ?? undefined };
  return { view: "overview" };
}

export function href(r: Route): string {
  if (r.view === "case") return `#/case/${encodeURIComponent(r.id)}`;
  if (r.view === "queue") {
    const q = new URLSearchParams();
    if (r.run) q.set("run", r.run);
    if (r.day) q.set("day", r.day);
    if (r.status) q.set("status", r.status);
    const s = q.toString();
    return `#/queue${s ? `?${s}` : ""}`;
  }
  return "#/overview";
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(location.hash));
  const [analyst, setAnalyst] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (getToken()) api.me().then((m) => setAnalyst(m.display_name)).catch(() => setToken(null));
  }, []);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setToken(tokenInput.trim());
    try {
      const m = await api.me();
      setAnalyst(m.display_name);
      setTokenInput("");
      setAuthError(null);
    } catch {
      setToken(null);
      setAuthError("Token not recognised");
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden>◆</span>
          <div>
            <strong>Fraud Review Workbench</strong>
            <span className="muted small">Synthetic PaySim v2 · local demo</span>
          </div>
        </div>
        <nav>
          <a className={route.view === "overview" ? "active" : ""} href="#/overview">Overview</a>
          <a className={route.view !== "overview" ? "active" : ""} href={href({ view: "queue" })}>Queue</a>
        </nav>
        <div className="auth">
          {analyst ? (
            <>
              <span className="small">Signed in as <strong>{analyst}</strong></span>
              <button className="ghost" onClick={() => { setToken(null); setAnalyst(null); }}>Sign out</button>
            </>
          ) : (
            <form onSubmit={signIn} className="signin">
              <input type="password" placeholder="Analyst token" value={tokenInput}
                     onChange={(e) => setTokenInput(e.target.value)} aria-label="Analyst token" />
              <button type="submit" disabled={!tokenInput.trim()}>Sign in</button>
              {authError && <span className="error small">{authError}</span>}
            </form>
          )}
        </div>
      </header>
      <main>
        {route.view === "overview" && <OverviewView />}
        {route.view === "queue" && <QueueView route={route} />}
        {route.view === "case" && <CaseView id={route.id} signedIn={analyst !== null} />}
      </main>
      <footer className="muted small">
        Synthetic data (CC BY-SA 4.0, Lopez-Rojas et al., 2016). Amounts are simulation currency units; steps are relative
        hours. Scores rank transactions for review; they do not establish fraud.
      </footer>
    </div>
  );
}
