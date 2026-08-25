-- Seed realistic site records for local development and demos.
-- Safe to run repeatedly: existing rows are matched by the unique site code.

BEGIN;

INSERT INTO sites (
    id,
    code,
    name,
    plant_type,
    active,
    created_at,
    updated_at
)
VALUES
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000001',
        'HK-369',
        'HongKong Electronics Assembly Plant',
        'electronics',
        TRUE,
        '2026-01-05 08:00:00+00',
        '2026-08-24 08:00:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000002',
        'BK-ASIA-01',
        'Bangkok Precision Components Plant',
        'precision_manufacturing',
        TRUE,
        '2026-01-08 08:00:00+00',
        '2026-08-24 08:05:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000003',
        'NA-US-35',
        'Northern American Heavy Equipment Plant',
        'heavy_manufacturing',
        TRUE,
        '2026-01-12 08:00:00+00',
        '2026-08-24 08:10:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000004',
        'SA-US-33',
        'Southern American Parts Distribution Center',
        'distribution',
        TRUE,
        '2026-01-15 08:00:00+00',
        '2026-08-24 08:15:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000005',
        'MUM-ASIA-11',
        'Mumbai City Packaging Plant',
        'packaging',
        TRUE,
        '2026-02-03 08:00:00+00',
        '2026-08-24 08:20:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000006',
        'HCM-ASIA-12',
        'Ho Chi Minh City Food Processing Plant',
        'food_processing',
        TRUE,
        '2026-02-10 08:00:00+00',
        '2026-08-24 08:25:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000007',
        'SG-ASIA-22',
        'Singapore Automotive Components Center Plant',
        'automotive',
        TRUE,
        '2026-03-02 08:00:00+00',
        '2026-08-24 08:30:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000008',
        'HP-VN-01',
        'Hai Phong Marine Equipment Plant',
        'marine_equipment',
        TRUE,
        '2026-03-12 08:00:00+00',
        '2026-08-24 08:35:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000009',
        'MK-VN-01',
        'Mekong Delta Agricultural Machinery Plant',
        'agricultural_machinery',
        TRUE,
        '2026-04-01 08:00:00+00',
        '2026-08-24 08:40:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000010',
        'BJ-CN-01',
        'Beijing Consumer Goods Plant',
        'consumer_goods',
        TRUE,
        '2026-04-14 08:00:00+00',
        '2026-08-24 08:45:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000011',
        'BLR-ASIA-01',
        'Bangalore Materials Recovery Facility',
        'recycling',
        TRUE,
        '2026-05-04 08:00:00+00',
        '2026-08-24 08:50:00+00'
    ),
    (
        '4ce82a7b-9db7-4c16-8c2c-010000000012',
        'LA-US-01',
        'Los Angeles Legacy Pilot Manufacturing Site',
        'pilot_manufacturing',
        FALSE,
        '2025-06-01 08:00:00+00',
        '2026-07-31 17:00:00+00'
    )
ON CONFLICT (code) DO UPDATE
SET
    name = EXCLUDED.name,
    plant_type = EXCLUDED.plant_type,
    active = EXCLUDED.active,
    updated_at = EXCLUDED.updated_at;

COMMIT;
