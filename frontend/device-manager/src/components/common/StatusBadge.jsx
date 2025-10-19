// src/components/common/StatusBadge.jsx
import { getDeviceStatus, getStatusLabel, getStatusColors } from '../../utils/deviceStatus.js';

const StatusBadge = ({ device, className = '', size = 'normal' }) => {
  const status = getDeviceStatus(device);
  const label = getStatusLabel(status);
  const colors = getStatusColors(status);
  
  const sizeClasses = {
    small: 'px-2 py-1 text-xs',
    normal: 'px-3 py-1 text-sm',
    large: 'px-4 py-2 text-base'
  };
  
  const baseClasses = `inline-flex items-center rounded-full border font-medium ${sizeClasses[size]} ${colors}`;
  
  return (
    <span className={`${baseClasses} ${className}`}>
      {label}
    </span>
  );
};

export default StatusBadge;