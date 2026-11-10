import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type CaseStatus, type Disposition, type Evidence, type RecordSet } from "./api";
import { href } from "./App";
import { AssistantPanel } from "./AssistantPanel";
import { Card, ErrorNote, Loading, StatusPill, fmtAmount, label } from "./ui";

const NEXT: Record<CaseStatus, CaseStatus[]> = {
  new: ["in_review"], in_review: ["escalated", "closed", "new"], escalated: ["in_review", "closed"], closed: [],
};
const ACTION_LABEL: Record<CaseStatus, string> = {
  in_review: "Start review", escalated: "Escalate", closed: "Close with disposition", new: "Release to queue",
};
const DISPOSITIONS: Disposition[] = ["needs_more_information", "suspicious_in_demo", "no_action"];

function Records({ title, set, empty }: { title: string; set: RecordSet; empty: string }) {
  return (
    <div className="records">
      <h3>{title} <span className="muted small">steps {set.steps[0]}–{set.steps[1]} · {set.count} record(s)
        {set.count > 0 && ` · total ${fmtAmount(set.amount_sum)}`}</span></h3>
      {set.count === 0 ? <p className="empty">{empty}</p> : (
        <table className="compact">
          <thead><tr><th className="num">Step</th><th>Type</th><th className="num">Amount</th><th>Sender</th><th>Recipient</th><th>Source</th></tr></thead>
          <tbody>
            {set.records.map((r) => (
              <tr key={r.event_id}>
                <td className="num">{r.step}</td><td>{r.type}</td><td className="num">{fmtAmount(r.amount)}</td>
                <td className="mono small">{r.name_orig}</td><td className="mono small">{r.name_dest}</td>
                <td className="mono small">{r.event_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {set.shown < set.count && <p className="muted small">Showing the latest {set.shown} of {set.count}.</p>}
    </div>
  );
}

export function CaseView({ id, signedIn }: { id: string; signedIn: boolean }) {
  const [ev, setEv] = useState<Evidence | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [disposition, setDisposition] = useState<Disposition | "">("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.evidence(id).then((e) => { setEv(e); setError(null); }).catch(setError), [id]);
  useEffect(() => { setEv(null); load(); }, [load]);

  async function act(target: CaseStatus) {
    if (!ev) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.transition(id, {
        expected_version: ev.case.version, status: target,
        ...(target === "closed" && disposition ? { disposition } : {}),
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      setNote("");
      setDisposition("");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && "current_version" in e.body) {
        setActionError(`${e.message} (now version ${String(e.body.current_version)}, status ${String(e.body.current_status)}). Reloaded.`);
        await load();
      } else {
        setActionError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  async function addNote() {
    setBusy(true);
    setActionError(null);
    try {
      await api.addNote(id, note.trim());
      setNote("");
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorNote error={error} />;
  if (!ev) return <Loading />;
  const c = ev.case, t = ev.transaction, m = ev.model_evidence, f = m.score_time_features;

  return (
    <div className="stack">
      <div className="case-head">
        <a href={href({ view: "queue", run: c.run_id, day: String(m.simulation_day) })} className="small">← Queue, day {m.simulation_day}</a>
        <h1>Case {c.case_id.split("/").slice(-2).join(" · ")}</h1>
        <div className="case-meta">
          <StatusPill status={c.status} />
          {c.disposition && <span className="tag">{label(c.disposition)}</span>}
          <span className="muted small">version {c.version}{c.assigned_to && ` · ${c.assigned_to}`}</span>
          <span className="muted small">scored at step {c.scoring_step} · evidence cutoff step {c.case_evidence_cutoff_step}</span>
        </div>
      </div>

      <div className="grid-2">
        <Card title="Transaction">
          <dl className="kv">
            <dt>Event</dt><dd className="mono">{t.event_id}</dd>
            <dt>Type</dt><dd>{t.type}</dd>
            <dt>Amount</dt><dd>{fmtAmount(t.amount)} <span className="muted">{t.unit}</span></dd>
            <dt>Step</dt><dd>{t.step} (day {m.simulation_day})</dd>
            <dt>Sender</dt><dd className="mono">{t.name_orig}</dd>
            <dt>Recipient</dt><dd className="mono">{t.name_dest}</dd>
            <dt>Source row</dt><dd className="mono">{t.source_row}</dd>
          </dl>
          <p className="muted small">Project event ID derived from the dataset hash and source row — not a bank transaction ID.</p>
        </Card>
        <Card title="Model evidence" aside={<span className="badge">association, not proof</span>}>
          <div className="score-line">
            <span className="score">{m.score.toFixed(4)}</span>
            <span className="muted small">rank {m.rank} of {m.capacity} · {m.model_version} · {m.policy_version}</span>
          </div>
          <table className="compact">
            <tbody>
              <tr><td>Recipient has earlier record</td><td className="num">{f.dest_has_prior ? "yes" : "no"}</td></tr>
              <tr><td>Earlier recipient records</td><td className="num">{Number(f.dest_prior_count)}</td></tr>
              <tr><td>Earlier recipient total</td><td className="num">{fmtAmount(String(f.dest_prior_amount_sum ?? 0))}</td></tr>
              <tr><td>Recipient records, previous 24 steps</td><td className="num">{Number(f.dest_prior_count_24h)}</td></tr>
              <tr><td>Steps since recipient's last record</td><td className="num">{f.dest_steps_since_last ?? "missing (none)"}</td></tr>
            </tbody>
          </table>
          <p className="muted small">{m.semantics}</p>
        </Card>
      </div>

      <Card title="Computed facts">
        <ul className="facts">
          {ev.computed_facts.map((x) => <li key={x.id}><span className="fact-id">{x.id}</span>{x.fact} <span className="muted small">[{x.source}]</span></li>)}
        </ul>
        <h3>Missing information</h3>
        <ul className="missing">{ev.missing_information.map((x) => <li key={x}>{x}</li>)}</ul>
      </Card>

      <AssistantPanel caseId={c.case_id} signedIn={signedIn} />

      <Card title="Recipient history" aside={<span className="muted small">same role only</span>}>
        <Records title="Before scoring (eligible for the score)" set={ev.recipient_history.score_time}
                 empty="No earlier records available in this dataset." />
        <Records title="After scoring, up to the evidence cutoff (review-time only)" set={ev.recipient_history.review_time}
                 empty="No further records up to the evidence cutoff." />
        <p className="muted small">{ev.recipient_history.note}</p>
      </Card>

      <Card title="Sender history">
        <Records title="Before scoring" set={ev.sender_history.score_time} empty="No earlier records available in this dataset." />
        <Records title="After scoring, up to the evidence cutoff (review-time only)" set={ev.sender_history.review_time}
                 empty="No further records up to the evidence cutoff." />
      </Card>

      <div className="grid-2">
        <Card title="Review action">
          {!signedIn ? <p className="muted">Sign in with an analyst token to act on this case.</p> : (
            <div className="actions">
              <textarea placeholder="Analyst note (optional for a status change)" value={note} maxLength={4000}
                        onChange={(e) => setNote(e.target.value)} rows={3} />
              {NEXT[c.status].includes("closed") && (
                <label className="small">Disposition (required to close)
                  <select value={disposition} onChange={(e) => setDisposition(e.target.value as Disposition | "")}>
                    <option value="">choose…</option>
                    {DISPOSITIONS.map((d) => <option key={d} value={d}>{label(d)}</option>)}
                  </select>
                </label>
              )}
              <div className="buttons">
                {NEXT[c.status].map((s) => (
                  <button key={s} disabled={busy || (s === "closed" && !disposition)}
                          className={s === "closed" ? "primary" : ""} onClick={() => act(s)}>{ACTION_LABEL[s]}</button>
                ))}
                <button className="ghost" disabled={busy || !note.trim()} onClick={addNote}>Add note only</button>
              </div>
              {c.status === "closed" && <p className="muted small">Closed cases cannot be reopened in this demo.</p>}
              {actionError && <p className="error" role="alert">{actionError}</p>}
            </div>
          )}
        </Card>
        <Card title="Notes" aside={<span className="muted small">analyst-authored, untrusted text</span>}>
          {ev.notes.length === 0 ? <p className="empty">No notes yet.</p> : (
            <ul className="notes">
              {ev.notes.map((n) => (
                <li key={n.note_id}><div className="muted small">{n.actor} · {new Date(n.created_at).toLocaleString()}</div>
                  <div className="note-body">{n.body}</div></li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Audit trail" aside={<span className="muted small">append-only</span>}>
        {ev.audit.length === 0 ? <p className="empty">No actions recorded yet.</p> : (
          <table className="compact">
            <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Before</th><th>After</th></tr></thead>
            <tbody>
              {ev.audit.map((a) => (
                <tr key={a.audit_id}>
                  <td className="num">{a.audit_id}</td><td className="small">{new Date(a.at).toLocaleString()}</td>
                  <td>{a.actor}</td><td>{label(a.action)}</td>
                  <td className="mono small">{a.prior_state ? JSON.stringify(a.prior_state) : "—"}</td>
                  <td className="mono small">{a.new_state ? JSON.stringify(a.new_state) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
