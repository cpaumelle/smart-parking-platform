// src/components/chirpstack/ChirpStackBulkActions.jsx
import React, { useState } from 'react';
import { chirpstackService } from '../../services/chirpstackService.js';
import { X, Upload, FileUp, CheckCircle, XCircle } from 'lucide-react';

const ChirpStackBulkActions = ({ onClose, onSuccess, applications, deviceProfiles }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'text/csv') {
      setSelectedFile(file);
      setError(null);
      setResult(null);
    } else {
      setError('Please select a valid CSV file');
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file first');
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const result = await chirpstackService.bulkCreateFromCSV(selectedFile);
      setResult(result);
      
      if (result.succeeded > 0) {
        setTimeout(() => {
          onSuccess();
        }, 2000);
      }
    } catch (err) {
      console.error('Bulk upload failed:', err);
      setError(err.response?.data?.detail || err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = () => {
    const template = [
      'dev_eui,name,description,application_id,device_profile_id,join_eui,enabled_class,app_key,nwk_key',
      '0004A30B00FB0001,Test Device 1,Example device,app-id-here,profile-id-here,0000000000000000,A,00000000000000000000000000000000,00000000000000000000000000000000'
    ].join('\\n');

    const blob = new Blob([template], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'chirpstack_devices_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-white rounded-lg border shadow-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Upload className="w-6 h-6 text-blue-600 mr-3" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Bulk Device Import</h3>
            <p className="text-sm text-gray-600">Upload a CSV file to import multiple devices</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600"
        >
          <X className="w-6 h-6" />
        </button>
      </div>

      {/* CSV Format Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">CSV Format Requirements:</h4>
        <ul className="text-xs text-blue-800 space-y-1 ml-4 list-disc">
          <li>Headers: dev_eui,name,description,application_id,device_profile_id,join_eui,enabled_class,app_key,nwk_key</li>
          <li>DevEUI must be 16-character hexadecimal (e.g., 0004A30B00FB0001)</li>
          <li>Application ID and Device Profile ID must match existing IDs in ChirpStack</li>
          <li>Keys (app_key, nwk_key) must be 32-character hexadecimal</li>
        </ul>
        <button
          onClick={downloadTemplate}
          className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline"
        >
          Download CSV Template
        </button>
      </div>

      {/* Available Applications & Profiles Reference */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 rounded-md p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Available Applications:</h4>
          <div className="text-xs text-gray-700 space-y-1 max-h-32 overflow-y-auto">
            {applications.length > 0 ? (
              applications.map(app => (
                <div key={app.id} className="font-mono">
                  {app.id} - {app.name}
                </div>
              ))
            ) : (
              <div className="text-gray-500">No applications found</div>
            )}
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-md p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Available Device Profiles:</h4>
          <div className="text-xs text-gray-700 space-y-1 max-h-32 overflow-y-auto">
            {deviceProfiles.length > 0 ? (
              deviceProfiles.map(profile => (
                <div key={profile.id} className="font-mono">
                  {profile.id} - {profile.name}
                </div>
              ))
            ) : (
              <div className="text-gray-500">No profiles found</div>
            )}
          </div>
        </div>
      </div>

      {/* File Upload */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select CSV File
        </label>
        <div className="flex items-center space-x-3">
          <label className="flex-1 flex items-center justify-center px-4 py-3 border-2 border-dashed border-gray-300 rounded-md cursor-pointer hover:border-blue-400 transition">
            <FileUp className="w-5 h-5 text-gray-400 mr-2" />
            <span className="text-sm text-gray-600">
              {selectedFile ? selectedFile.name : 'Choose CSV file...'}
            </span>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
          <div className="flex items-start">
            <XCircle className="w-5 h-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-800">Upload Failed</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Result Display */}
      {result && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex items-start mb-3">
            <CheckCircle className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-green-800">Upload Completed</p>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4 mt-3">
            <div className="bg-white rounded-md p-3 border border-green-200">
              <div className="text-2xl font-bold text-gray-900">{result.total}</div>
              <div className="text-xs text-gray-600">Total</div>
            </div>
            <div className="bg-white rounded-md p-3 border border-green-200">
              <div className="text-2xl font-bold text-green-600">{result.succeeded}</div>
              <div className="text-xs text-gray-600">Succeeded</div>
            </div>
            <div className="bg-white rounded-md p-3 border border-green-200">
              <div className="text-2xl font-bold text-red-600">{result.failed}</div>
              <div className="text-xs text-gray-600">Failed</div>
            </div>
          </div>

          {result.errors && result.errors.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-semibold text-gray-800 mb-2">Errors:</p>
              <div className="bg-white rounded-md p-3 border max-h-40 overflow-y-auto">
                <ul className="text-xs text-red-700 space-y-1">
                  {result.errors.map((error, idx) => (
                    <li key={idx} className="font-mono">{error}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ChirpStackBulkActions;
