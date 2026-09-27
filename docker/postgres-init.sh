#!/bin/sh
# Runs once when the Postgres volume is first created.
# lookbook_owner owns the schema and runs migrations; lookbook_app is what the API and workers use
# (data read/write only: no DDL, can't drop or alter tables).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<SQL
CREATE ROLE lookbook_owner LOGIN PASSWORD '${DB_OWNER_PASSWORD}';
CREATE ROLE lookbook_app LOGIN PASSWORD '${DB_APP_PASSWORD}' CONNECTION LIMIT 60;
CREATE DATABASE lookbook OWNER lookbook_owner;
\connect lookbook
CREATE EXTENSION IF NOT EXISTS vector;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CREATE, USAGE ON SCHEMA public TO lookbook_owner;
SQL
