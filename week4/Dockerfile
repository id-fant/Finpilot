# FinPilot week 4 — deploy image for the week2 Django backend.
#
# Build from the REPO ROOT so the build context can see week2/:
#   docker build -f week4/Dockerfile -t finpilot .

FROM node:22-slim AS frontend
WORKDIR /frontend
COPY week4/frontend/package.json week4/frontend/package-lock.json ./
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then \
      export NODE_EXTRA_CA_CERTS=/run/secrets/ca_bundle; \
    fi; \
    npm ci --no-audit --no-fund
COPY week4/frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/week2

# WHY copy requirements first: this layer is cached until requirements.txt
# changes, so day-to-day code edits don't trigger a full dependency reinstall.
COPY week2/requirements.txt ./
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then \
      export PIP_CERT=/run/secrets/ca_bundle; \
    fi; \
    pip install -r requirements.txt

# Application code and the framework-free sibling packages imported by
# settings.py. Keep the repository layout so those paths stay identical.
COPY week2/ /app/week2/
COPY week3/ /app/week3/
COPY week4/broker/ /app/week4/broker/
COPY --from=frontend /frontend/dist/ /app/week2/frontend_dist/

# WHY a non-root user: never run a web process as root — if the app is
# compromised, the blast radius is limited to this unprivileged user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Railway overrides this with its own startCommand (see railway.toml); this
# CMD is what `docker run` and docker-compose use locally.
CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn finpilot.asgi:application --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers"]
