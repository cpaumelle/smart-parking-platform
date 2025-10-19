// 10-ui-frontend/sensemy-platform/src/App.jsx
// Version: 1.0.0 - 2025-08-08 07:20 UTC
// Changelog:
// - Updated to use enhanced SenseMyIoTPlatform component
// - Simplified app structure for device management platform

import React from 'react';
import SenseMyIoTPlatform from './components/SenseMyIoTPlatform';
import './index.css';

function App() {
  return (
    <div className="App">
      <SenseMyIoTPlatform />
    </div>
  );
}

export default App;
