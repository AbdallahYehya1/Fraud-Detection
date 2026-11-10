import { useEffect, useState } from "react";
import { api, type EvaluationReport, type Overview } from "./api";
import { href } from "./App";
import { Card, ErrorNote, Loading, Stat, fmtNum, fmtPct, label } from "./ui";

const METHOD_LABELS: Record<string, string> = {
  champion: "Champion (booster + recipient history)",
  amount_type_rule: "Amount/type rule",
  logistic_regression_base: "Logistic regression (type + amount)",
  seeded_random: "Seeded random ranking",
};

export function OverviewView() {
  const [data, setData] = useState<Overview | null>(null);
  const [evalData, setEvalData] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.overview().then((o) => {
      setData(o);
      return api.evaluation(o.runs[0]?.run_id);
    }).then(setEvalData).catch(setError);
  }, []);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const ft = evalData?.frozen_test;

  return (
    <div className="stack">
      <div className="grid-3">
        <Card title="Dataset">
          <p><strong>{data.dataset.name}</strong></p>
          <p className="muted small">Licence {data.dataset.licence} · {data.dataset.unit} · {data.dataset.time}</p>
          <p className="mono small" title={data.dataset.csv_sha256}>sha256 {data.dataset.csv_sha256.slice(0, 16)}…</p>
        </Card>
        <Card title="Model">
          <p><strong>{data.model.model_version}</strong> <span className="muted">({label(data.model.kind)})</span></p>
          <p className="muted small">Contract {data.model.feature_contract} · split {data.model.split_protocol}</p>
          <p className="small">{data.model.features.map(label).join(", ")}</p>
        </Card>
        <Card title="Review policy">
          <p><strong>{data.policy.version}</strong>: top {data.policy.k} per simulation day</p>
          <p className="muted small">Partial days {data.policy.partial_segments}; ties by {data.policy.tie_break}.</p>
          <p className="muted small">{data.model.score_semantics}</p>
        </Card>
      </div>

      <Card title="Replay runs">
        {data.runs.length === 0 ? <p className="muted">No replay runs yet.</p> : (
          <table>
            <thead><tr><th>Run</th><th>Status</th><th>Progress</th><th>Segments</th><th>Cases</th><th></th></tr></thead>
            <tbody>
              {data.runs.map((r) => {
                const total = r.last_step - r.first_step + 1;
                const done = r.committed_through_step - r.first_step + 1;
                const counts = r.cases_by_status;
                const n = Object.values(counts).reduce((a, b) => a + (b ?? 0), 0);
                return (
                  <tr key={r.run_id}>
                    <td className="mono">{r.run_id}</td>
                    <td>{r.status}</td>
                    <td>
                      <div className="bar" aria-label={`${done} of ${total} steps`}><span style={{ width: `${(100 * done) / total}%` }} /></div>
                      <span className="muted small">steps {r.first_step}–{r.committed_through_step} of {r.last_step}</span>
                    </td>
                    <td>{r.finalized_segments}</td>
                    <td className="small">
                      {fmtNum(n)} total · {counts.new ?? 0} new · {counts.in_review ?? 0} in review · {counts.escalated ?? 0} escalated · {counts.closed ?? 0} closed
                    </td>
                    <td><a className="button" href={href({ view: "queue", run: r.run_id })}>Open queue</a></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <section className="evaluation">
        <div className="eval-banner">
          <strong>Offline evaluation</strong> — computed by the evaluator role from dataset labels; aggregates only.
          Labels are never shown in cases and are not available to investigation tools.
        </div>
        {ft && (
          <Card title="Frozen test partition (run once)">
            <div className="stats">
              <Stat value={fmtNum(ft.population.rows)} caption="test transactions" />
              <Stat value={fmtNum(ft.population.positives)} caption="labelled positives" />
              <Stat value={fmtPct(ft.population.prevalence, 2)} caption="prevalence (AP of a constant score)" />
            </div>
            <table>
              <thead><tr><th>Method</th><th className="num">Average precision</th><th className="num">Found at 100/day</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">In mixed-label hours</th></tr></thead>
              <tbody>
                {Object.entries(ft.methods).map(([m, v]) => (
                  <tr key={m}>
                    <td>{METHOD_LABELS[m] ?? m}</td>
                    <td className="num">{v.average_precision.toFixed(3)}</td>
                    <td className="num">{fmtNum(v.k100.true_positives)} / {fmtNum(v.k100.positives)}</td>
                    <td className="num">{fmtPct(v.k100.precision)}</td>
                    <td className="num">{fmtPct(v.k100.recall)}</td>
                    <td className="num">{fmtNum(v.mixed_hours.mixed.selected_true_positives)} / {fmtNum(v.mixed_hours.mixed.positives)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">
              Many test hours contain only fraud-labelled rows (a simulator artifact); the last column counts hits in
              ordinary mixed-label hours only. Synthetic data; no real-bank, savings or staffing claim follows.
            </p>
          </Card>
        )}
        {evalData?.run && (
          <Card title="This replay's day-end queues">
            <table>
              <thead><tr><th>Day</th><th className="num">Hours</th><th className="num">Capacity</th><th className="num">Transactions</th><th className="num">Positives</th><th className="num">Found</th><th className="num">Precision</th><th className="num">Recall</th></tr></thead>
              <tbody>
                {evalData.run.segments.map((s) => (
                  <tr key={s.day}>
                    <td>{s.day}</td><td className="num">{s.hours}</td><td className="num">{s.capacity}</td>
                    <td className="num">{fmtNum(s.population)}</td><td className="num">{s.positives}</td>
                    <td className="num">{s.true_positives}</td><td className="num">{fmtPct(s.precision)}</td><td className="num">{fmtPct(s.recall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">
              {evalData.run.offline_segment_crosscheck.every((c) => c.match)
                ? "Each day's queue reproduces the offline test evaluation for the same day exactly."
                : "Warning: a day's queue differs from the offline evaluation."}
            </p>
          </Card>
        )}
      </section>
    </div>
  );
}
