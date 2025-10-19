// src/utils/deviceStatus.js
// Device status logic based on device_type_id and location_id

export const DEVICE_STATUSES = {
  ORPHANED: 'orphaned',
  PARTIAL_TYPE: 'partial_type', 
  PARTIAL_LOCATION: 'partial_location',
  CONFIGURED: 'configured',
  ARCHIVED: 'archived'
};

export const STATUS_LABELS = {
  [DEVICE_STATUSES.ORPHANED]: '🔴 ORPHANED',
  [DEVICE_STATUSES.PARTIAL_TYPE]: '🟡 NEED TYPE',
  [DEVICE_STATUSES.PARTIAL_LOCATION]: '🟡 NEED LOCATION', 
  [DEVICE_STATUSES.CONFIGURED]: '🟢 CONFIGURED',
  [DEVICE_STATUSES.ARCHIVED]: '📦 ARCHIVED'
};

export const STATUS_COLORS = {
  [DEVICE_STATUSES.ORPHANED]: 'text-red-600 bg-red-50 border-red-200',
  [DEVICE_STATUSES.PARTIAL_TYPE]: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  [DEVICE_STATUSES.PARTIAL_LOCATION]: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  [DEVICE_STATUSES.CONFIGURED]: 'text-green-600 bg-green-50 border-green-200',
  [DEVICE_STATUSES.ARCHIVED]: 'text-gray-600 bg-gray-50 border-gray-200'
};

export const getDeviceStatus = (device) => {
  if (device.archived_at) {
    return DEVICE_STATUSES.ARCHIVED;
  }
  
  const hasType = device.device_type_id != null;
  const hasLocation = device.location_id != null;
  
  if (hasType && hasLocation) {
    return DEVICE_STATUSES.CONFIGURED;
  }
  
  if (hasType && !hasLocation) {
    return DEVICE_STATUSES.PARTIAL_LOCATION;
  }
  
  if (!hasType && hasLocation) {
    return DEVICE_STATUSES.PARTIAL_TYPE;
  }
  
  return DEVICE_STATUSES.ORPHANED;
};

export const getStatusLabel = (status) => {
  return STATUS_LABELS[status] || status;
};

export const getStatusColors = (status) => {
  return STATUS_COLORS[status] || STATUS_COLORS[DEVICE_STATUSES.ORPHANED];
};

export const deviceNeedsAction = (device) => {
  const status = getDeviceStatus(device);
  return [
    DEVICE_STATUSES.ORPHANED,
    DEVICE_STATUSES.PARTIAL_TYPE,
    DEVICE_STATUSES.PARTIAL_LOCATION
  ].includes(status);
};

export const getRequiredAction = (device) => {
  const status = getDeviceStatus(device);
  
  switch (status) {
    case DEVICE_STATUSES.ORPHANED:
      return 'Assign device type and location';
    case DEVICE_STATUSES.PARTIAL_TYPE:
      return 'Assign device type';
    case DEVICE_STATUSES.PARTIAL_LOCATION:
      return 'Assign location';
    case DEVICE_STATUSES.CONFIGURED:
      return 'Ready for processing';
    case DEVICE_STATUSES.ARCHIVED:
      return 'Archived - no processing';
    default:
      return 'Unknown status';
  }
};