#! /usr/bin/env bash

set -e
set -x

# Create migrations
alembic revision --autogenerate
# Run migrations
alembic upgrade head

