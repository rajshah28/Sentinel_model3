import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { getCameras } from "../api";

const GUJARAT_CENTER = [22.2587, 71.1924];

export default function GisMap() {
  const [cameras, setCameras] = useState([]);

  useEffect(() => {
    getCameras().then(setCameras);
  }, []);

  return (
    <div>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Camera GIS View</h2>
          <div className="muted">{cameras.length} federated camera locations across Gujarat</div>
        </div>
      </div>
      <div className="card" style={{ padding: 8 }}>
        <MapContainer center={GUJARAT_CENTER} zoom={7} scrollWheelZoom={true}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {cameras.map((c) => (
            <CircleMarker
              key={c.id}
              center={[c.latitude, c.longitude]}
              radius={9}
              pathOptions={{
                color: c.status === "online" ? "#22c55e" : "#ef4444",
                fillColor: c.status === "online" ? "#22c55e" : "#ef4444",
                fillOpacity: 0.7,
              }}
            >
              <Popup>
                <strong>{c.id}</strong><br />
                {c.location_name}<br />
                {c.department}<br />
                Vendor: {c.vendor}<br />
                Status: {c.status}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
