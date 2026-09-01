#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
POSTGRES_VERSION=${POSTGRES_VERSION:-16.15}
POSTGRES_HOME="${PROJECT_ROOT}/.local/postgresql-${POSTGRES_VERSION}"
BUILD_ROOT="${PROJECT_ROOT}/.postgres/build-${POSTGRES_VERSION}"
ARCHIVE="${BUILD_ROOT}/postgresql-${POSTGRES_VERSION}.tar.bz2"
CHECKSUM="${ARCHIVE}.sha256"
SOURCE="${BUILD_ROOT}/postgresql-${POSTGRES_VERSION}"
DOWNLOAD_ROOT="https://download.postgresql.org/pub/source/v${POSTGRES_VERSION}"

if [ -x "${POSTGRES_HOME}/bin/postgres" ]; then
    "${POSTGRES_HOME}/bin/postgres" --version
    exit 0
fi

mkdir -p "${BUILD_ROOT}" "${POSTGRES_HOME}"
curl -fL "${DOWNLOAD_ROOT}/postgresql-${POSTGRES_VERSION}.tar.bz2" -o "${ARCHIVE}"
curl -fL "${DOWNLOAD_ROOT}/postgresql-${POSTGRES_VERSION}.tar.bz2.sha256" \
    -o "${CHECKSUM}"

expected=$(awk '{print $1}' "${CHECKSUM}")
actual=$(shasum -a 256 "${ARCHIVE}" | awk '{print $1}')
if [ -z "${expected}" ] || [ "${expected}" != "${actual}" ]; then
    echo "PostgreSQL archive checksum validation failed" >&2
    exit 1
fi

if [ ! -d "${SOURCE}" ]; then
    tar -xjf "${ARCHIVE}" -C "${BUILD_ROOT}"
fi

(
    cd "${SOURCE}"
    ./configure \
        --prefix="${POSTGRES_HOME}" \
        --without-icu \
        --without-readline \
        --without-zlib
    make -j4
    make install
)

"${POSTGRES_HOME}/bin/postgres" --version
