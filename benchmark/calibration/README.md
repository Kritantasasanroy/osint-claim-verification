# Confidence calibration artifacts

`Harness` loads `confidence.json` from this folder when it exists. **It deliberately does not exist yet.**

`candidate-dev2.json` was fitted on `results/v2-dev2` (dev split, seed 0, `short`, 42 episodes, 5 wrong).
Leave-one-out Brier on those episodes: shipped evidence posterior 0.184, model's verbalised probability 0.067,
this calibrator 0.075. It weights the model's probability 2.0 and the evidence posterior -0.09.

It is not adopted because (1) five wrong answers are too few to fit four weights, and (2) with these weights a
model that says 99% over two 0.40 sources would ship ~0.99 again, which is the failure the review flagged
(A1); the stopping gate would still refuse to close the case, but the reported number would mislead.
Adopt a calibrator only after a dev run with several seeds and memory modes gives enough wrong answers.
