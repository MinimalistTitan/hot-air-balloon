-- Seed realistic asset records for local development and demos.
-- Each site_id is resolved from the current sites table by its unique code.
-- Safe to run repeatedly: existing rows are matched by the unique asset code.

BEGIN;

INSERT INTO assets (
    id,
    site_id,
    code,
    name,
    category,
    criticality,
    status,
    created_at,
    updated_at
)
VALUES
    (
        'a55e7000-0000-4000-8000-000000000001',
        (SELECT id FROM sites WHERE code = 'PLANT-HCM'),
        'AST-HCM-001',
        'Hydraulic Stamping Press',
        'production_machine',
        'high',
        'running',
        '2026-02-02 01:00:00+00',
        '2026-08-24 09:00:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000002',
        (SELECT id FROM sites WHERE code = 'PLANT-HN'),
        'AST-HN-001',
        'Automated Assembly Robot',
        'robotics',
        'high',
        'running',
        '2026-02-05 01:00:00+00',
        '2026-08-24 09:05:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000003',
        (SELECT id FROM sites WHERE code = 'HK-369'),
        'AST-HK-001',
        'Surface Mount Placement Machine',
        'electronics_assembly',
        'critical',
        'running',
        '2026-02-10 01:00:00+00',
        '2026-08-24 09:10:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000004',
        (SELECT id FROM sites WHERE code = 'BK-ASIA-01'),
        'AST-BK-001',
        'Five-Axis CNC Machining Center',
        'cnc_machine',
        'critical',
        'maintenance',
        '2026-02-14 01:00:00+00',
        '2026-08-24 09:15:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000005',
        (SELECT id FROM sites WHERE code = 'NA-US-35'),
        'AST-NA-001',
        'Industrial Air Compressor',
        'utility_equipment',
        'high',
        'running',
        '2026-02-18 01:00:00+00',
        '2026-08-24 09:20:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000006',
        (SELECT id FROM sites WHERE code = 'SA-US-33'),
        'AST-SA-001',
        'Automated Storage and Retrieval Crane',
        'warehouse_equipment',
        'medium',
        'running',
        '2026-02-22 01:00:00+00',
        '2026-08-24 09:25:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000007',
        (SELECT id FROM sites WHERE code = 'MUM-ASIA-11'),
        'AST-MUM-001',
        'Automatic Cartoning Machine',
        'packaging_machine',
        'medium',
        'idle',
        '2026-03-02 01:00:00+00',
        '2026-08-24 09:30:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000008',
        (SELECT id FROM sites WHERE code = 'HCM-ASIA-12'),
        'AST-HCM-FP-001',
        'Continuous Pasteurization Line',
        'food_processing_line',
        'critical',
        'running',
        '2026-03-08 01:00:00+00',
        '2026-08-24 09:35:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000009',
        (SELECT id FROM sites WHERE code = 'SG-ASIA-22'),
        'AST-SG-001',
        'Automotive Component Test Bench',
        'testing_equipment',
        'high',
        'running',
        '2026-03-12 01:00:00+00',
        '2026-08-24 09:40:00+00'
    ),
    (
        'a55e7000-0000-4000-8000-000000000010',
        (SELECT id FROM sites WHERE code = 'HP-VN-01'),
        'AST-HP-001',
        'Marine Engine Dynamometer',
        'testing_equipment',
        'high',
        'maintenance',
        '2026-03-18 01:00:00+00',
        '2026-08-24 09:45:00+00'
    )
ON CONFLICT (code) DO UPDATE
SET
    site_id = EXCLUDED.site_id,
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    criticality = EXCLUDED.criticality,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at;

COMMIT;
