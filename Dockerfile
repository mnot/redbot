FROM python:3-slim-bookworm

# Install necessary Debian packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libffi-dev \
    build-essential \
    openssl \
    locales \
    && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen \ 
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
