# Negative spillover: finish on Eesha's laptop (handoff 19 Nov 2026, 18:35)

Plan (fixed 14 Nov, before any data): `NEGATIVE_SPILLOVER_PLAN_14NOV.md`. Script: `scripts/negative_spillover_test.py`.

## State when handed over
- Mood scoring stopped on Shimona's laptop at her request. **11,398 videos already scored**, saved in
  `models/video_mood_14nov.json` (pushed with this note). About 1,600 videos were still to score.
- The test itself has **not** been run (`models/negative_spillover_results_14nov.json` does not exist).

## Steps
1. `git pull` on branch `review2-shimona-temporal`.
2. `.env` with `DATABASE_URL` (Azure; your IP must be allowed in the Azure firewall).
3. Scoring (resumes; skips every video already in `models/video_mood_14nov.json`; saves every 200 videos, so it can be
   stopped and started again):

       python -u scripts/negative_spillover_test.py score

   It uses the app's mood models (ml/temporal/sentiment.py: twitter-roberta-base-sentiment-latest for English, the
   multilingual XLM-R scorer for Hindi script). First run downloads the models from Hugging Face. CPU: about 470-600
   videos an hour; a GPU is much faster.
4. When scoring prints the last count and exits, run the test **ONCE** (the script refuses a second run):

       python -u scripts/negative_spillover_test.py run

5. Push `models/negative_spillover_results_14nov.json` and the updated `models/video_mood_14nov.json`.

## Rules (from the plan)
Run once; report whatever it shows. Negative spillover is DETECTED only if the 95% interval of the mean effect is
entirely below 0 and the placebo interval includes 0. Do not change windows, thresholds or the event rule after seeing
any number. A GAIL-R version is planned only if this simple test detects negative spillover.
