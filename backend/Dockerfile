# A2 backend API smoke image. Build context = branch root (must contain backend/).
# ml/ + models/ are intentionally NOT baked in: without them the spillover
# service falls back to placeholder basis by design, so this smoke proves the
# API layer boots and serves. Full GAIL wiring is verified by pytest
# (backend/tests/test_spillover.py) plus the live check in Track C's HANDOFF.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
WORKDIR /srv/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
