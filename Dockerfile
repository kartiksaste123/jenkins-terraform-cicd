# ---------- Student Task Tracker (Flask) ----------
# Small, secure image: slim Python base, non-root user, gunicorn server.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

# Install dependencies first so this layer is cached between builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app/ ./app/

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

ARG BUILD_NUMBER=local
ENV BUILD_NUMBER=${BUILD_NUMBER}
LABEL org.opencontainers.image.title="student-task-tracker" \
      org.opencontainers.image.authors="Kartik Saste" \
      org.opencontainers.image.source="https://github.com/kartiksaste123/jenkins-terraform-cicd"

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:5000/health')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app.app:app"]
