-- Seed work orders for the 10 assets added by seed_assets.sql.
-- The site and asset lookups verify each expected site/asset relationship.
-- Safe to run repeatedly: existing rows are matched by the unique work-order code.

BEGIN;

INSERT INTO work_orders (
    id,
    site_id,
    asset_id,
    code,
    title,
    description,
    priority,
    status,
    work_type,
    due_at,
    created_at,
    updated_at
)
VALUES
    (
        'b77e9000-0000-4000-8000-000000000001',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'PLANT-HCM' AND a.code = 'AST-HCM-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'PLANT-HCM' AND a.code = 'AST-HCM-001'
        ),
        'WO-HCM-0101',
        'Inspect stamping press hydraulic circuit',
        'Inspect hoses, fittings, pressure valves, and the hydraulic reservoir for leaks.',
        'high',
        'open',
        'preventive',
        '2026-08-28 08:00:00+00',
        '2026-08-24 10:00:00+00',
        '2026-08-24 10:00:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000002',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'PLANT-HN' AND a.code = 'AST-HN-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'PLANT-HN' AND a.code = 'AST-HN-001'
        ),
        'WO-HN-0101',
        'Calibrate assembly robot position sensors',
        'Verify axis repeatability and recalibrate all position sensors to factory tolerance.',
        'medium',
        'pending',
        'preventive',
        '2026-08-30 08:00:00+00',
        '2026-08-24 10:05:00+00',
        '2026-08-24 10:05:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000003',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'HK-369' AND a.code = 'AST-HK-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'HK-369' AND a.code = 'AST-HK-001'
        ),
        'WO-HK-0101',
        'Replace placement machine feeder nozzle',
        'Replace the worn feeder nozzle and validate component placement accuracy.',
        'critical',
        'open',
        'corrective',
        '2026-08-26 08:00:00+00',
        '2026-08-24 10:10:00+00',
        '2026-08-24 10:10:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000004',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'BK-ASIA-01' AND a.code = 'AST-BK-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'BK-ASIA-01' AND a.code = 'AST-BK-001'
        ),
        'WO-BK-0101',
        'Correct CNC spindle alignment',
        'Realign the spindle, inspect bearings, and verify runout after lubrication.',
        'critical',
        'in_progress',
        'corrective',
        '2026-08-25 08:00:00+00',
        '2026-08-24 10:15:00+00',
        '2026-08-24 10:15:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000005',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'NA-US-35' AND a.code = 'AST-NA-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'NA-US-35' AND a.code = 'AST-NA-001'
        ),
        'WO-NA-0101',
        'Service industrial air compressor',
        'Inspect vibration, replace the intake filter, and confirm operating pressure.',
        'high',
        'open',
        'preventive',
        '2026-08-29 08:00:00+00',
        '2026-08-24 10:20:00+00',
        '2026-08-24 10:20:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000006',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'SA-US-33' AND a.code = 'AST-SA-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'SA-US-33' AND a.code = 'AST-SA-001'
        ),
        'WO-SA-0101',
        'Test retrieval crane safety controls',
        'Test emergency stops, travel limits, interlocks, and overload protection.',
        'high',
        'pending',
        'preventive',
        '2026-09-01 08:00:00+00',
        '2026-08-24 10:25:00+00',
        '2026-08-24 10:25:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000007',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'MUM-ASIA-11' AND a.code = 'AST-MUM-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'MUM-ASIA-11' AND a.code = 'AST-MUM-001'
        ),
        'WO-MUM-0101',
        'Recommission automatic cartoning machine',
        'Inspect guards and sensors, lubricate the drive, and complete a dry production run.',
        'medium',
        'open',
        'corrective',
        '2026-08-31 08:00:00+00',
        '2026-08-24 10:30:00+00',
        '2026-08-24 10:30:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000008',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'HCM-ASIA-12' AND a.code = 'AST-HCM-FP-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'HCM-ASIA-12' AND a.code = 'AST-HCM-FP-001'
        ),
        'WO-HCM-FP-0101',
        'Sanitize and calibrate pasteurization line',
        'Complete the sanitation cycle and calibrate temperature and flow sensors.',
        'critical',
        'in_progress',
        'preventive',
        '2026-08-25 12:00:00+00',
        '2026-08-24 10:35:00+00',
        '2026-08-24 10:35:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000009',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'SG-ASIA-22' AND a.code = 'AST-SG-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'SG-ASIA-22' AND a.code = 'AST-SG-001'
        ),
        'WO-SG-0101',
        'Calibrate test bench torque sensors',
        'Calibrate all torque channels and record results against the certified reference.',
        'high',
        'pending',
        'preventive',
        '2026-09-02 08:00:00+00',
        '2026-08-24 10:40:00+00',
        '2026-08-24 10:40:00+00'
    ),
    (
        'b77e9000-0000-4000-8000-000000000010',
        (
            SELECT s.id
            FROM sites AS s
            JOIN assets AS a ON a.site_id = s.id
            WHERE s.code = 'HP-VN-01' AND a.code = 'AST-HP-001'
        ),
        (
            SELECT a.id
            FROM assets AS a
            JOIN sites AS s ON s.id = a.site_id
            WHERE s.code = 'HP-VN-01' AND a.code = 'AST-HP-001'
        ),
        'WO-HP-0101',
        'Replace dynamometer cooling pump seal',
        'Replace the leaking pump seal, refill coolant, and perform a pressure test.',
        'critical',
        'in_progress',
        'corrective',
        '2026-08-27 08:00:00+00',
        '2026-08-24 10:45:00+00',
        '2026-08-24 10:45:00+00'
    )
ON CONFLICT (code) DO UPDATE
SET
    site_id = EXCLUDED.site_id,
    asset_id = EXCLUDED.asset_id,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    work_type = EXCLUDED.work_type,
    due_at = EXCLUDED.due_at,
    updated_at = EXCLUDED.updated_at;

COMMIT;
