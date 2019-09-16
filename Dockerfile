FROM python:3-alpine
WORKDIR /redbot
COPY . /redbot

RUN pip install --trusted-host pypi.python.org thor markdown netaddr

EXPOSE 8000

ENV PYTHONPATH /redbot
ENV PYTHONUNBUFFERED true
ENTRYPOINT ["python", "bin/redbot_daemon.py", "extra/config-docker.txt"]
