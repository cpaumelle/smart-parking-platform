/*
 * SenseMy IoT Platform - Version Info Component
 * Version: 1.0.0
 * Created: 2025-08-11 17:45:00 UTC
 * Author: SenseMy IoT Development Team
 * 
 * Displays build version information
 */

import React from 'react';
import { GitCommit, Clock } from 'lucide-react';
import { useVersion } from '../../hooks/useVersion.js';

const VersionInfo = ({ className = "", showFull = false }) => {
  const { version, loading } = useVersion();

  if (loading || !version) return null;

  return (
    <div className={`flex items-center space-x-3 text-xs text-gray-500 ${className}`}>
      <div className="flex items-center space-x-1">
        <GitCommit className="w-3 h-3" />
        <span className="font-mono">Build: {version.buildNumber}</span>
      </div>
      
      {showFull && (
        <>
          <div className="flex items-center space-x-1">
            <Clock className="w-3 h-3" />
            <span>{version.buildTimestamp}</span>
          </div>
          <div className="hidden sm:block">
            <span className="font-mono">v{version.version}.{version.build}</span>
          </div>
          {version.gitCommit && version.gitCommit !== 'unknown' && (
            <div className="hidden md:block">
              <span className="font-mono text-gray-400">{version.gitCommit}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VersionInfo;
