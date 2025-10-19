// src/components/common/LoadingSpinner.jsx
const LoadingSpinner = ({ size = 'normal', text = '', className = '' }) => {
  const sizeClasses = {
    small: 'w-4 h-4',
    normal: 'w-8 h-8', 
    large: 'w-12 h-12'
  };

  const textSizes = {
    small: 'text-sm',
    normal: 'text-base',
    large: 'text-lg'
  };

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div 
        className={`animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 ${sizeClasses[size]}`}
      />
      {text && (
        <p className={`mt-2 text-gray-600 ${textSizes[size]}`}>
          {text}
        </p>
      )}
    </div>
  );
};

export default LoadingSpinner;