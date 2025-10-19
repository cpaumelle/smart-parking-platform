// src/components/common/InteractiveStatusCard.jsx
// Version: 1.0.0 - 2025-08-09 14:35:00 UTC
// Changelog:
// - Created interactive status card with navigation support
// - Supports dashboard links to filtered pages
// - Handles active state for current filters
// - Mobile-responsive design consistent with platform

import React from 'react';

const InteractiveStatusCard = ({
  title,
  count,
  icon: Icon,
  color = 'gray',
  onClick,
  isActive = false,
  isClickable = true,
  subtitle,
  loading = false
}) => {
  const colorConfig = {
    gray: {
      bg: 'bg-white',
      iconBg: 'bg-gray-100',
      iconColor: 'text-gray-600',
      textColor: 'text-gray-900',
      subtitleColor: 'text-gray-600',
      hoverBg: 'hover:bg-gray-50',
      activeBg: 'bg-blue-50',
      activeBorder: 'border-blue-200'
    },
    blue: {
      bg: 'bg-white',
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      textColor: 'text-blue-600',
      subtitleColor: 'text-gray-600',
      hoverBg: 'hover:bg-blue-50',
      activeBg: 'bg-blue-50',
      activeBorder: 'border-blue-200'
    },
    green: {
      bg: 'bg-white',
      iconBg: 'bg-green-100',
      iconColor: 'text-green-600',
      textColor: 'text-green-600',
      subtitleColor: 'text-gray-600',
      hoverBg: 'hover:bg-green-50',
      activeBg: 'bg-green-50',
      activeBorder: 'border-green-200'
    },
    yellow: {
      bg: 'bg-white',
      iconBg: 'bg-yellow-100',
      iconColor: 'text-yellow-600',
      textColor: 'text-yellow-600',
      subtitleColor: 'text-gray-600',
      hoverBg: 'hover:bg-yellow-50',
      activeBg: 'bg-yellow-50',
      activeBorder: 'border-yellow-200'
    },
    red: {
      bg: 'bg-white',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      textColor: 'text-red-600',
      subtitleColor: 'text-gray-600',
      hoverBg: 'hover:bg-red-50',
      activeBg: 'bg-red-50',
      activeBorder: 'border-red-200'
    }
  };

  const config = colorConfig[color] || colorConfig.gray;

  const cardClasses = `
    ${config.bg} 
    rounded-lg 
    border 
    p-3 sm:p-4 
    transition-all 
    duration-200
    ${isActive ? `${config.activeBg} ${config.activeBorder}` : 'border-gray-200'}
    ${isClickable ? `${config.hoverBg} cursor-pointer hover:shadow-md` : ''}
    ${loading ? 'opacity-75' : ''}
  `.trim();

  const handleClick = () => {
    if (isClickable && onClick && !loading) {
      onClick();
    }
  };

  return (
    <div className={cardClasses} onClick={handleClick}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-xs sm:text-sm font-medium text-gray-600 mb-1">{title}</p>
          <div className="flex items-baseline space-x-2">
            <p className={`text-lg sm:text-2xl font-bold ${config.textColor}`}>
              {loading ? '...' : count.toLocaleString()}
            </p>
            {subtitle && (
              <p className={`text-xs ${config.subtitleColor} hidden sm:block`}>
                {subtitle}
              </p>
            )}
          </div>
          {isActive && (
            <div className="mt-2">
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                Active Filter
              </span>
            </div>
          )}
        </div>
        <div className={`p-2 rounded-lg ${config.iconBg} flex-shrink-0`}>
          {Icon && <Icon className={`w-6 h-6 ${config.iconColor}`} />}
        </div>
      </div>
      {isClickable && (
        <div className="mt-2 flex items-center text-xs text-gray-500">
          <span>Click to view {title.toLowerCase()}</span>
          <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      )}
    </div>
  );
};

export default InteractiveStatusCard;
