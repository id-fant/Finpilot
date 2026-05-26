# FinPilot week 4 — deploy image for the week2 Django backend.
#
# Build from the REPO ROOT so the build context can see week2/:
#   docker build -f week4/Dockerfile -t finpilot .

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# WHY copy requirements first: this layer is cached until requirements.txt
# changes, so day-to-day code edits don't trigger a full dependency reinstall.
COPY week2/requirements.txt ./
RUN pip install -r requirements.txt gunicorn

# Application code.
COPY week2/ ./

# WHY a non-root user: never run a web process as root — if the app is
# compromised, the blast radius is limited to this unprivileged user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Railway overrides this with its own startCommand (see railway.toml); this
# CMD is what `docker run` and docker-compose use locally.
CMD ["gunicorn", "finpilot.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
