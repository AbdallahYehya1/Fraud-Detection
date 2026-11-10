import { useEffect, useState } from "react";
import { api, type QueueItem } from "./api";
import { href, type Route } from "./App";
import { Card, ErrorNote, Loading, StatusPill, fmtAmount } from "./ui";

export function QueueView({ route }: { route: Extract<Route, { view: "queue" }> }) {
  const [runs, setRuns] = useState<string[]>([]);
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const run = route.run ?? runs[0];
  const day = route.day ?? "";
  const status = route.status ?? "";

  useEffect(() => { api.overview().then((o) => setRuns(o.runs.map((r) => r.run_id))).catch(setError); }, []);
  useEffect(() => { setOffset(0); }, [run, day, status]);
  useEffect(() => {
    if (!run) return;
    setItems(null);
    api.queue(run, status, day, offset).then((q) => { setItems(q.items); setTotal(q.total); }).catch(setError);
  }, [run, day, status, offset]);

  const go = (patch: Partial<{ run: string; day: string; status: string }>) => {
    location.hash = href({ view: "queue", run, day, status, ...patch });
  };

  if (error) return <ErrorNote error={error} />;
  return (
    <Card title="Alert queue" aside={<span className="muted small">{total} cases · ordered by day, then rank</span>}>
      <div className="filters">
        <label>Run
          <select value={run ?? ""} onChange={(e) => go({ run: e.target.value })}>
            {runs.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <label>Simulation day
          <input type="number" min={0} max={30} value={day} placeholder="all" onChange={(e) => go({ day: e.target.value })} />
        </label>
        <label>Status
          <select value={status} onChange={(e) => go({ status: e.target.value })}>
            <option value="">all</option>
            <option value="new">new</option>
            <option value="in_review">in review</option>
            <option value="escalated">escalated</option>
            <option value="closed">closed</option>
          </select>
        </label>
      </div>
      {!run ? <p className="muted">No replay runs yet.</p> : items === null ? <Loading /> : items.length === 0 ? (
        <p className="muted">No cases match these filters.</p>
      ) : (
        <>
          <table className="queue">
            <thead>
              <tr><th>Day</th><th className="num">Rank</th><th>Transaction</th><th className="num">Step</th><th>Type</th>
                  <th className="num">Amount (sim. units)</th><th className="num">Score</th><th>Recipient</th><th>Status</th></tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.case_id} className="clickable" onClick={() => { location.hash = href({ view: "case", id: c.case_id }); }}>
                  <td>{c.simulation_day}</td>
                  <td className="num">{c.rank} / {c.capacity}</td>
                  <td className="mono small"><a href={href({ view: "case", id: c.case_id })}>{c.event_id}</a></td>
                  <td className="num">{c.step}</td>
                  <td>{c.type}</td>
                  <td className="num">{fmtAmount(c.amount)}</td>
                  <td className="num">{c.score.toFixed(4)}</td>
                  <td className="small">{c.dest_has_prior ? "has earlier records" : <span className="tag">no earlier record</span>}</td>
                  <td><StatusPill status={c.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button className="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button>
            <span className="muted small">{offset + 1}–{Math.min(offset + 50, total)} of {total}</span>
            <button className="ghost" disabled={offset + 50 >= total} onClick={() => setOffset(offset + 50)}>Next</button>
          </div>
        </>
      )}
    </Card>
  );
}
