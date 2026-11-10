import type { ReactNode } from "react";

export const fmtAmount = (s: string) =>
  Number(s).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtPct = (x: number | null | undefined, d = 1) => (x == null ? "n/a" : `${(100 * x).toFixed(d)}%`);
export const fmtNum = (x: number) => x.toLocaleString("en-US");
export const label = (s: string) => s.replace(/_/g, " ");

export function Card({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function StatusPill({ status }: { status: string }) {
  return <span className={`pill pill-${status}`}>{label(status)}</span>;
}

export function Loading() {
  return <p className="muted">Loading…</p>;
}

export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return <p className="error" role="alert">{msg}</p>;
}

export function Stat({ value, caption }: { value: ReactNode; caption: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-caption">{caption}</div>
    </div>
  );
}
