// src/utils/deviceStatus.js
// Device status logic for ChirpStack-based devices (Build 18+)
// Device type comes from ChirpStack (always present)
// Site assignment is optional (via description field)

export const DEVICE_STATUSES = {
  UNASSIGNED: 'unassigned',     // No site assigned
  ASSIGNED: 'assigned',          // Site assigned via description
  ARCHIVED: 'archived'           // Archived device
};

export const STATUS_LABELS = {
  [DEVICE_STATUSES.UNASSIGNED]: '🟡 UNASSIGNED',
  [DEVICE_STATUSES.ASSIGNED]: '🟢 ASSIGNED',
  [DEVICE_STATUSES.ARCHIVED]: '📦 ARCHIVED'
};

export const STATUS_COLORS = {
  [DEVICE_STATUSES.UNASSIGNED]: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  [DEVICE_STATUSES.ASSIGNED]: 'text-green-600 bg-green-50 border-green-200',
  [DEVICE_STATUSES.ARCHIVED]: 'text-gray-600 bg-gray-50 border-gray-200'
};

export const getDeviceStatus = (device) => {
  // Archived devices
  if (device.archived_at) {
    return DEVICE_STATUSES.ARCHIVED;
  }

  // Device is assigned to a site if description field is populated
  // (description field contains site name, like in gateways)
  const hasSiteAssignment = device.description && device.description.trim().length > 0;

  if (hasSiteAssignment) {
    return DEVICE_STATUSES.ASSIGNED;
  }

  return DEVICE_STATUSES.UNASSIGNED;
};

export const getStatusLabel = (status) => {
  return STATUS_LABELS[status] || status;
};

export const getStatusColors = (status) => {
  return STATUS_COLORS[status] || STATUS_COLORS[DEVICE_STATUSES.UNASSIGNED];
};

export const deviceNeedsAction = (device) => {
  const status = getDeviceStatus(device);
  // Only unassigned devices need action (site assignment)
  return status === DEVICE_STATUSES.UNASSIGNED;
};

export const getRequiredAction = (device) => {
  const status = getDeviceStatus(device);

  switch (status) {
    case DEVICE_STATUSES.UNASSIGNED:
      return 'Assign to site';
    case DEVICE_STATUSES.ASSIGNED:
      return 'Assigned to site';
    case DEVICE_STATUSES.ARCHIVED:
      return 'Archived - no processing';
    default:
      return 'Unknown status';
  }
};