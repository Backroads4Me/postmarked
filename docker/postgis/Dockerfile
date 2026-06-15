FROM postgres:16-bookworm

# Install PostGIS from the PGDG repository configured by the official Postgres
# image. Existing databases keep their registered extension version until an
# explicit ALTER EXTENSION UPDATE; new databases initialize with the packaged
# version through init-postgis.sql.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

COPY init-postgis.sql /docker-entrypoint-initdb.d/10-postgis.sql
