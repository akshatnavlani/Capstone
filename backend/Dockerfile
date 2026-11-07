# Backend API image (numpy added 1 Nov 2026: creator_features.py and temporal.py import it at the top, so the image did not start without it).
# Build context = repo root (must contain backend/ and models/).
# ml/ and the GAIL checkpoint are intentionally NOT baked in: without them the spillover
# service falls back to placeholder basis by design, so this image proves the
# API layer boots and serves. Full GAIL wiring is verified by pytest
# (backend/tests/test_spillover.py) plus the live check in Track C's HANDOFF.
# Python 3.12: the version the backend and its tests were run on.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
# The result files the API reads (small JSON, no torch needed). Paths match backend/app: Path(__file__).parents[2] / "models" = /srv/models.
# Without them the passport, the Insights page, the influencer photos, analysis tab, platform comparison, promotion and sentiment blocks would be empty inside Docker.
COPY models/analysis_dashboard.json models/creator_passport.json models/platform_pairs.json models/promotion_behaviour.json models/temporal_sentiment.json models/creator_photos.json models/gail_real_results.json models/semisynth_new_graph_effect0.json models/semisynth_new_graph_effect1.json models/power_analysis.json models/fusion_simulation.json models/e4_e5_results.json models/published_baselines_eesha.json models/creator_value.csv ./models/
WORKDIR /srv/backend
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5   CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
