# Database seed scripts

Run migrations before loading seed data:

```powershell
uv run alembic upgrade head
```

## Seed sites

With PostgreSQL running through Docker Compose:

```powershell
Get-Content -Raw scripts/seed_sites.sql |
    docker compose exec -T database psql -U postgres -d galaxy_universal
```

Or, with a locally installed `psql` client:

```powershell
psql "postgresql://postgres:1234@localhost:5433/galaxy_universal" `
    -f scripts/seed_sites.sql
```

The script inserts 12 sites and explicitly supplies a value for every column in the `sites`
table. It is safe to rerun: rows with an existing `code` are updated, while their existing `id` and
`created_at` values are preserved to avoid disrupting related records.

## Seed assets

Load the site data first, then run:

```powershell
Get-Content -Raw scripts/seed_assets.sql |
    docker compose exec -T database psql -U postgres -d galaxy_universal
```

The script inserts 10 assets and supplies values for every column in the `assets` table. Each
`site_id` is looked up from `sites.code`, ensuring the asset uses the UUID currently stored for that
site. Existing asset codes are updated safely when the script is rerun.

## Seed work orders

Load the site and asset data first, then run:

```powershell
Get-Content -Raw scripts/seed_work_orders.sql |
    docker compose exec -T database psql -U postgres -d galaxy_universal
```

The script inserts 10 work orders and supplies values for every column in the `work_orders` table.
Each lookup checks the expected site code and asset code together, preventing a work order from being
linked to an asset at the wrong site. Existing work-order codes are updated safely on reruns.
