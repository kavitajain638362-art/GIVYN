# GIVYN seasonal model experiment

This is an experimental model, not professional validation. It must not be presented as reliable personal accuracy. User uploads, saved results and the model's own predictions are **not** training data.

## Data and permitted use

Feature CSV: [Lumina research repository](https://github.com/nypoclary/armocromia-classical-ml), Ngwe Yee Pearl Ou and Jonathan Hoyin Chan, *Lumina: Seasonal Color Analysis System with Explainable Machine Learning*, IAIT 2026, DOI [10.1145/3816713.3818796](https://doi.org/10.1145/3816713.3818796). Downloaded revision `63d3338078c27a3b2a89b340e0ad38d8f2c46388`, file `data/features_30_per_region.csv`. Its SHA-256 is recorded in `evaluation.json`.

The features derive from [Deep Armocromia](https://github.com/lorenzo-stacchio/Deep-Armocromia), Stacchio, Paolanti, Spigarelli and Frontoni, ECCV 2024. The original dataset is released for **scientific/research purposes only**. GIVYN treats these features and the resulting model as research-use artifacts. The upstream MIT code license is retained in `data/SOURCE_LICENSE.txt`; it does not establish commercial rights to the source photographs or derived data. Obtain appropriate data rights before commercial use. No original training photographs were downloaded or redistributed here. Public person names appear in the source CSV and are used only to separate identities, never as prediction features.

## Reproduce

From the project root:

```powershell
uv pip install --python .venv/Scripts/python.exe -r training/requirements.txt
.venv/Scripts/python.exe -m training.train
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Outputs: `backend/models/seasonal_model.json`, `training/evaluation.json`, and `training/split_manifest.json`. Restart Flask after retraining. NumPy runs the portable JSON model; scikit-learn is used only to train/evaluate the forest candidate. Never load a third-party pickle as a replacement model.

## Audit and protocol

Of 4,920 source rows, 2,981 have no supplied person identity, 11 belong to a conflicting-label identity and one lacks required measurements. Those rows are excluded. 1,927 rows remain: 1,182 training rows / 294 identities, 358 validation rows / 96 identities, and 387 test rows / 99 identities. Names are normalized for punctuation, spaces, case and accents before a deterministic, label-stratified identity split (seed 42). Names with multiple season labels are excluded. Exact feature duplicates are checked across all splits. Aliases and incorrect labels may still remain; these are disjoint *supplied identities*, not verified real-world identities.

The source image partition is intentionally replaced because repeated people across image splits can inflate generalization claims. No seasonal or person-based imputation is used. Model inputs never include labels, subtypes, names, filenames, source partitions or CelebA flags.

For each representation, six regularized linear/quadratic softmax candidates and one fixed random-forest candidate are compared using **validation macro F1**. Standardization is fitted on training rows only. Temperature scaling uses validation labels only. Test labels are used only to report the final feature benchmark. The model remains fitted on the training partition; test rows are never folded back into training.

## Results and interpretation

| Representation | Test accuracy | Macro F1 | Top-two accuracy |
| --- | ---: | ---: | ---: |
| Skin + hair Lab means (live model when hair available) | 44.96% | 0.4484 | 76.23% |
| Detailed skin + hair statistics (offline experiment) | 43.93% | 0.4342 | 73.39% |
| Skin Lab means (weak-evidence fallback) | 29.20% | 0.2842 | 52.71% |

All values use 387 held-out source rows. The largest held-out class is 30.23% of the test set; always predicting the *training* majority class gives 24.55%. Both are constant-class comparison points, not the previous GIVYN algorithm. Full candidate scores, per-class recalls and confusion matrices are in `evaluation.json`. The live skin-and-hair model predicts all four classes on the held-out set (Autumn 65, Spring 72, Summer 127, Winter 123); this is a regression check against output collapse, not evidence of balanced accuracy.

The detailed statistics model is retained for inspection and reproduction, not used on live photographs. The mean-only model offers a closer shared feature definition for segmented pixels and manual swatches. Source skin/hair segmentation differs from GIVYN's forehead/cheek and hair extraction. **These metrics do not measure GIVYN's end-to-end photo accuracy.** Demographic, gender and skin-depth coverage is unverified. All live results remain tentative; the skin-only fallback is explicitly weak evidence. Eye-region source statistics include a different region from an iris sample, so iris measurements are used for contrast descriptions but are deliberately not passed as training-compatible eye features.

Undertone labels were not provided, so no undertone model was trained. The displayed undertone remains a photo-based heuristic, separate from the learned seasonal classifier. User drape observations affect that heuristic, not the learned probabilities. Compatibility and palette explanations remain knowledge-base rules.

The sensitivity diagnostic changes each measured mean by ±2 L* or ±1 a*/b* and reports how often the leading season stays the same. It is deterministic and **not an accuracy or confidence calibration measure**. Regional ablation explanations replace one region with the training average; they describe model sensitivity, not causes of a person's natural coloring. Predictions outside the usual training range, missing hair, manual swatches or photo warnings lower confidence.

## Improving the next version

Collect a separately consented, expert-labeled photo dataset with natural hair/eyes, consistent lighting, repeated captures and documented coverage across men, women and skin depths. Split by person before any fitting and keep a final external set untouched. Evaluate the actual GIVYN extraction pipeline, class recall, calibration, repeated-photo consistency and performance by consented demographic groups. Do not infer demographic labels from photos, label people from HEX heuristics, or train on GIVYN's own output. More source rows alone do not establish better accuracy.
