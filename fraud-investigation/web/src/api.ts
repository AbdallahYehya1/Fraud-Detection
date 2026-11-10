// Typed client for the local FastAPI service. In dev, Vite proxies /api; in the built
// app, FastAPI serves the UI and the API from the same origin.
const BASE = import.meta.env.DEV ? "/api" : "";
const TOKEN_KEY = "fraudinv.analystToken";

export type CaseStatus = "new" | "in_review" | "escalated" | "closed";
export type Disposition = "needs_more_information" | "suspicious_in_demo" | "no_action";

export interface Run {
  run_id: string;
  status: string;
  first_step: number;
  last_step: number;
  committed_through_step: number;
  daily_capacity: number;
  model_version: string;
  policy_version: string;
  finalized_segments: number;
  cases_by_status: Partial<Record<CaseStatus, number>>;
}

export interface Overview {
  dataset: { name: string; licence: string; key: string; csv_sha256: string; unit: string; time: string };
  model: { model_version: string; kind: string; features: string[]; feature_contract: string; split_protocol: string; score_semantics: string };
  policy: { version: string; rule: string; k: number; partial_segments: string; tie_break: string };
  runs: Run[];
}

export interface QueueItem {
  case_id: string;
  status: CaseStatus;
  disposition: Disposition | null;
  version: number;
  assigned_to: string | null;
  simulation_day: number;
  rank: number;
  capacity: number;
  event_id: string;
  step: number;
  type: string;
  amount: string;
  score: number;
  dest_has_prior: number;
  unit: string;
}

export interface TxRecord { event_id: string; step: number; type: string; amount: string; name_orig: string; name_dest: string }
export interface RecordSet { count: number; amount_sum: string; shown: number; steps: [number, number]; records: TxRecord[]; matches_score_time_count?: boolean }

export interface Evidence {
  case: { case_id: string; run_id: string; status: CaseStatus; disposition: Disposition | null; version: number;
          assigned_to: string | null; scoring_step: number; case_evidence_cutoff_step: number; created_at: string; updated_at: string };
  transaction: TxRecord & { source_row: number; unit: string };
  model_evidence: { score: number; rank: number; capacity: number; simulation_day: number; partition: string;
                    model_version: string; feature_contract: string; policy_version: string; feature_sha256: string;
                    score_time_features: Record<string, number | string | null>; semantics: string };
  computed_facts: { id: string; fact: string; source: string }[];
  recipient_history: { score_time: RecordSet; review_time: RecordSet; note: string };
  sender_history: { score_time: RecordSet; review_time: RecordSet };
  missing_information: string[];
  notes: { note_id: number; actor: string; body: string; created_at: string; trust: string }[];
  audit: { audit_id: number; actor: string; action: string; prior_state: Record<string, unknown> | null;
           new_state: Record<string, unknown> | null; at: string }[];
}

export interface Capacity { alerts: number; true_positives: number; positives: number; precision: number | null; recall: number | null; false_alerts_per_1000_legitimate: number | null }
export interface EvaluationReport {
  scope: string;
  frozen_test?: {
    population: { rows: number; positives: number; prevalence: number };
    constant_score_ap_reference: number;
    methods: Record<string, { average_precision: number; k100: Capacity; mixed_hours: Record<string, { rows: number; positives: number; selected_true_positives: number }> }>;
    bootstrap: Record<string, Record<string, { "p2.5": number; "p97.5": number }>>;
  };
  run?: { segments: { day: number; hours: number; capacity: number; population: number; positives: number;
                      true_positives: number; alerts: number; precision: number | null; recall: number | null }[];
          total: { population: number; positives: number; true_positives: number; alerts: number; precision: number | null; recall: number | null };
          offline_segment_crosscheck: { day: number; match: boolean }[] } | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public body: Record<string, unknown> = {}) {
    super(message);
  }
}

export function getToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: token lives only in memory for this page */ }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const res = await fetch(BASE + path, { ...init, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    throw new ApiError(res.status, detail, body);
  }
  return body as T;
}

const caseUrl = (id: string) => `/cases/${id.split("/").map(encodeURIComponent).join("/")}`;

export interface AssistantReply {
  mode: "assistant" | "template_fallback" | "error";
  label: string;
  answer: string;
  tool_calls: number;
  seconds: number;
  model: string;
  error: string | null;
  refs: Record<string, string>;
  tool_trace: { tool: string; ok: boolean; error: string | null; ms: number }[];
  guard: { removed: { text: string; reasons: string[] }[] | null; valid_refs_cited: string[] | null };
}

export const api = {
  assistant: (caseId: string, question: string) =>
    request<AssistantReply>(`${caseUrl(caseId)}/assistant`, { method: "POST", body: JSON.stringify({ question }) }),
  overview: () => request<Overview>("/overview"),
  evaluation: (runId?: string) => request<EvaluationReport>(`/evaluation${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`),
  me: () => request<{ analyst_id: string; display_name: string }>("/me"),
  queue: (runId: string, status: string, day: string, offset: number) => {
    const q = new URLSearchParams({ run_id: runId, limit: "50", offset: String(offset) });
    if (status) q.set("status", status);
    if (day) q.set("day", day);
    return request<{ total: number; items: QueueItem[] }>(`/cases?${q}`);
  },
  evidence: (caseId: string) => request<Evidence>(`${caseUrl(caseId)}/evidence`),
  transition: (caseId: string, body: { expected_version: number; status: CaseStatus; disposition?: Disposition; note?: string }) =>
    request<{ status: CaseStatus; version: number }>(`${caseUrl(caseId)}/transition`, { method: "POST", body: JSON.stringify(body) }),
  addNote: (caseId: string, body: string) =>
    request<{ note_id: number }>(`${caseUrl(caseId)}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
};
