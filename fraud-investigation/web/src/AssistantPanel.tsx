import { useState } from "react";
import { api, type AssistantReply } from "./api";
import { Card } from "./ui";

const SUGGESTIONS = ["Summarize this case.", "What is missing from the evidence?", "Explain the model evidence."];

export function AssistantPanel({ caseId, signedIn }: { caseId: string; signedIn: boolean }) {
  const [question, setQuestion] = useState(SUGGESTIONS[0]);
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    setBusy(true);
    setError(null);
    try {
      setReply(await api.assistant(caseId, question.trim()));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Local assistant" aside={<span className="badge">read-only · runs on this computer</span>}>
      {!signedIn ? <p className="muted">Sign in to ask the assistant about this case.</p> : (
        <div className="actions">
          <div className="buttons">
            {SUGGESTIONS.map((s) => <button key={s} className="ghost small" onClick={() => setQuestion(s)}>{s}</button>)}
          </div>
          <textarea rows={2} maxLength={500} value={question} onChange={(e) => setQuestion(e.target.value)} />
          <div className="buttons">
            <button className="primary" disabled={busy || !question.trim()} onClick={ask}>
              {busy ? "Thinking… (usually 15–60 s)" : "Ask"}
            </button>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          {reply && (
            <div className="assistant-reply">
              <p className={reply.mode === "assistant" ? "badge" : "tag"}>{reply.label}</p>
              <div className="note-body">{reply.answer}</div>
              <p className="muted small">
                {reply.tool_calls} tool call(s) · {reply.seconds}s
                {reply.guard.removed && reply.guard.removed.length > 0 &&
                  ` · ${reply.guard.removed.length} unsupported sentence(s) removed by the guard`}
                {reply.error && ` · ${reply.error}`}
              </p>
              {reply.guard.valid_refs_cited && reply.guard.valid_refs_cited.length > 0 && (
                <p className="muted small">
                  Refs: {reply.guard.valid_refs_cited.map((r) => `${r} = ${reply.refs[r]}`).join(" · ")}
                </p>
              )}
            </div>
          )}
          <p className="muted small">
            Uses only this case's evidence up to its cutoff. It cannot see dataset labels or change the case. Check
            every statement against the evidence above; numbers and refs are verified automatically, wording is not.
          </p>
        </div>
      )}
    </Card>
  );
}
