# Fraud Detection and Investigation — recorded demo

Recorded 10 November 2026 from the working local application.

**[Play the captioned MP4](Fraud_Detection_Demo.mp4)** · [Captions](Fraud_Detection_Demo.srt) · [Verification record](Fraud_Detection_Demo_Verification.json)

- Duration: approximately 4 min 40 s.
- Format: H.264 MP4, 1600 × 1120, 25 fps, captions included in a separate lower band.
- Audio: none. Actions and assistant generation are shown at their actual speed; one chapter cut joins the human-review continuation after a recorder navigation error.
- Local assistant: qwen3:4b; this demonstration response took 59.77 seconds with 1 tool call(s).
- The assistant left the case version, notes and audit count unchanged.
- A human then reviewed the synthetic case and closed it as needs more information. The audit trail records those actions.
- Existing original holdout, fresh holdout and freeze files retained their recorded SHA-256 values.
- Verification run: 101 tests passed, with one dependency deprecation warning, in 9.95 seconds. The frozen holdout was not rerun.

The demonstration uses case demo-test-d14-16/test/d15/r012, selected outside the saved assistant evaluation cases. Authentication was prepared without showing or typing a credential on camera. No inference API or hosting fee was used.

The video covers dataset/model/policy identity, the frozen offline comparison, the queue, transaction evidence, scoring-time versus review-time history, the local assistant, and a human disposition with its audit trail.

**Limitations shown:** PaySim is synthetic, scores are rankings rather than calibrated probabilities, many test hours contain only positive labels, and the fresh assistant holdout remains 10/12. The question-number filter, refusal grader and short note paraphrases remain documented limitations. Zero observed unsafe delivered outputs on that small holdout is not a universal safety claim.

The full decoded video stream was checked successfully and sampled frames were inspected before delivery.
