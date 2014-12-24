# redbot
#
# https://github.com/mnot/redbot

# Pull base image.
FROM ubuntu:14.10

MAINTAINER Julien Rottenberg <julien@rottenberg.info>

ENV        DEBIAN_FRONTEND noninteractive
ENV        PYTHONPATH      /redbot


# Install python requirements
RUN        apt-get install -y python-setuptools && easy_install thor


ADD        . /redbot


# Expose ports.
EXPOSE     80

# Define default command.
ENTRYPOINT /redbot/bin/webui.py 80 /redbot/share
