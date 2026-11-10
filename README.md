# Fraud Detection: analyst investigation workbench

A local, free-to-run portfolio MVP. It ranks recorded **synthetic** mobile-money transactions
(PaySim v2), builds a fixed-capacity daily review queue, assembles review-time evidence for a human
analyst, and offers a bounded local AI assistant (Ollama + `qwen3:4b`). No paid service is used.

| folder | contents |
|---|---|
| [fraud-investigation/](fraud-investigation/) | **The application**: Python package, SQL, React workbench, tests, configs, reports and documentation. Start with its [README](fraud-investigation/README.md). |
| [outputs/](outputs/) | Planning documents (blueprint, seven-day sprint, implementation handoff, data guide), the PaySim source manifest and data audit, the task backlog, and the [captioned demo video](outputs/Fraud_Detection_Demo.mp4). |
| [work/](work/) | Planning-time scripts (data audit, demo recording/rendering) and demo stills. |

## Data (not included)

The PaySim v2 data is synthetic and licensed CC BY-SA 4.0 (E. A. Lopez-Rojas, A. Elmir and
S. Axelsson, EMSS 2016). It is not committed. To reproduce:

1. Download version 2 of [ealaxi/paysim1](https://www.kaggle.com/datasets/ealaxi/paysim1) and save the
   archive as `outputs/data/PaySim_v2.zip`.
2. From `fraud-investigation/`, run `python -m fraudinv verify --extract`. It checks the archive and the
   extracted CSV (`work/data/raw/paysim-v2.csv`) against the SHA-256 values in
   [config/data_source.yaml](fraud-investigation/config/data_source.yaml).

Other locations can be set with `FRAUDINV_RAW_ARCHIVE`, `FRAUDINV_RAW_CSV` and `FRAUDINV_DATA_DIR`.

## Headline results (synthetic test partition, evaluated once)

At 100 reviews per day the frozen model found 1,189 of 4,250 fraud-labelled transactions (precision 73.5%,
recall 28.0%, AP 0.335), versus 670 for an amount/type rule. In mixed-label hours only, which excludes a
simulator artifact, it found 505 of 2,000 (AP 0.241). The local assistant passed 10 of 12 cases on a fresh
holdout, with no writes, label claims or invalid citations. These are results on simulated data, not
real-world performance claims; see
[fraud-investigation/docs/evaluation.md](fraud-investigation/docs/evaluation.md).
