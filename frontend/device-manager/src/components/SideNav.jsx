import { Link } from "react-router-dom";
export default function SideNav() {
  const items = [
    { to:"/", label:"Dashboard" },
    { to:"/devices", label:"Devices" },
    { to:"/locations", label:"Locations" },
    { to:"/gateways", label:"Gateways" },
    { to:"/uplinks", label:"Uplinks" },
    { to:"/settings", label:"Settings" },
  ];
  return (
    <nav className="p-3">
      <ul className="space-y-1">
        {items.map(i => <li key={i.to}><Link className="block px-2 py-1 rounded hover:bg-gray-100" to={i.to}>{i.label}</Link></li>)}
      </ul>
    </nav>
  );
}
