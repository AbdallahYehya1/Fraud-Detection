# PaySim initial data audit

**Measured from canonical version 2 on 8 November 2026. No model trained.**

- Rows: 6,362,620; columns: 11.
- Positive fraud labels: 8,213 (0.1291%).
- Existing policy flags: 16; this count alone is not its precision.
- CSV: 493,534,783 bytes; ZIP: 186,385,561 bytes.
- Relative hourly steps: 1–743, with 743 observed hours.
- Missing cells: 0; negative amounts: 0.
- Distinct sender references: 6,353,307.
- Rows with strictly earlier-step sender history: 9,266 (0.146%).
- Distinct recipient references: 2,722,362.
- Rows with strictly earlier-step recipient history: 3,592,717 (56.466%).

**Implication:** focus available history features on recipients; do not promise rich sender histories or verified transfer chains. The recurrence calculation concerns the same source column/role and does not establish usefulness for prediction.

**Simulator artifact:** 320 hours contain only positive-labelled records. In the proposed final window, 195 hours contain only positives and contribute 2,250 of 4,250 positives. Keep whole-window results and evaluator-only mixed-hour diagnostics. A label-defined diagnostic subset is never an input to serving or the assistant.

**Proposed chronological partitions, not yet frozen**

- train_proposal: steps 1–281; 3,820,599 rows; 3,193 positives; prevalence 0.0836%.
- validation_proposal: steps 282–355; 1,293,285 rows; 770 positives; prevalence 0.0595%.
- test_proposal: steps 356–743; 1,248,736 rows; 4,250 positives; prevalence 0.3403%.


The class-support metadata above has been inspected; model/policy performance has not. Test prevalence differs substantially from development prevalence. Freeze the protocol before fitting and use prevalence-matched references.

**Open checks:** duplicate semantics, non-finite numeric values beyond missingness, time/class-specific history coverage, and final feature/policy/split decisions. No real-bank validation or fraud savings are established.

[Machine-readable audit](PaySim_Data_Audit.json) · [Source manifest](PaySim_Source_Manifest.json) · [Dataset attribution](data/README.md)
