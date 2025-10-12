#!/bin/bash
# Actuation Health Monitoring Script
# Purpose: Monitor parking actuation reliability at scale
# Usage: ./monitor-actuation-health.sh [time_window_minutes]

set -euo pipefail

TIME_WINDOW=${1:-60}  # Default: last 60 minutes
ALERT_THRESHOLD=95    # Alert if success rate < 95%

echo "🔍 Parking Actuation Health Report"
echo "Time Window: Last ${TIME_WINDOW} minutes"
echo "Alert Threshold: ${ALERT_THRESHOLD}% success rate"
echo "================================================"
echo ""

# Overall Actuation Statistics
echo "📊 Overall Statistics (Last ${TIME_WINDOW} min)"
echo "------------------------------------------------"

sudo docker compose exec -T postgres-primary psql -U parking_user -d parking_platform <<SQL
SELECT
    COUNT(*) as total_actuations,
    SUM(CASE WHEN downlink_sent = true THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN downlink_sent = false THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN downlink_sent = true THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct,
    ROUND(AVG(response_time_ms)::numeric, 1) as avg_response_ms,
    ROUND(MIN(response_time_ms)::numeric, 1) as min_response_ms,
    ROUND(MAX(response_time_ms)::numeric, 1) as max_response_ms
FROM parking_operations.actuations
WHERE created_at > NOW() - INTERVAL '${TIME_WINDOW} minutes';
SQL

echo ""
echo "📍 Per-Space Success Rates"
echo "------------------------------------------------"

sudo docker compose exec -T postgres-primary psql -U parking_user -d parking_platform <<SQL
SELECT
    s.space_name,
    s.current_state,
    COUNT(a.actuation_id) as actuations,
    SUM(CASE WHEN a.downlink_sent = true THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN a.downlink_sent = true THEN 1 ELSE 0 END) / COUNT(a.actuation_id), 1) as success_pct,
    ROUND(AVG(a.response_time_ms)::numeric, 1) as avg_ms,
    MAX(a.created_at) as last_actuation
FROM parking_spaces.spaces s
LEFT JOIN parking_operations.actuations a ON a.display_deveui = s.display_device_deveui
WHERE a.created_at > NOW() - INTERVAL '${TIME_WINDOW} minutes'
GROUP BY s.space_id, s.space_name, s.current_state
ORDER BY success_pct ASC, actuations DESC;
SQL

echo ""
echo "❌ Failed Actuations (Last ${TIME_WINDOW} min)"
echo "------------------------------------------------"

sudo docker compose exec -T postgres-primary psql -U parking_user -d parking_platform <<SQL
SELECT
    TO_CHAR(a.created_at, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
    s.space_name,
    a.trigger_type,
    a.previous_state || ' → ' || a.new_state as transition,
    a.downlink_error as error
FROM parking_operations.actuations a
JOIN parking_spaces.spaces s ON a.display_deveui = s.display_device_deveui
WHERE a.created_at > NOW() - INTERVAL '${TIME_WINDOW} minutes'
  AND a.downlink_sent = false
ORDER BY a.created_at DESC
LIMIT 10;
SQL

echo ""
echo "================================================"
echo "Report generated: $(date)"
