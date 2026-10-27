"""Builds Handoff_for_Eesha_27Oct.pdf: what was done, what was fixed, how to train, what is left. Numbers are the ones checked live on 27 Oct 2026.

    python scripts/make_handoff_pdf.py            (needs reportlab)
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "Handoff_for_Eesha_27Oct.pdf"
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.2, leading=12.4, spaceAfter=3)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.2, leading=10.6, textColor=colors.HexColor("#444444"))
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.3, leading=10.6, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
H1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, alignment=0, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1b3a5c"))
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=11, bulletIndent=2)
INK, LINE, SOFT = colors.HexColor("#1b3a5c"), colors.HexColor("#c9d1da"), colors.HexColor("#eef2f6")


def p(t, s=BODY):
    return Paragraph(t, s)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="-") for t in items]


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SOFT)]
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(18 * mm, 10 * mm, "Handoff for Eesha - capstone project 011 - 27 Oct 2026 - numbers read from the live database and code on 27 Oct")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


s = []
s += [p("Handoff for Eesha: what we did, what we fixed, what is left", H1),
      p("From Shimona and Claude, 27 Oct 2026. Branch <b>review2-shimona-temporal</b>, last pushed commit <b>45e0031</b> (later changes are noted below as not yet pushed). Everything here was checked against the live Supabase data and the code; where something is uncertain it says so.", SMALL),
      Spacer(1, 4)]

s += [p("1. The short version", H2)]
s += bullets([
    "<b>The data side is ready for GAIL training.</b> Training files are re-exported (27 Oct 14:00, after the label corrections): 159 independent shared-brand observations from 75 neighbours (it was about 39 observations before), and 95 of the 150 verified creators have at least one graph link (it was 17).",
    "<b>The old patch would have crashed.</b> The shared-brand block sat in a function without the <i>itertools</i> import (NameError at graph loading with SHARED_BRAND=1). The regenerated patch fixes it and adds an @mention edge option. Do not use any copy of the patch from before 27 Oct.",
    "<b>Real-data tests find no spillover and no confirmed lag.</b> Simulated checks on top of the same data show our tests would have caught a broad effect of 0.25 or more, so the null is informative (limits in section 5).",
    "<b>One number was retracted:</b> the earlier '91% of flagged sponsorship events are real ads' mixed human checks with assumed rows and earlier Claude drafts. Human-only: 73 of 75 (97%), but that is 4% of events; weak-tier precision is somewhere between about 60% and 95%.",
])

s += [p("2. Data: what we collected and fixed (the 150 verified creators unless noted)", H2),
      table([["Area", "Result", "What changed"],
             ["YouTube", "59,281 videos, Dec 2023 to Oct 2026; 262,700 growth readings every 2 h since 11 Oct", "History extended from about 21,000 to 59,000 videos (24 months). 2-hourly snapshot job runs inside Supabase."],
             ["Instagram", "78 of 150 creators, 1,021 posts; 403 posts still have no like/comment counts", "Daily job (12:00 IST, cap 130 page loads) now also fills counts for old posts with an owner check; foreign posts were detached with a backup."],
             ["Sponsorship events", "1,857 events (341 strong evidence, 1,516 weak: brand name or brand + code); all scored in sponsorship_event_scores", "Re-labelled after the history extension (892 to 1,876 earlier, 1,857 after removing 19 false labels). 28 wrong brands removed 25 Oct; 17 brandless posts of 9 creators given their brand and 25 unclassified brands classified 27 Oct (backups kept)."],
             ["Graph links", "Creators with any link: 17 (flags off), 80 (shared brand), 91 (plus @mentions), 95 after the 27 Oct brand fixes", "New relations: shared brand (1,226 directed edges) and @mention of another tracked creator (154 edges, 34 pairs inside the 150). Only 7 real collaboration pairs are inside the 150."],
             ["Sentiment", "149 of 150 creators scored; 35,152 comments", "Devanagari comments (about 1%) now scored with a multilingual model (agreement with labels +0.33 to +0.76); English and Hinglish unchanged."],
             ["Reddit", "3,308 posts, 61,570 comments (11% with a time); last run 21 Oct", "Unchanged; refresh is due."]],
            [26, 70, 78])]

s += [p("3. Fixes and corrections, in plain words", H2)]
s += bullets([
    "<b>Training patch:</b> shared-brand block moved to <i>load_cooccurrence_edges</i> (where itertools is imported); new env <i>MENTION_EDGES</i> adds the mention pairs to the collaborates_with graph. Tested by running both loaders on the live database with every flag combination.",
    "<b>Label accuracy:</b> only rows with reviewer exactly 'Shimona' (checked one by one) count as human; rows marked 'assumed' or 'not checked', the earlier 'Claude (draft)' rows and Claude's 26 Oct pre-labels are reported separately. The scoring script, the table, the dashboard card and the report were corrected.",
    "<b>Recommendation list:</b> creators with no collected posts on either platform used to rank in the top 3 on category and graph alone. They now rank below creators with data (none removed) and carry a 'no data collected yet' badge.",
    "<b>New feature:</b> per-platform status (YouTube vs Instagram: audience, typical views/likes/comments, engagement rate, first-24-hour growth, strong/typical/weak) for any creator, shown by a button on each dashboard card.",
    "<b>Other:</b> alerts now carry creator names; CLIP/BERT warm up at startup so the first brief gets real feature scores; Analysis tab has live-results cards with real results and SIMULATED checks side by side.",
    "<b>Not changed on purpose:</b> no model code, no GAIL checkpoint, no sponsored label flipped from true to false.",
])

s += [p("4. Results on real data (no simulation)", H2),
      table([["Question", "Result", "How to read it"],
             ["Spillover: neighbour lift after a sponsored post vs the same neighbour at placebo dates", "+0.00 (95% range -0.04 to +0.03); strong-evidence events only: -0.11 (-0.17 to 0.00)", "No broad spillover. The exposed-vs-unexposed comparison (+0.49) is confounded (exposed creators already grew faster); never quote it alone."],
             ["Dose-response: does a stronger tie (more shared brands) show more spillover?", "1 brand -0.05, 2 brands -0.06, 3 or more -0.11 (-0.23 to -0.06); trend over 63 neighbours -0.05 (-0.28 to +0.19)", "No gradient, so link weights were not changed."],
             ["Lag: Instagram post to YouTube views (15 days of readings)", "Control (YouTube upload to own views) detected; best Instagram to YouTube window p = 0.043, not significant after correcting for 4 windows", "No lag confirmed. Re-run 29 Oct and 8-10 Nov. Not tested yet: sentiment shifts, Granger."],
             ["Direct effect: a sponsored YouTube video vs the creator's own typical video", "Views ratio 0.98 (0.83 to 1.21), 80 creators; like+comment rate lower (-0.045, -0.136 to -0.013)", "A sponsored video draws about the same views. Instagram has only 15 usable posts."],
             ["Out-of-time ranking (rank from data before 1 Jan 2026, outcome after)", "No baseline beats random (popularity Spearman +0.08, engagement rate +0.13, past direct effect +0.30 then -0.14 at a second cutoff)", "Harness is ready: pass GAIL scores built only from pre-cutoff data with --scores."],
             ["Label accuracy of flagged events", "Human, one by one: 73 of 75 (97%, 91-99%). Claude text-only readings of 113 weak-tier events: 61% (52-70%)", "Weak tiers are uncertain (60-95%) until a person checks the 30 rows Claude called footer-only."]],
            [50, 62, 62])]

s += [p("5. Simulated checks on top of the real data (validation only)", H2),
      p("Simulated rows are built from the real events, neighbours and noise with a planted effect of known size. They are labelled SIMULATED everywhere and never enter the database, the training set or any real result.", SMALL),
      table([["Check", "Result"],
             ["Spillover test vs a naive analysis (10,641 real rows, 65 neighbours, planted trend 0.15 +/- 0.15)", "Naive is off by +0.38 at every effect size and 'finds' an effect in 100% of studies even at zero. The placebo test is off by -0.05, has 0% false alarms, finds a planted 0.10 in 48% and 0.25 or more in 100%."],
             ["Limit of that test", "If the effect reaches only about 20% of neighbours, the placebo test (median over neighbours) misses it: a 0.20 average effect is found in 6% of studies. Finding which neighbours matter is what GAIL attention is for."],
             ["Lag test on the real growth readings (extra attention planted 12-36 h after real Instagram posts)", "All-posts test (294 units, 55 creators): 0% false alarms, +10% of a normal day found in 7 of 8 runs. Strict test (65 units, 29 creators): +15% in 4 of 8, +25% in 8 of 8."],
             ["Neural GAIL acceptance (scripts/gail_acceptance.py, 26 Oct, old checkpoint)", "Failed 0 of 4 simulated checks. It has to be re-run on the NEW checkpoint after retraining."]],
            [70, 104]),
      p("Decision from Shimona: simulated rows may be added to GAIL training as long as real rows are always included. A generator with a hold-out safeguard is designed but not built; if used, report the real-only model next to the real-plus-simulated one, test on held-out real creators only, and never quote a spillover effect from the mixed model as a finding (it would learn the planted effect).", SMALL)]

s += [p("6. How to train (Eesha)", H2)]
s += bullets([
    "Apply the patch on <b>review2-eesha-model</b>: <i>git apply scripts/patches/train_prod_model_shared_brand.patch</i> (use <i>--ignore-whitespace</i> if line endings complain).",
    "The training files are in <b>exports/training_inputs_26oct/</b> on Shimona's laptop. That folder is <b>git-ignored (16 MB), so it is not on GitHub</b>: Shimona sends it (zip or Drive), or regenerate with <i>scripts/export_feature_store.py &lt;dir&gt;</i>, then <i>compute_training_pair_deltas.py</i>, then <i>scripts/make_shared_brand_targets.py --base &lt;dir&gt; --out &lt;dir2&gt;</i> (needs DATABASE_URL).",
    "Environment: <b>SHARED_BRAND=1</b>, <b>MENTION_EDGES=&lt;folder&gt;/mention_edges.json</b>, <b>SHARED_BRAND_TARGETS=&lt;folder&gt;/training_pair_deltas.json</b>. It runs on CPU (torch 2.6 CPU build). Time (not measured, an estimate from the code): the 100 GNN epochs on 390 nodes are quick, but a first run also builds creator features (up to 20 YouTube and 20 Instagram thumbnails per creator through CLIP and BERT on CPU), which can take roughly 30 to 90 minutes unless <i>models/feature_cache.pt</i> already exists on that machine; later runs reuse the cache.",
    "Do not quote the in-sample effect that training prints (memorised). Report held-out creators against always-zero and train-mean baselines.",
    "After training send Shimona the numbers; Claude then runs <i>check_live_scores.py</i>, <i>gail_acceptance.py</i>, <i>calibrate_fusion.py</i>, <i>backfill_fusion_scores.py</i> (dry run first) and scores held-out creators. Expect real spillover scores for about 95 of 150 creators (5 today); the other 55 have no link in our data and stay neutral.",
    "A spoken-sponsor scan of 175 videos (creators with no sponsored post found yet) finished on 27 Oct: 8 hits, all read in context, none is a sponsorship, so it added no events or links. With the feature cache in place a second run is much faster than the first.",
])

s += [p("7. What is left", H2),
      table([["Item", "Who", "Status"],
             ["GAIL retraining with the patch and flags", "Eesha", "Ready to start; files re-exported 27 Oct 14:00."],
             ["Model changes from the 'Next Steps' PDF: edge features in attention, effect over time (7/30/90 days), cross-fitted statistics with 5+ seeds, per-platform normalisation", "Eesha", "Not done; model code, untouched by Shimona's side. Known issues: saturated propensity (0.000 to 1.000), head ignores exposure, attention learns nothing, in-sample effect memorised."],
             ["Neural GAIL acceptance check and held-out scoring on the new checkpoint", "Claude", "After training."],
             ["Spoken-sponsor scan, then label pass, re-export, push", "Claude", "Scan running (about 13:30 IST); follow-up about 20 minutes."],
             ["Check the 30 batch-11 rows marked footer-only; 120 Hinglish comments", "Shimona", "Open (optional). These decide the weak-label accuracy and the Hinglish sentiment accuracy. Of the 45 caption labels approved unchecked on 24 Oct, 17 were read in context and removed as not sponsored; the other 28 (brand and code said aloud) stay."],
             ["Two posts that look sponsored but are not, and 17 spoken labels with only a bare word", "Done 27 Oct", "All 19 marked not sponsored on Shimona's yes (backups and undo scripts exist)."],
             ["Frontend changes and Docker for frontend + backend", "Claude / Shimona", "Docker files exist but were never run (no Docker on the laptop); the backend image leaves out ml/ and models/, so GAIL and CLIP/BERT scores would be neutral inside it. Frontend change list pending from Shimona."],
             ["Simulated rows in GAIL training (optional add-on)", "Claude, if wanted", "Parked."],
             ["Reddit refresh; lag re-test (29 Oct, 8-10 Nov); about 342 old Instagram posts still need counts (daily job, about 2 weeks)", "Claude / daily job", "Scheduled or manual as noted."],
             ["Stale 5 Oct alerts", "Claude", "Regenerate only after the retrain."]],
            [78, 24, 72]),
      p("Known limits to keep in the presentation", H2),
      ]
s += bullets([
    "The graph is mostly 'same brand' (576 of 605 shared-brand pairs are inside the 150) plus 7 real collaborations: it shows exposure to the same brands, not who influences whom. Label it exploratory.",
    "Links and training targets come from the same sponsorship events: score on held-out creators or the result will look better than it is.",
    "Only about 15 days of growth readings exist; Instagram is thin (78 of 150 creators, 39% of posts without counts); 55 of the 150 creators have no link and stay neutral.",
    "Weak-tier sponsorship labels are 81% of events and their true precision is uncertain; the detector's miss rate is unknown (no human-checked random sample of unflagged posts).",
    "Hinglish sentiment is only moderate (agreement +0.45 against Claude's labels, which are not human ground truth); human labels are pending.",
])

s += [p("Where to look", H2),
      p("Repository root: <b>CAPSTONE_NEXT_STEPS.md</b> (full living handoff), <b>DATA_HANDOFF_REPORT.md</b> (the 8-section data report), Analysis tab in the app (live results and simulated checks), models/*.json (every result file), scripts/ (every test is a script with its method in the header).", SMALL)]

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                        title="Handoff for Eesha - 27 Oct 2026", author="Shimona Sinha and Claude")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
