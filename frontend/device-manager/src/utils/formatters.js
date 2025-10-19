/**
 * utils/formatters.js
 * Version: 1.0.0
 * Last Updated: 2025-08-08 12:05 UTC+2
 * Changelog:
 * - Add formatLastSeen() and formatDateTime() for shared UI formatting
 */

/**
 * Human-ish "last seen" formatter:
 * - <1m     -> "Just now"
 * - <60m    -> "Xm ago"
 * - <24h    -> "Xh ago"
 * - >=24h   -> "Xd ago"
 * - falsy   -> "Never"
 */
export function formatLastSeen(timestamp) {
  if (!timestamp) return 'Never';
  try {
    const now = Date.now();
    const t = new Date(timestamp).getTime();
    if (Number.isNaN(t)) return '—';
    const diffMs = now - t;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
    return `${Math.floor(mins / 1440)}d ago`;
  } catch {
    return '—';
  }
}

/**
 * Safe datetime pretty-printer using locale.
 * Returns fallback (default '—') when null/invalid.
 */
export function formatDateTime(timestamp, fallback = '—') {
  if (!timestamp) return fallback;
  const d = new Date(timestamp);
  if (isNaN(d.getTime())) return fallback;
  return d.toLocaleString();
}
