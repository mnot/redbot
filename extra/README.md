# REDbot Deployment Extras

This directory holds sample files for running REDbot as a managed service:

* `redbot.service` — systemd unit for the `redbot_daemon` web interface.
* `redbot-gc.service` / `redbot-gc.timer` — periodic cleanup of saved tests.
* `redbot-sysusers.conf` — creates the system user the two units share.
* `config-docker.txt` — sample `config.txt` used by the container image.

The service files are only samples; review and adapt the paths, resource limits, and sandboxing to your system before installing them.


## Running REDbot as a systemd Service

REDbot can run as a standalone service, managed by [systemd](https://freedesktop.org/wiki/Software/systemd/). This offers a degree of sandboxing and resource management, as well as process monitoring (including a watchdog function).

Install REDbot with the `systemd` option so the watchdog integration is available:

> pipx install redbot[systemd]

The examples below assume REDbot is installed under `/opt/redbot`, matching the paths in the shipped units; adjust them to wherever you install it.

### Create the service user

Both `redbot.service` and `redbot-gc.service` run as a static `redbot` system user rather than using systemd's `DynamicUser`. A dynamic user gets a different ephemeral UID per unit, so the daemon and the cleanup job could not share ownership of the saved-tests directory. The static user lets the timer remove files the daemon wrote.

Install the shipped sysusers snippet and apply it, as root:

~~~ bash
> cp extra/redbot-sysusers.conf /etc/sysusers.d/redbot.conf
> systemd-sysusers
~~~

### Install the units

Copy the unit files into the appropriate directory (on most systems, `/etc/systemd/system/`):

~~~ bash
> cp extra/redbot.service extra/redbot-gc.service extra/redbot-gc.timer /etc/systemd/system/
~~~

Modify them appropriately, then reload systemd and enable the daemon and the cleanup timer, as root:

~~~ bash
> systemctl daemon-reload
> systemctl enable --now redbot
> systemctl enable --now redbot-gc.timer
~~~

By default, REDbot will listen on localhost port 8000. This can be adjusted in `config.txt`. Running REDbot behind a reverse proxy is recommended, if it is to be exposed to the Internet.

### Saved tests and cleanup

If you want to allow people to save test results, set `save_dir` in `config.txt` to a directory the REDbot process can write to. Because `redbot.service` sets `PrivateTmp=true`, the default `/tmp/redbot/` is not shared outside the unit; point `save_dir` at the state directory the unit provisions instead (`StateDirectory=redbot` creates `/var/lib/redbot`, owned by the `redbot` user).

Saved tests are garbage-collected out of process by `redbot_gc <config>`, not by the daemon. `redbot-gc.timer` triggers `redbot-gc.service`, which runs that command as the same `redbot` user. The timer's `OnUnitActiveSec` should match `gc_mins` in `config.txt` (both default to 10 minutes); a run won't stack on a stalled one, since systemd skips activation while the oneshot is still active.

Cleanup only removes files that are actually eligible: saved files persist for `save_days` (default 30 days), and unsaved scratch files persist for `no_save_mins` (default 20 minutes). If you disable saving (comment out `save_dir`), you can skip enabling `redbot-gc.timer`.
