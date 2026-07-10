#!/bin/sh
set -e

mkdir -p "${DATA_DIR:-/storage/data}"

# Täglicher Datenabruf als eigener Prozess neben dem Webserver
python -u scheduler.py &

exec gunicorn --workers 2 --bind 0.0.0.0:80 wsgi:app
