# Postmarked operations guide

This guide covers persistent storage, backups, restore, upgrades, and optional
Cloudflare caching for a self-hosted Postmarked instance.

## Storage

Postmarked stores persistent data under `MEDIA_DIR` and limits individual
uploads with `MAX_UPLOAD_FILE_MIB`:

```env
MEDIA_DIR=./data
MAX_UPLOAD_FILE_MIB=500
```

The default 500 MiB limit supports typical phone photos and short videos while
bounding disk and processing cost. Raise it for longer or 4K video uploads.

| Subdirectory | Contents | Back up? |
| --- | --- | --- |
| `derivatives` | Processed media served to the site | **Yes** |
| `backups` | Scheduled and on-demand `pg_dump` database dumps | **Yes** |
| `originals` | Source uploads when `MEDIA_KEEP_ORIGINALS=true` | Optional |
| `db_data` | Live PostgreSQL data directory | **No**—use database dumps |

For disaster recovery, copy `derivatives` and `backups`, plus `originals` when
original uploads are retained. Do not file-copy the live `db_data` directory;
the database may be mid-write. The `pg_dump` files in `backups` provide a
consistent database snapshot.

## Backup and restore

The admin **Backup** page exports or restores a complete instance. This is a
convenience tool for small sites and instance migration, not the routine
disaster-recovery path for a mature media library.

- **Export** downloads a ZIP containing application data and all processed
  media derivatives. Original uploads are not included because the derivatives
  are sufficient to serve the site.
- **Restore** uploads a ZIP and replaces the current application data and
  media. Restore is destructive and has no preview step.
- **Large libraries** produce large export ZIPs because every processed media
  derivative is included.

For routine disaster recovery, Postmarked writes database dumps to
`${MEDIA_DIR}/backups`:

- A daily snapshot runs at `BACKUP_HOUR`:`BACKUP_MINUTE` in the server's time
  zone and retains the latest `BACKUP_RETENTION` dumps.
- **Snapshot Database Now** on the admin Backup page creates a dump on demand.
- Database dumps do not contain media. Copy `derivatives` separately with a
  file backup tool such as `rsync`, `restic`, or `borg`.

## Upgrades

Pull the current images and recreate the stack:

```bash
docker compose pull && docker compose up -d
```

### Database collation and index integrity

PostgreSQL sorts text using the system collation library. When a database image
provides a different library version, stored index ordering can become stale.
The visible symptom can be a published post that returns 404 on its own URL
while still appearing in trip and stop listings.

Postmarked checks for collation changes on startup and rebuilds affected
indexes before serving traffic. Set `REINDEX_ON_COLLATION_CHANGE=false` only
when a large database requires a separately scheduled rebuild; the startup log
then prints the SQL to run.

Inspect the indexes manually with:

```bash
./scripts/check-collation.sh
```

Add `--repair` to rebuild anything the check flags.

## Serving behind Cloudflare

When Cloudflare proxies a Postmarked instance, create the following cache rules
under **Caching → Cache Rules**. Keep them in this order.

### 1. Bypass MP4 caching

Bypass the edge cache so iOS and Safari range requests reach the origin:

```text
(http.request.uri.path strict wildcard r"/media/*/*.mp4")
```

Set **Cache eligibility** to **Bypass cache**.

### 2. Cache processed images

```text
(http.request.uri.path strict wildcard r"/media/*/*.webp") or (http.request.uri.path strict wildcard r"/media/*/*.avif") or (http.request.uri.path strict wildcard r"/media/*/*.jpg")
```

Use these settings:

- Cache eligibility: **Eligible for cache**
- Edge TTL: **Respect origin TTL**
- Browser TTL: **Respect origin TTL**

### 3. Cache public home and timeline pages

```text
(http.request.uri.path eq "/" or http.request.uri.path eq "/timeline") and not http.cookie contains "postmarked_session"
```

Use **Eligible for cache** and **Respect origin TTL** for both edge and browser
TTL. Authenticated administrators carry the `postmarked_session` cookie and
bypass this rule. Postmarked's response header provides a 30-second freshness
window with background revalidation.

When the Cloudflare zone serves multiple hostnames, prepend
`http.host eq "yourdomain.tld" and ` to scope the expression. Purge any MP4s
cached before adding the bypass rule.

See Cloudflare's
[MP4 troubleshooting guide](https://developers.cloudflare.com/cache/troubleshooting/mp4-videos-on-ios-and-safari/)
for the range-request behavior. Verify a cache rule by requesting the same URL
twice and checking `cf-cache-status`:

```bash
curl -sI https://yourdomain.tld/ | grep -i cf-cache-status
```
