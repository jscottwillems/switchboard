-- Local honeypot number. Not a production enrollment.
INSERT INTO ops.operator_number (id, e164, label, status)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    '+15550001001',
    'dev-honeypot-1',
    'active'
);
