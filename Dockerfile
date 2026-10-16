# Build stage: compiler and headers live here only, and never reach the final image.
FROM python:3-slim-bookworm AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libffi-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
RUN python -m venv /opt/redbot-venv && \
    /opt/redbot-venv/bin/pip install --no-cache-dir /src


FROM python:3-slim-bookworm

# Notes:
# Locales are needed for the redbot_daemon.py to run
# locale.normalize(conf["redbot"]["lang"]) = "en_US.ISO8859-1"
# by default we will install all standard en_US locales (en_US.ISO-8859-1, en_US.ISO-8859-15, en_US.UTF-8)

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openssl \
    locales \
    && sed -i '/^# *en_US/s/^# *//' /etc/locale.gen \
    && locale-gen \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# The daemon fetches and parses arbitrary remote content, so it runs unprivileged.
# /var/lib/redbot is a place for save_dir; mount a volume there to keep saved tests.
RUN groupadd --system redbot && \
    useradd --system --gid redbot --no-create-home --shell /usr/sbin/nologin redbot && \
    install -d -o redbot -g redbot /var/lib/redbot

COPY --from=build /opt/redbot-venv /opt/redbot-venv

WORKDIR /redbot
COPY . /redbot

EXPOSE 8000

ENV PYTHONUNBUFFERED=true
USER redbot
ENTRYPOINT ["/opt/redbot-venv/bin/redbot_daemon"]
CMD ["extra/config-docker.txt"]
