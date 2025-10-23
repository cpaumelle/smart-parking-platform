// frontend/src/config/featureFlags.js

export const FeatureFlags = {
  USE_V6_API: process.env.REACT_APP_USE_V6_API === 'true',
  SHOW_PLATFORM_ADMIN_UI: process.env.REACT_APP_SHOW_PLATFORM_ADMIN === 'true',
  ENABLE_DEVICE_POOL: process.env.REACT_APP_ENABLE_DEVICE_POOL === 'true',
};

// Gradual rollout configuration
export const V6_ROLLOUT = {
  devices: FeatureFlags.USE_V6_API,
  gateways: false, // Still on v5
  spaces: false,    // Still on v5
  dashboard: FeatureFlags.USE_V6_API,
};

export function shouldUseV6(feature) {
  return V6_ROLLOUT[feature] || false;
}

export const PLATFORM_TENANT_ID = '00000000-0000-0000-0000-000000000000';
