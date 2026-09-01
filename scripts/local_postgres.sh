#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    . "${PROJECT_ROOT}/.env"
    set +a
fi

POSTGRES_VERSION=${POSTGRES_VERSION:-16.15}
POSTGRES_HOME="${PROJECT_ROOT}/.local/postgresql-${POSTGRES_VERSION}"
POSTGRES_BIN="${POSTGRES_HOME}/bin"
POSTGRES_DATA="${PROJECT_ROOT}/.postgres/data"
POSTGRES_LOG="${PROJECT_ROOT}/.postgres/postgres.log"
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-sales_app}
POSTGRES_DB=${POSTGRES_DB:-sales_analytics}
POSTGRES_CONNECT_HOST=${POSTGRES_HOST:-127.0.0.1}
POSTGRES_BIND_HOST=${POSTGRES_CONNECT_HOST}
if [ "${POSTGRES_BIND_HOST}" = "localhost" ]; then
    POSTGRES_BIND_HOST=127.0.0.1
fi

require_postgres() {
    if [ ! -x "${POSTGRES_BIN}/postgres" ]; then
        echo "PostgreSQL ${POSTGRES_VERSION} is not installed at ${POSTGRES_HOME}" >&2
        exit 1
    fi
}

start_postgres() {
    require_postgres
    mkdir -p "${PROJECT_ROOT}/.postgres"
    if [ ! -f "${POSTGRES_DATA}/PG_VERSION" ]; then
        "${POSTGRES_BIN}/initdb" \
            --pgdata="${POSTGRES_DATA}" \
            --username="${POSTGRES_USER}" \
            --auth-local=trust \
            --auth-host=trust
    fi
    if ! "${POSTGRES_BIN}/pg_ctl" status --pgdata="${POSTGRES_DATA}" >/dev/null 2>&1; then
        "${POSTGRES_BIN}/pg_ctl" \
            --pgdata="${POSTGRES_DATA}" \
            --log="${POSTGRES_LOG}" \
            --options="-h ${POSTGRES_BIND_HOST} -p ${POSTGRES_PORT}" \
            --wait start
    fi
    if ! "${POSTGRES_BIN}/psql" \
        --host="${POSTGRES_CONNECT_HOST}" --port="${POSTGRES_PORT}" \
        --username="${POSTGRES_USER}" --dbname=postgres \
        --tuples-only --no-align \
        --command="SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'" \
        | grep -qx 1; then
        "${POSTGRES_BIN}/createdb" \
            --host="${POSTGRES_CONNECT_HOST}" --port="${POSTGRES_PORT}" \
            --username="${POSTGRES_USER}" "${POSTGRES_DB}"
    fi
    "${POSTGRES_BIN}/postgres" --version
    echo "PostgreSQL is ready on ${POSTGRES_CONNECT_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
}

stop_postgres() {
    require_postgres
    if [ -f "${POSTGRES_DATA}/PG_VERSION" ] \
        && "${POSTGRES_BIN}/pg_ctl" status --pgdata="${POSTGRES_DATA}" >/dev/null 2>&1; then
        "${POSTGRES_BIN}/pg_ctl" --pgdata="${POSTGRES_DATA}" --wait --mode=fast stop
    else
        echo "PostgreSQL is already stopped"
    fi
}

case "${1:-}" in
    up) start_postgres ;;
    down) stop_postgres ;;
    version) require_postgres; "${POSTGRES_BIN}/postgres" --version ;;
    *) echo "Usage: $0 {up|down|version}" >&2; exit 2 ;;
esac
