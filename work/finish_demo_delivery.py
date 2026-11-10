from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs"
APP=ROOT/"fraud-investigation"
verification=json.loads((OUT/"Fraud_Detection_Demo_Verification.json").read_text(encoding="utf-8"))
assert verification["delivery"]["full_decode_verified"]
assert verification["protected_reports_unchanged"]
assert verification["assistant"]["mode"]=="assistant"
assert not verification["assistant"]["case_changed"]
assert verification["review"]["status"]=="closed"
duration=verification["duration_seconds"]
duration_text=f"{int(duration//60)} min {round(duration%60):02d} s"

notes=f"""# Fraud Detection and Investigation — recorded demo

Recorded 10 November 2026 from the working local application.

**[Play the captioned MP4](Fraud_Detection_Demo.mp4)** · [Captions](Fraud_Detection_Demo.srt) · [Verification record](Fraud_Detection_Demo_Verification.json)

- Duration: approximately {duration_text}.
- Format: H.264 MP4, 1600 × 1120, 25 fps, captions included in a separate lower band.
- Audio: none. Actions and assistant generation are shown at their actual speed; one chapter cut joins the human-review continuation after a recorder navigation error.
- Local assistant: {verification['assistant']['model']}; this demonstration response took {verification['assistant']['seconds']} seconds with {verification['assistant']['tool_calls']} tool call(s).
- The assistant left the case version, notes and audit count unchanged.
- A human then reviewed the synthetic case and closed it as needs more information. The audit trail records those actions.
- Existing original holdout, fresh holdout and freeze files retained their recorded SHA-256 values.
- Verification run: 101 tests passed, with one dependency deprecation warning, in 9.95 seconds. The frozen holdout was not rerun.

The demonstration uses case {verification['case_id']}, selected outside the saved assistant evaluation cases. Authentication was prepared without showing or typing a credential on camera. No inference API or hosting fee was used.

The video covers dataset/model/policy identity, the frozen offline comparison, the queue, transaction evidence, scoring-time versus review-time history, the local assistant, and a human disposition with its audit trail.

**Limitations shown:** PaySim is synthetic, scores are rankings rather than calibrated probabilities, many test hours contain only positive labels, and the fresh assistant holdout remains 10/12. The question-number filter, refusal grader and short note paraphrases remain documented limitations. Zero observed unsafe delivered outputs on that small holdout is not a universal safety claim.

The full decoded video stream was checked successfully and sampled frames were inspected before delivery.
"""
(OUT/"Fraud_Detection_Demo_Notes.md").write_text(notes,encoding="utf-8")

backlog_path=OUT/"fraud-project-backlog.json"
backlog=json.loads(backlog_path.read_text(encoding="utf-8"))
for task in backlog["tasks"]:
    if task["id"]=="T18":
        task["status"]="complete"
        task["completed_date"]="2026-11-10"
        task.setdefault("implementation_artifacts",[])
        for item in ["outputs/Fraud_Detection_Demo.mp4","outputs/Fraud_Detection_Demo.srt","outputs/Fraud_Detection_Demo_Notes.md","outputs/Fraud_Detection_Demo_Verification.json"]:
            if item not in task["implementation_artifacts"]:
                task["implementation_artifacts"].append(item)
        task["evidence_note"]=f"Captioned {duration_text} recording of the actual local UI, live local assistant and human review/audit flow. 101 tests pass. Full video decode checked; source holdout/freeze report hashes unchanged. Fresh holdout stays 10/12 with documented limitations."
backlog["open_blockers"]=[b for b in backlog.get("open_blockers",[]) if b.get("task")!="T18"]
backlog["immediate_next"]=[]
backlog["updated_date"]="2026-11-10"
backlog["status"]="seven_day_mvp_complete_with_documented_limitations"
backlog_path.write_text(json.dumps(backlog,indent=2),encoding="utf-8")

readme_path=APP/"README.md"
readme=readme_path.read_text(encoding="utf-8")
recording_text="**Recorded walkthrough:** [captioned demo](../outputs/Fraud_Detection_Demo.mp4) · [recording notes and limitations](../outputs/Fraud_Detection_Demo_Notes.md).\n\n"
if "**Recorded walkthrough:**" not in readme:
    readme=readme.replace("**Requirements:**",recording_text+"**Requirements:**",1)
readme_path.write_text(readme,encoding="utf-8")

checkpoint_path=APP/"docs/checkpoints/day-07.md"
checkpoint=checkpoint_path.read_text(encoding="utf-8")
checkpoint=checkpoint.replace("| T18 Reproducible portfolio release | **partial** |","| T18 Reproducible portfolio release | **complete** (recording follow-up below) |",1)
checkpoint=checkpoint.replace("**Open: the 3–5 minute demo recording (manual step) and the T21 follow-ups**","The recording and T21 follow-ups were completed in the subsequent follow-ups; see below.",1)
checkpoint=checkpoint.replace("T17's dependency T21 is still partial (assistant holdout 10/12 with a citation-validation gap). The end-to-end and performance checks here do not depend on resolving it.","At the initial Day 7 check, T21 was partial. The Day 6 follow-up subsequently completed the fixes and a fresh 10/12 holdout; its reported failures remain documented.",1)
checkpoint=checkpoint.replace("1. **Demo recording (T18)** — your step, following `docs/demo_script.md`.","1. **Demo recording (T18)** — completed; see recording follow-up below.",1)
checkpoint=checkpoint.replace("2. **Assistant follow-ups (T21):** validate parenthesized `(E1)` refs; forbid quoting note text; require a cutoff statement when a tool enforces the cutoff. Then author a **new** holdout set and run it once.","2. **Assistant follow-ups (T21)** — completed and evaluated on a fresh holdout; see the Day 6 follow-up. Remaining competence/guard limitations are disclosed.",1)
followup=f"""

---

## Recording follow-up — 10 November 2026

T18 is complete. The actual local browser workflow was recorded and delivered as [a captioned MP4](../../../outputs/Fraud_Detection_Demo.mp4), approximately {duration_text}, with [captions](../../../outputs/Fraud_Detection_Demo.srt) and [verification](../../../outputs/Fraud_Detection_Demo_Verification.json).

The video shows the overview and frozen evaluation, a ranked queue, case evidence and history timing, an actual local {verification['assistant']['model']} response, and a human review ending with needs more information and its audit trail. The assistant response took {verification['assistant']['seconds']} seconds; its case version/notes/audit counts did not change. The human subsequently changed the synthetic demo case through the UI.

Verification: 101 tests passed (one dependency deprecation warning) in 9.95 seconds. No holdout evaluation was rerun. The original holdout, new holdout and frozen identity files kept their pre-recording SHA-256 values. Full video decoding succeeded, and sampled frames were visually checked.

The recording explicitly retains the synthetic-data caveat, ranking-score semantics, simulator artifact, 10/12 fresh holdout result, and the remaining question-number/refusal-grading/short-paraphrase limitations. Editorial captions are in a separate lower band. No audio or generation speedup is used; no analyst credential is shown. One chapter edit joins the human-review continuation after a capture-selector error; the live assistant response was not regenerated.

No fraud model, assistant guard, grading rubric or evaluation result was changed to make this recording.
"""
if "## Recording follow-up — 10 November 2026" not in checkpoint:
    checkpoint+=followup
checkpoint_path.write_text(checkpoint,encoding="utf-8")
print(json.dumps({"T18":"complete","duration":duration_text,"core_mvp_tasks_remaining":[t["id"] for t in backlog["tasks"] if t.get("release")=="seven_day_mvp" and t["status"]!="complete"]},indent=2))
