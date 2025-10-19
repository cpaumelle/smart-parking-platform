import { useEffect, useMemo, useState } from "react";
import useLocations from "../../hooks/useLocations";

/**
 * Cascading picker: Site → Floor → Room → Zone
 *
 * Props:
 * - value: { siteId?, floorId?, roomId?, zoneId? } (controlled)
 * - onChange: (next) => void
 * - archived: "false" | "true" | "all"
 * - disabled: boolean
 * - dense: boolean (smaller controls)
 */
const LocationPicker = ({
  value,
  onChange,
  archived = "false",
  disabled = false,
  dense = false,
}) => {
  const { childrenOf, loading, error } = useLocations({ archived });

  // Internal state if uncontrolled
  const [internal, setInternal] = useState({
    siteId: null,
    floorId: null,
    roomId: null,
    zoneId: null,
  });

  const state = value ?? internal;

  // reset downstream selections when a parent changes
  const setPart = (part, id) => {
    const next = {
      ...state,
      [part]: id || null,
      ...(part === "siteId" ? { floorId: null, roomId: null, zoneId: null } : {}),
      ...(part === "floorId" ? { roomId: null, zoneId: null } : {}),
      ...(part === "roomId" ? { zoneId: null } : {}),
    };
    if (onChange) onChange(next);
    else setInternal(next);
  };

  const sites = useMemo(() => childrenOf(null, "site"), [childrenOf]);
  const floors = useMemo(
    () => (state.siteId ? childrenOf(state.siteId, "floor") : []),
    [childrenOf, state.siteId]
  );
  const rooms = useMemo(
    () => (state.floorId ? childrenOf(state.floorId, "room") : []),
    [childrenOf, state.floorId]
  );
  const zones = useMemo(
    () => (state.roomId ? childrenOf(state.roomId, "zone") : []),
    [childrenOf, state.roomId]
  );

  useEffect(() => {
    // Sanity: clear selections that no longer exist
    if (state.siteId && !sites.find((s) => s.location_id === state.siteId)) {
      setPart("siteId", null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sites.length]);

  const cls = dense ? "p-1 text-sm" : "p-2";

  if (loading) return <div className="text-sm text-gray-500">Loading locations…</div>;
  if (error) return <div className="text-sm text-red-600">Failed to load locations.</div>;
  if (!sites.length) return <div className="text-sm text-gray-500">No locations.</div>;

  return (
    <div className="grid gap-2 md:grid-cols-4">
      <div>
        <label className="block text-xs text-gray-600 mb-1">Site</label>
        <select
          className={`w-full border rounded ${cls}`}
          disabled={disabled}
          value={state.siteId || ""}
          onChange={(e) => setPart("siteId", e.target.value || null)}
        >
          <option value="">—</option>
          {sites.map((s) => (
            <option key={s.location_id} value={s.location_id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">Floor</label>
        <select
          className={`w-full border rounded ${cls}`}
          disabled={disabled || !state.siteId}
          value={state.floorId || ""}
          onChange={(e) => setPart("floorId", e.target.value || null)}
        >
          <option value="">—</option>
          {floors.map((f) => (
            <option key={f.location_id} value={f.location_id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">Room</label>
        <select
          className={`w-full border rounded ${cls}`}
          disabled={disabled || !state.floorId}
          value={state.roomId || ""}
          onChange={(e) => setPart("roomId", e.target.value || null)}
        >
          <option value="">—</option>
          {rooms.map((r) => (
            <option key={r.location_id} value={r.location_id}>
              {r.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">Zone</label>
        <select
          className={`w-full border rounded ${cls}`}
          disabled={disabled || !state.roomId}
          value={state.zoneId || ""}
          onChange={(e) => setPart("zoneId", e.target.value || null)}
        >
          <option value="">—</option>
          {zones.map((z) => (
            <option key={z.location_id} value={z.location_id}>
              {z.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};

export default LocationPicker;
