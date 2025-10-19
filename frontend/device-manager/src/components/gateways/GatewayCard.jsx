import { formatLastSeen, formatDateTime } from '../../utils/formatters.js';
/**
 * GatewayCard.jsx
 * Version: 1.0.0
 * Last Updated: 2025-08-08 11:05 UTC+2
 * Changelog:
 * - Initial gateway card with status/last-seen and actions
 */

import { useState } from 'react';
import { updateGateway, archiveGateway } from '../../services/gateways';

const badge = (status) => {
  const s = (status || 'UNKNOWN').toUpperCase();
  if (s === 'ONLINE') return 'bg-green-100 text-green-800 border border-green-200';
  if (s === 'OFFLINE') return 'bg-gray-100 text-gray-800 border border-gray-200';
  return 'bg-yellow-50 text-yellow-800 border border-yellow-200';
};

const GatewayCard = ({ gateway, onChanged }) => {
  const [busy, setBusy] = useState(false);

  const toggleStatus = async () => {
    setBusy(true);
    try {
      const next = (gateway.status || 'OFFLINE').toUpperCase() === 'ONLINE' ? 'OFFLINE' : 'ONLINE';
      await updateGateway(gateway.gw_eui, { status: next });
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  const doArchive = async () => {
    if (!confirm(`Archive gateway ${gateway.gw_eui}?`)) return;
    setBusy(true);
    try {
      await archiveGateway(gateway.gw_eui);
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border rounded-xl p-4 bg-white shadow-sm flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-gray-500 font-mono">{gateway.gw_eui}</div>
          <div className="text-lg font-semibold text-gray-900">
            {gateway.gateway_name || 'Unnamed Gateway'}
          </div>
        </div>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${badge(gateway.status)}`}>
          {(gateway.status || 'UNKNOWN').toUpperCase()}
        </span>
      </div>

      <div className="text-sm text-gray-600">
        <div><span className="text-gray-500">Last seen:</span> {formatLastSeen(gateway.last_seen_at)}</div>
        <div><span className="text-gray-500">Archived:</span> {gateway.archived_at ? fmtTime(gateway.archived_at) : '—'}</div>
      </div>

      <div className="mt-2 flex gap-2">
        <button
          onClick={toggleStatus}
          disabled={busy || !!gateway.archived_at}
          className="px-3 py-1.5 rounded border bg-gray-50 hover:bg-gray-100 disabled:opacity-50"
        >
          Toggle Status
        </button>
        {!gateway.archived_at && (
          <button
            onClick={doArchive}
            disabled={busy}
            className="px-3 py-1.5 rounded border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            Archive
          </button>
        )}
      </div>
    </div>
  );
};

export default GatewayCard;
