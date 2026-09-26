#!/bin/sh
set -eu
umask 077
cd /opt/day18-agent
exec >> /var/log/day18/cron.log 2>&1
exec .venv/bin/python -B -m day18.cli \
  --env-file /etc/day18/day18.env \
  --db /var/lib/day18/day18.sqlite3 \
  --model deepseek/deepseek-v4.1-flash \
  --verified-visible-budget 20000 scheduled
