"""Day 1 local-inference smoke test (T23).

Runs against a local Ollama server only. No hosted endpoint is contacted; the
base URL must resolve to localhost. Tests:

1. grounded summary - evidence supplied in the prompt; every number in the
   answer must appear in the evidence, and evidence refs must be cited;
2. typed read-only tool call via Ollama's native /api/chat;
3. the same tool call via the OpenAI-compatible /v1/chat/completions endpoint
   (the route the planned eve adapter would use).
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import APP_ROOT
from .runtime import machine_memory_gib

FIXTURE = APP_ROOT / "fixtures" / "ai_smoke_case.json"
SYSTEM = ("You are a fraud-investigation assistant. Use only the evidence provided by tools or the user. "
          "Cite evidence refs like [E1]. Amounts are simulation currency units. Do not guess missing facts; "
          "say what is missing. You cannot see fraud labels and must not claim a transaction is fraud.")

TOOL = {
    "type": "function",
    "function": {
        "name": "get_case_evidence",
        "description": "Read-only. Return the stored evidence bundle for one investigation case.",
        "parameters": {
            "type": "object",
            "required": ["case_id"],
            "properties": {"case_id": {"type": "string", "description": "Case identifier, e.g. CASE-FIX-001"}},
            "additionalProperties": False,
        },
    },
}


def load_case() -> dict:
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case.pop("_note", None)
    return case


def get_case_evidence(arguments: dict, case: dict) -> dict:
    """Typed read-only tool. Validates arguments strictly; never mutates the fixture."""
    if set(arguments) != {"case_id"} or not isinstance(arguments["case_id"], str):
        return {"error": "invalid_arguments", "expected": {"case_id": "string"}}
    if arguments["case_id"] != case["case_id"]:
        return {"error": "case_not_found", "case_id": arguments["case_id"]}
    return json.loads(json.dumps(case))


def _numbers(text: str) -> set[float]:
    found = set()
    for m in re.findall(r"(?<![A-Za-z\-])\d[\d,]*\.?\d*", text):
        try:
            found.add(round(float(m.replace(",", "").rstrip(".")), 4))
        except ValueError:
            pass
    return found


def allowed_numbers(case: dict) -> set[float]:
    allowed = _numbers(json.dumps(case))
    # citation markers and percent rendering of the score are acceptable
    allowed |= {1.0, 2.0, 3.0, 87.0}
    return allowed


def evidence_refs(evidence: dict | None) -> set[str]:
    """Refs actually present in evidence returned to the model (none for an error result)."""
    return set(re.findall(r'"ref": "(E\d)"', json.dumps(evidence))) if evidence else set()


def check_answer(text: str, case: dict, returned: dict | None = None) -> dict:
    """Grade the final answer only. Reasoning must arrive in a separate field, not in content."""
    leaked = "</think>" in text or "<think>" in text
    final = text.rsplit("</think>", 1)[-1] if "</think>" in text else text
    nums = _numbers(re.sub(r"\[E\d\]", "", final))
    unsupported = sorted(n for n in nums if n not in allowed_numbers(case))
    cites = sorted(set(re.findall(r"\[(E\d)\]", final)))
    valid = evidence_refs(case if returned is None else returned)
    invalid_cites = sorted(c for c in cites if c not in valid)
    claims_fraud = bool(re.search(r"\b(is|was|confirmed)\s+(a\s+)?fraud(ulent)?\b", final, re.I))
    return {"numbers_found": sorted(nums), "unsupported_numbers": unsupported,
            "citations": [f"[{c}]" for c in cites], "invalid_citations": [f"[{c}]" for c in invalid_cites],
            "mentions_no_history": bool(re.search(r"no (earlier|prior|previous)", final, re.I)),
            "asserts_fraud_as_fact": claims_fraud, "reasoning_leaked_into_content": leaked,
            "passed": (not unsupported and len(cites) >= 2 and not invalid_cites
                       and not claims_fraud and not leaked)}


def _ollama_memory() -> dict:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process ollama*,llama-server* -ErrorAction SilentlyContinue | Select-Object Name,@{n='WS_MiB';e={[math]::Round($_.WorkingSet64/1MB)}},"
             "@{n='Peak_MiB';e={[math]::Round($_.PeakWorkingSet64/1MB)}} | ConvertTo-Json"],
            capture_output=True, text=True, timeout=30).stdout
        data = json.loads(out) if out.strip() else []
        return {"processes": data if isinstance(data, list) else [data]}
    except Exception as exc:  # observation only
        return {"error": str(exc)}


class Local:
    def __init__(self, base_url: str, model: str, num_ctx: int, timeout: float) -> None:
        host = urlparse(base_url).hostname
        if host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError(f"refusing non-local inference endpoint {base_url}")
        self.base, self.model, self.num_ctx = base_url.rstrip("/"), model, num_ctx
        self.http = httpx.Client(timeout=timeout)

    def native(self, messages: list[dict], tools: list | None = None) -> tuple[dict, float]:
        # qwen3:4b declares thinking values [True] only; think=false does not disable reasoning,
        # it moves it into content. Leave thinking at the model default so it stays in "thinking".
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"num_ctx": self.num_ctx, "temperature": 0, "seed": 20261109}}
        if tools:
            body["tools"] = tools
        t = time.perf_counter()
        r = self.http.post(f"{self.base}/api/chat", json=body)
        r.raise_for_status()
        return r.json(), round(time.perf_counter() - t, 2)

    def openai(self, messages: list[dict], tools: list | None = None) -> tuple[dict, float]:
        body = {"model": self.model, "messages": messages, "temperature": 0, "seed": 20261109}
        if tools:
            body["tools"] = tools
        t = time.perf_counter()
        r = self.http.post(f"{self.base}/v1/chat/completions", json=body)
        r.raise_for_status()
        return r.json(), round(time.perf_counter() - t, 2)

    def ps(self) -> dict:
        return self.http.get(f"{self.base}/api/ps").json()

    def version(self) -> str:
        return self.http.get(f"{self.base}/api/version").json().get("version")

    def tags(self) -> dict:
        return self.http.get(f"{self.base}/api/tags").json()


def _perf(resp: dict) -> dict:
    keys = ["total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
            "eval_count", "eval_duration"]
    p = {k: resp.get(k) for k in keys}
    if resp.get("eval_count") and resp.get("eval_duration"):
        p["tokens_per_second"] = round(resp["eval_count"] / (resp["eval_duration"] / 1e9), 2)
    return p


def run(base_url: str, model: str, num_ctx: int = 4096, timeout: float = 600.0) -> dict:
    case = load_case()
    llm = Local(base_url, model, num_ctx, timeout)
    result: dict = {"model": model, "base_url": base_url, "num_ctx": num_ctx,
                    "ollama_version": llm.version(), "memory_before": machine_memory_gib()}
    tag = next((m for m in llm.tags().get("models", []) if m["name"] == model), None)
    if tag:
        result["model_digest"] = tag.get("digest")
        result["model_size_bytes"] = tag.get("size")
        result["model_details"] = tag.get("details")

    # 0. warm load (separately timed so later latencies are steady-state)
    resp, secs = llm.native([{"role": "user", "content": "Reply with OK."}])
    result["warm_load"] = {"seconds": secs, "reply": resp["message"]["content"][:80], **_perf(resp)}
    result["loaded"] = llm.ps()
    result["memory_loaded"] = {**machine_memory_gib(), **_ollama_memory()}

    # 1. grounded summary from supplied evidence
    prompt = ("Evidence bundle (JSON):\n" + json.dumps(case) +
              "\n\nWrite a 3-sentence case summary for an analyst. Cite refs like [E1]. "
              "State what is missing. Do not add facts.")
    resp, secs = llm.native([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
    text = resp["message"]["content"]
    result["grounded_summary"] = {"seconds": secs, "response": text, "checks": check_answer(text, case),
                                  "thinking_chars": len(resp["message"].get("thinking") or ""), **_perf(resp)}

    # 2. native tool call
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Summarize case CASE-FIX-001 in 3 sentences with evidence refs."}]
    resp, secs1 = llm.native(msgs, tools=[TOOL])
    calls = resp["message"].get("tool_calls") or []
    step: dict = {"first_call_seconds": secs1, "tool_calls": calls, "first_perf": _perf(resp)}
    ok_call = (len(calls) == 1 and calls[0]["function"]["name"] == "get_case_evidence"
               and calls[0]["function"].get("arguments") == {"case_id": "CASE-FIX-001"})
    step["tool_call_valid"] = ok_call
    if calls:
        tool_out = get_case_evidence(calls[0]["function"].get("arguments") or {}, case)
        msgs += [resp["message"], {"role": "tool", "tool_name": "get_case_evidence",
                                   "content": json.dumps(tool_out)}]
        resp2, secs2 = llm.native(msgs, tools=[TOOL])
        final = resp2["message"]["content"]
        step.update({"second_call_seconds": secs2, "response": final,
                     "checks": check_answer(final, case, returned=tool_out),
                     "thinking_chars": len(resp2["message"].get("thinking") or ""),
                     "second_perf": _perf(resp2), "extra_tool_calls": resp2["message"].get("tool_calls")})
    step["passed"] = ok_call and step.get("checks", {}).get("passed", False)
    result["native_tool_call"] = step

    # 3. OpenAI-compatible tool call (eve/AI SDK route)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Summarize case CASE-FIX-001 in 3 sentences with evidence refs."}]
    oresp, osecs = llm.openai(msgs, tools=[TOOL])
    omsg = oresp["choices"][0]["message"]
    ocalls = omsg.get("tool_calls") or []
    ostep: dict = {"first_call_seconds": osecs, "tool_calls": ocalls, "usage": oresp.get("usage")}
    oargs = None
    if ocalls:
        try:
            oargs = json.loads(ocalls[0]["function"]["arguments"])
        except (TypeError, json.JSONDecodeError):
            oargs = None
    ostep["tool_call_valid"] = (len(ocalls) == 1 and ocalls[0]["function"]["name"] == "get_case_evidence"
                                and oargs == {"case_id": "CASE-FIX-001"})
    if ocalls:
        tool_out = get_case_evidence(oargs or {}, case)
        msgs += [omsg, {"role": "tool", "tool_call_id": ocalls[0].get("id"), "content": json.dumps(tool_out)}]
        oresp2, osecs2 = llm.openai(msgs, tools=[TOOL])
        omsg2 = oresp2["choices"][0]["message"]
        final = omsg2.get("content") or ""
        ostep.update({"second_call_seconds": osecs2, "response": final,
                      "checks": check_answer(final, case, returned=tool_out),
                      "reasoning_field_present": bool(omsg2.get("reasoning")),
                      "usage2": oresp2.get("usage")})
    ostep["passed"] = ostep["tool_call_valid"] and ostep.get("checks", {}).get("passed", False)
    result["openai_compatible_tool_call"] = ostep

    # 4. wrong-ID handling (tool returns case_not_found; model must not invent a case)
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Summarize case CASE-FIX-999."}]
    resp, secs = llm.native(msgs, tools=[TOOL])
    wcalls = resp["message"].get("tool_calls") or []
    wrong: dict = {"tool_calls": wcalls, "first_call_seconds": secs}
    if wcalls:
        out = get_case_evidence(wcalls[0]["function"].get("arguments") or {}, case)
        msgs += [resp["message"], {"role": "tool", "tool_name": "get_case_evidence", "content": json.dumps(out)}]
        resp2, secs2 = llm.native(msgs, tools=[TOOL])
        text = resp2["message"]["content"]
        nums = _numbers(re.sub(r"CASE-FIX-\d+", "", text))
        # the tool returned an error, so any evidence citation is unsupported
        cites = sorted(set(re.findall(r"\[E\d\]", text)))
        wrong.update({"second_call_seconds": secs2, "response": text,
                      "invented_case_numbers": sorted(n for n in nums if n in {181500.0, 0.87, 210.0}),
                      "invalid_citations": cites, "reasoning_leaked_into_content": "</think>" in text})
        wrong["passed"] = (not wrong["invented_case_numbers"] and not cites
                           and not wrong["reasoning_leaked_into_content"]
                           and bool(re.search(r"not found|no case|could not|unable|does not exist", text, re.I)))
    else:
        wrong["passed"] = False
    result["wrong_id"] = wrong
    result["memory_after"] = {**machine_memory_gib(), **_ollama_memory()}
    result["passed"] = all(result[k]["passed"] if "passed" in result[k] else result[k]["checks"]["passed"]
                           for k in ("grounded_summary", "native_tool_call", "openai_compatible_tool_call", "wrong_id"))
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen3:4b")
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--out", type=Path, default=APP_ROOT / "reports" / "day1")
    args = ap.parse_args(argv)
    res = run(args.base_url, args.model, args.num_ctx)
    args.out.mkdir(parents=True, exist_ok=True)
    name = "local_ai_smoke_" + args.model.replace(":", "_").replace("/", "_") + ".json"
    (args.out / name).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("model", "ollama_version", "passed")}, indent=2))
    for k in ("grounded_summary", "native_tool_call", "openai_compatible_tool_call", "wrong_id"):
        print(k, "passed=", res[k].get("passed", res[k].get("checks", {}).get("passed")))
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
