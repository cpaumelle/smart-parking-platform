// src/pages/DeviceManager.jsx
import DeviceList from '../components/devices/DeviceList.jsx';

const DeviceManager = ({ initialFilters }) => {
  return <DeviceList initialFilters={initialFilters} />;
};

export default DeviceManager;
