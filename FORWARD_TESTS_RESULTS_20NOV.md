# Forward tests, result runs of 20 Nov 2026 (each run once, as fixed in the plans)

Data collection finished first (Instagram 128 readings; YouTube 69 new uploads; final history fetch 7,131 older videos).

## 1. Collaboration -> subscriber growth of the tagged creator (COLLAB_SPILLOVER_PLAN_7NOV.md, timing note 10 Nov)
`scripts/collab_forward_test.py run`, 20 Nov 15:06 IST; models/collab_forward_results_20nov.json.
- 22 collaboration events since 7 Nov; 21 with 48 h passed; **9 counted** (both readings available).
- Verdict (plan rule): **fewer than 20 counted events: early evidence, not a result.**
- Numbers for the record only: mean -2.25 (log growth, 48 h after minus 48 h before) [-6.75, -0.0001], n = 9;
  placebo 0.0 [0.0, 0.0], n = 337 from 2 creators; B under 100k: n = 2. Values this far from normal 48-hour growth on
  9 events are not interpreted.

## 2. Big-host collaboration -> subscriber growth of the guest (BIG_HOST_SPILLOVER_PLAN_9NOV.md)
`scripts/big_host_forward_test.py run`, 20 Nov 15:06 IST; models/big_host_results_20nov.json, models/big_host_events.json.
- 6 big-host events since 10 Nov; 4 with 48 h passed; **2 counted**.
- Verdict (plan rule): **fewer than 20 counted events: early evidence, not a result** (host 3x and 10x the same 2 events).
- Numbers for the record only: -0.0028 [-0.0056, 0.0], n = 2; placebo -0.0015 [-0.0028, 0.0], n = 337.

## Reading
The forward studies started on 7 and 10 Nov; at 3-7 events a week they could not reach 20 counted events by the
project cut-off. Reported in the paper as running studies with their event counts, not as findings. Per the big-host
plan, a second, final run on 30 Nov is reported only if the data keeps coming.
