// src/components/common/Navigation.jsx
import { useState } from 'react';
import { NAVIGATION_ITEMS, APP_CONFIG } from '../../utils/constants.js';

const Navigation = ({ currentPath = '/', onNavigate }) => {
  const [activeTab, setActiveTab] = useState(currentPath);

  const handleTabClick = (item) => {
    setActiveTab(item.path);
    if (onNavigate) {
      onNavigate(item.path);
    }
  };

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <h1 className="text-xl font-bold text-gray-900">
              {APP_CONFIG.name}
            </h1>
            <span className="ml-2 text-sm text-gray-500">
              v{APP_CONFIG.version}
            </span>
          </div>
          
          <div className="text-sm text-gray-500">
            {APP_CONFIG.description}
          </div>
        </div>

        <div className="flex space-x-8">
          {NAVIGATION_ITEMS.map((item) => {
            const isActive = activeTab === item.path;
            return (
              <button
                key={item.id}
                onClick={() => handleTabClick(item)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
