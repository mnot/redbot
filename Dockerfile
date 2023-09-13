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
    && sed -i '/^# *en_US/s/^# *//' /etc/locale.gen \
    && locale-gen \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /redbot
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt
COPY . /redbot

EXPOSE 8000

ENV PYTHONPATH /redbot
ENV PYTHONUNBUFFERED true
ENTRYPOINT ["python"] 
CMD ["bin/redbot_daemon.py", "extra/config-docker.txt"]
