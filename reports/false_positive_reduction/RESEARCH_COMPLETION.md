# False-positive reduction experiment completion

Date: 2026-11-14
Branch: `experiment/false-positive-reduction`
Base release: `release/final-detect-first` at `16c657c`

## Preservation and protocol status

Astra's experiment worktree and branch were preserved. The two pre-existing
untracked backend test artifacts remain unmodified:

- `backend_tests.log`
- `backend_tests.xml`

The frozen protocol is `docs/FALSE_POSITIVE_PROTOCOL.md`. Development data,
labels, candidate policies, selection rules, separation audit, production model
hash, and input hashes were committed before scoring. The development set is 80
repository-authored synthetic first-contact scenarios: 40 legitimate-intent and
40 fraudulent-intent. Labels are stipulated author intent, not independent
human adjudication. It is separate from the 32 final messages and demo
fixtures.

The separation audit reported zero normalized exact overlaps, zero internal
exact duplicates, zero development/final or development/demo cosine pairs at
0.85, and maximum cross cosine 0.3522. This is a lexical audit, not proof of
semantic independence.

## Backend regression

Astra's backend suite completed before the one-shot final evaluation:

- **135 passed, 64 deselected** (`-m not browser`)

The final evaluation was run once, after the backend gate. The protocol created
`final_run_started.json` before inference and refuses a repeat or overwrite.
The inherited `reports/final_blind_evaluation.json` is the original-model
report; it was not treated as candidate output.

## Development selection

Original combined development baseline:

- `[[16, 24], [4, 36]]`
- TP 36, TN 16, FP 24, FN 4
- Precision 0.6000, recall 0.9000, F1 0.7200, FPR 60.0%

`strong_actions` combined:

- `[[38, 2], [18, 22]]`
- TP 22, TN 38, FP 2, FN 18
- Precision 0.9167, recall 0.5500, F1 0.6875, FPR 5.0%

`strong_actions_sensitive` combined, selected for diagnostic comparison:

- `[[38, 2], [14, 26]]`
- TP 26, TN 38, FP 2, FN 14
- Precision 0.9286, recall 0.6500, F1 0.7647, FPR 5.0%

Neither candidate is eligible. Both violate the requirement of no more false
negatives than the original combined policy; `strong_actions_sensitive` also
fails the required F1 improvement of at least 0.05 (improvement was 0.0447).
The selection artifact explicitly records `passes_development_gate: false` and
labels the selected policy diagnostic-only.

## One-shot diagnostic final results

The exposed historical 32-message synthetic set was evaluated once, only after
development selection. It was not used to select or revise the candidate.
Matrices are rows actual and columns predicted in `[legitimate, fraudulent]`
order.

| System | N | TP | TN | FP | FN | Precision | Recall | F1 | Matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ML classifier | 32 | 5 | 16 | 0 | 11 | 1.0000 | 0.3125 | 0.4762 | `[[16, 0], [11, 5]]` |
| Original evidence rules | 32 | 9 | 8 | 8 | 7 | 0.5294 | 0.5625 | 0.5455 | `[[8, 8], [7, 9]]` |
| Original combined | 32 | 11 | 8 | 8 | 5 | 0.5789 | 0.6875 | 0.6286 | `[[8, 8], [5, 11]]` |
| Experimental rules | 32 | 3 | 16 | 0 | 13 | 1.0000 | 0.1875 | 0.3158 | `[[16, 0], [13, 3]]` |
| Experimental combined | 32 | 7 | 16 | 0 | 9 | 1.0000 | 0.4375 | 0.6087 | `[[16, 0], [9, 7]]` |

The experimental combined policy removes the eight observed false alarms on
this exposed synthetic set but misses four more scams than the original
combined policy. Its improvement is therefore not defensible, and it must not
be deployed.

Experimental combined false negatives:
`clear-scam-01`, `clear-scam-03`, `clear-scam-04`, `clear-scam-08`,
`subtle-scam-02`, `subtle-scam-03`, `subtle-scam-04`, `subtle-scam-05`,
`subtle-scam-07`.

Original combined false positives:
`clear-legit-02`, `clear-legit-03`, `clear-legit-04`, `clear-legit-06`,
`clear-legit-07`, `clear-legit-08`, `subtle-legit-05`, `subtle-legit-08`.

## Limitations and decision

The 80-message development set and 32-message final set are synthetic and
AI-authored. Public FTC/FBI guidance informed scenario families but supplied no
labels. No authentic, human-adjudicated first-contact recruitment benchmark was
available. The experiment demonstrates a precision/recall tradeoff on frozen
synthetic data; it does not establish real-world accuracy or improvement.

The original production model, evidence policy, frontend, warning UI, stable
release branch, and production model hash remain unchanged. No additional
training, optimization, threshold tuning, or final-set rerun was performed.
