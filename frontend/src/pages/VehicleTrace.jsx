import { useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { traceVehicle, frameFullUrl } from "../api";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export default function VehicleTrace() {
  const [plate, setPlate] = useState("BGY888");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSearch(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await traceVehicle(plate);
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Trace failed");
    } finally {
      setLoading(false);
    }
  }

  const positions = result?.route.map((r) => [r.latitude, r.longitude]) || [];

  return (
    <div>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Vehicle Trace</h2>
          <div className="muted">Cross-camera movement history lookup by plate number</div>
        </div>
      </div>

      <form onSubmit={handleSearch} className="card" style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "flex-end" }}>
        <div style={{ flex: 1 }}>
          <label className="muted">Plate Number</label>
          <input value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="e.g. BGY888" />
        </div>
        <button className="btn" type="submit" disabled={loading}>{loading ? "Searching..." : "Trace Vehicle"}</button>
      </form>

      {error && <div className="card" style={{ borderColor: "#ef4444", color: "#fca5a5", marginBottom: 20 }}>{error}</div>}

      {result && (
        <>
          <div className="grid grid-3" style={{ marginBottom: 20 }}>
            <div className="card">
              <div className="stat-label">Total Sightings</div>
              <div className="stat-value">{result.total_sightings}</div>
            </div>
            <div className="card">
              <div className="stat-label">Cameras Seen On</div>
              <div className="stat-value">{result.cameras_seen.length}</div>
            </div>
            <div className="card">
              <div className="stat-label">Watchlist Status</div>
              <div className="stat-value" style={{ color: result.watchlist_match ? "#f87171" : "#4ade80", fontSize: 18 }}>
                {result.watchlist_match ? "MATCH" : "Clear"}
              </div>
            </div>
          </div>

          {result.watchlist_match && (
            <div className="card" style={{ borderColor: "#ef4444", marginBottom: 20 }}>
              <div className="section-title" style={{ color: "#fca5a5" }}>Watchlist Record</div>
              <div>{result.watchlist_match.reason}</div>
              <div className="muted">{result.watchlist_match.vehicle_description}</div>
              <div className="muted">Flagged by: {result.watchlist_match.added_by_department}</div>
            </div>
          )}

          <div className="grid grid-2">
            <div className="card" style={{ padding: 8 }}>
              {positions.length > 0 && (
                <MapContainer center={positions[0]} zoom={9} scrollWheelZoom={true}>
                  <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <Polyline positions={positions} pathOptions={{ color: "#3b82f6" }} />
                  {result.route.map((r, i) => (
                    <Marker key={i} position={[r.latitude, r.longitude]}>
                      <Popup>
                        {r.location_name}<br />
                        {new Date(r.timestamp + (r.timestamp.endsWith("Z") ? "" : "Z")).toLocaleString()}<br />
                        Confidence: {(r.confidence * 100).toFixed(0)}%
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
              )}
            </div>

            <div className="card">
              <div className="section-title">Timeline</div>
              <div style={{ maxHeight: 460, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Time</th><th>Camera</th><th>Conf.</th></tr></thead>
                  <tbody>
                    {result.route.map((r, i) => (
                      <tr key={i}>
                        <td>{new Date(r.timestamp + (r.timestamp.endsWith("Z") ? "" : "Z")).toLocaleTimeString()}</td>
                        <td>{r.camera_id}<div className="muted">{r.location_name}</div></td>
                        <td>{(r.confidence * 100).toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
