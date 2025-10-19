// Lightweight hook to load the location tree from the Transform API
// Version: 1.1.0 - Fixed API base URL to match other services
import { useEffect, useMemo, useRef, useState } from "react";
import apiClient from "../services/apiClient.js";

export function useLocations({ archived = "false" } = {}) {
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    
    try {
      const response = await apiClient.get(`/v1/locations/tree?archived=${encodeURIComponent(archived)}`, {
        signal: abortRef.current.signal
      });
      setTree(Array.isArray(response.data) ? response.data : []);
    } catch (e) {
      if (e.name !== "AbortError") {
        console.error('Failed to fetch locations:', e);
        setError(e);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [archived]);

  // Helpers
  const byId = useMemo(() => {
    const m = new Map();
    const walk = (n) => {
      m.set(n.location_id, n);
      n.children?.forEach(walk);
    };
    tree.forEach(walk);
    return m;
  }, [tree]);

  const childrenOf = (parentId, type) => {
    if (!parentId) {
      // roots only (sites)
      return tree.filter((n) => n.type === (type || "site"));
    }
    const parent = byId.get(parentId);
    if (!parent) return [];
    return parent.children?.filter((n) => (type ? n.type === type : true)) || [];
  };

  const pathTo = (id) => {
    const node = byId.get(id);
    if (!node) return [];
    // we didn't store parent chains, but backend gave us `path_string`
    // so we'll reconstruct a best-effort array from siblings
    // For precise chains, you could extend the API or hydrate parents in this hook.
    return node.path_string?.split(" > ") ?? [];
  };

  return { tree, loading, error, refresh, childrenOf, byId, pathTo };
}

export default useLocations;
