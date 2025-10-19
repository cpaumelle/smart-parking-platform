/*
 * SenseMy IoT Platform - Version Hook
 * Version: 1.0.0
 * Created: 2025-08-11 17:30:00 UTC
 * Author: SenseMy IoT Development Team
 * 
 * Provides build version information to components
 */

import { useState, useEffect } from 'react';

export const useVersion = () => {
  const [version, setVersion] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadVersion = async () => {
      try {
        // Try to load version from version.json
        const response = await fetch('/version.json');
        if (response.ok) {
          const versionData = await response.json();
          setVersion(versionData);
        } else {
          // Fallback to environment variables from build
          setVersion({
            version: import.meta.env.VITE_VERSION || '1.0.0',
            build: import.meta.env.VITE_BUILD_NUMBER || '0',
            buildTimestamp: import.meta.env.VITE_BUILD_TIMESTAMP || 'Unknown',
            buildNumber: import.meta.env.VITE_BUILD_ID || 'dev',
            environment: 'production'
          });
        }
      } catch (error) {
        console.warn('Could not load version info:', error);
        setVersion({
          version: '1.0.0',
          build: '0',
          buildTimestamp: 'Unknown',
          buildNumber: 'dev',
          environment: 'development'
        });
      } finally {
        setLoading(false);
      }
    };

    loadVersion();
  }, []);

  return { version, loading };
};

export default useVersion;
