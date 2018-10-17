# redbot
#
# https://github.com/mnot/redbot

# Pull base image.
FROM ubuntu:14.10

MAINTAINER Julien Rottenberg <julien@rottenberg.info>

ENV        DEBIAN_FRONTEND noninteractive
ENV        PYTHONPATH      /redbot


# Install python requirements
RUN        apt-get update && apt-get install -y python-setuptools make phantomjs && easy_install thor selenium

ADD        . /redbot

RUN        make --directory=/redbot/test


# Expose ports.
EXPOSE     80

# Define default command.
ENTRYPOINT /redbot/bin/webui.py 80 /redbot/redbot/assets
