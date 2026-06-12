# Postmarked

Postmarked is a self-hosted travel journal for sharing trips, stops, updates, photos, and videos with family and friends. It works for road trips, long weekends, international travel, full-time travel, or any journey you want to share privately on your own server.

It is meant to be simple: run it, sign in, create a trip, post updates along the way, and let visitors follow along.

## Features

- Public trip pages, timeline, stops, posts, photos, and videos.
- Admin UI for trips, stops, posts, media, users, site text, and settings.
- Public/private visibility controls.
- Email notifications for new public updates.
- ZIP backup export and destructive restore.
- Docker Compose deployment.
- RV Trip Wizard `.xlsx` import with preview and apply for RV travelers.

## Screenshot

![Postmarked trip page](screenshots/trip.png)

## Install

```bash
cp .env.example .env
docker compose up -d
```

Before deploying, edit `.env` and set production values for:

- `SECRET_KEY`
- `APP_BASE_URL`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `POSTGRES_PASSWORD`

Open the admin UI:

```text
http://localhost:4321/admin
```

Sign in with `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.

## Storage

Media files are mounted from `MEDIA_DIR`:

```env
MEDIA_DIR=./data
```

The database uses Docker's `db_data` volume by default.

## Backup And Restore

In the admin UI, use Backup to export or restore an instance.

- Export downloads a ZIP with database records and media files.
- Restore uploads a ZIP and replaces the current instance with its contents.
- Restore is destructive and has no preview step.

## RV Trip Wizard Import

In the admin UI, use the Import page to upload an RV Trip Wizard `.xlsx` export. Review the preview diff, then apply it.

Imported stops are created as private drafts. Stops from a previous RV Trip Wizard import that are missing from the latest file are archived rather than deleted.

## License

[GPL v3](LICENSE)

## Support

Postmarked is free and open source.

If it helped you share your travels, please star the repository so other self-hosters can find it.

Sponsorships are appreciated, but never expected.

[![Star Repository](https://img.shields.io/badge/%E2%AD%90%20Star%20this%20Repo-GitHub-lightgrey?logo=github&logoColor=black)](https://github.com/Backroads4Me/postmarked)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-EA4AAA?logo=github-sponsors&logoColor=white)](https://github.com/sponsors/Backroads4Me)
