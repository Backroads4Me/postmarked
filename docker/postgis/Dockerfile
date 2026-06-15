FROM postgres:16-bookworm

# Pin PostGIS to the 3.4 series to match the upstream postgis/postgis:16-3.4
# image this build replaced. Existing volumes have their postgis extension
# registered at 3.4, and PostGIS does not support downgrade, so a 3.3 (Debian
# bookworm default) or newer-than-installed library would fail on startup.
# The official postgres image already configures the PGDG apt repo, which
# carries the 3.4 packages. Revisit the pin when intentionally upgrading the
# extension across all volumes (CREATE EXTENSION ... UPDATE / ALTER EXTENSION).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3=3.4.* \
        postgresql-16-postgis-3-scripts=3.4.* \
    && rm -rf /var/lib/apt/lists/*

COPY init-postgis.sql /docker-entrypoint-initdb.d/10-postgis.sql
