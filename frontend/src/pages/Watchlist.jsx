import { useEffect, useState } from "react";
import { getWatchlist } from "../api";
import { useAuth } from "../AuthContext";

export default function Watchlist() {
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);

  useEffect(() => {
    getWatchlist().then(setEntries);
  }, []);

  if (user?.role !== "admin") {
    return <div className="card">This section is restricted to admin users.</div>;
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>State Watchlist</h2>
          <div className="muted">Shared across all federated departments — admin access only</div>
        </div>
      </div>
      <div className="card">
        <table>
          <thead><tr><th>Plate</th><th>Reason</th><th>Vehicle</th><th>Priority</th><th>Flagged By</th></tr></thead>
          <tbody>
            {entries.map((w) => (
              <tr key={w.id}>
                <td><strong>{w.plate_text}</strong></td>
                <td>{w.reason}</td>
                <td className="muted">{w.vehicle_description}</td>
                <td><span className={`badge ${w.priority}`}>{w.priority}</span></td>
                <td className="muted">{w.added_by_department}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
