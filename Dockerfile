FROM python:3-slim-bookworm

# Notes:
# Locales are needed for the redbot_daemon.py to run
# locale.normalize(conf["redbot"]["lang"]) = "en_US.ISO8859-1"
# by default we will install all standard en_US locales (en_US.ISO-8859-1, en_US.ISO-8859-15, en_US.UTF-8)

# Install necessary Debian packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libffi-dev \
    build-essential \
    openssl \
    locales \
    pipx \
    && sed -i '/^# *en_US/s/^# *//' /etc/locale.gen \
    && locale-gen \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /redbot
COPY . /redbot
ENV PIPX_HOME /usr/local/share/pipx
ENV PIPX_BIN_DIR /usr/local/bin
RUN pipx install /redbot

EXPOSE 8000

ENV PYTHONUNBUFFERED true
ENTRYPOINT ["/usr/local/bin/redbot_daemon"]
CMD ["extra/config-docker.txt"]
