// src/components/ApiTester.jsx
import { useState } from 'react';
import { deviceService, locationService, healthService } from '../services';

const ApiTester = () => {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);

  const tests = {
    'Health Check': async () => {
      return await healthService.check();
    },
    'Get Devices (limit 3)': async () => {
      return await deviceService.getDevices({ limit: 3 });
    },
    'Get Locations (limit 3)': async () => {
      return await locationService.getLocations({ limit: 3 });
    },
    'Get Device Metadata (limit 2)': async () => {
      const metadata = await deviceService.getDeviceMetadata();
      return metadata.slice(0, 2); // Just return first 2 for brevity
    }
  };

  const runTest = async (testName, testFn) => {
    setResults(prev => ({
      ...prev,
      [testName]: { status: 'running', startTime: Date.now() }
    }));

    try {
      const startTime = Date.now();
      const result = await testFn();
      const duration = Date.now() - startTime;

      setResults(prev => ({
        ...prev,
        [testName]: {
          status: 'success',
          duration,
          data: result,
          dataSize: JSON.stringify(result).length
        }
      }));
    } catch (error) {
      setResults(prev => ({
        ...prev,
        [testName]: {
          status: 'error',
          error: error.userMessage || error.message,
          details: error.response?.data
        }
      }));
    }
  };

  const runAllTests = async () => {
    setLoading(true);
    setResults({});
    
    for (const [testName, testFn] of Object.entries(tests)) {
      await runTest(testName, testFn);
    }
    
    setLoading(false);
  };

  const runSingleTest = async (testName) => {
    await runTest(testName, tests[testName]);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          🔧 API Foundation Test
        </h1>
        <p className="text-gray-600 mb-4">
          Test your API connectivity before building UI components
        </p>
        
        <div className="flex items-center space-x-4 text-sm text-gray-500">
          <span>API Base: {import.meta.env.VITE_TRANSFORM_API_URL || 'Production'}</span>
          <span>Environment: {import.meta.env.VITE_NODE_ENV || 'production'}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex space-x-4">
          <button
            onClick={runAllTests}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '🔄 Running Tests...' : '🚀 Run All Tests'}
          </button>
          
          <button
            onClick={() => setResults({})}
            className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
          >
            🗑️ Clear Results
          </button>
        </div>
      </div>

      {/* Test Results */}
      <div className="space-y-4">
        {Object.entries(tests).map(([testName]) => {
          const result = results[testName];
          
          return (
            <div key={testName} className="bg-white rounded-lg shadow-sm border p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  {testName}
                </h3>
                
                <div className="flex items-center space-x-2">
                  {result?.duration && (
                    <span className="text-sm text-gray-500">
                      {result.duration}ms
                    </span>
                  )}
                  
                  <button
                    onClick={() => runSingleTest(testName)}
                    className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200"
                  >
                    Test
                  </button>
                </div>
              </div>

              {/* Status */}
              {result && (
                <div className="space-y-3">
                  <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
                    result.status === 'success' ? 'bg-green-100 text-green-800' :
                    result.status === 'error' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {result.status === 'success' && '✅ Success'}
                    {result.status === 'error' && '❌ Failed'}  
                    {result.status === 'running' && '🔄 Running...'}
                  </div>

                  {/* Error Message */}
                  {result.error && (
                    <div className="bg-red-50 border border-red-200 rounded p-3">
                      <p className="text-red-800 font-medium">Error:</p>
                      <p className="text-red-700">{result.error}</p>
                      {result.details && (
                        <pre className="text-xs text-red-600 mt-2 overflow-x-auto">
                          {JSON.stringify(result.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}

                  {/* Success Data */}
                  {result.data && (
                    <div className="bg-green-50 border border-green-200 rounded p-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-green-800 font-medium">Response:</p>
                        <span className="text-xs text-green-600">
                          {result.dataSize} bytes
                        </span>
                      </div>
                      <pre className="text-xs text-green-700 overflow-x-auto max-h-40">
                        {JSON.stringify(result.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ApiTester;
