import { useEffect, useRef, useState } from "react";
import { getAlerts, getCameras, runDemoIngestion, getIngestionStatus, frameFullUrl, WS_BASE } from "../api";
import { useAuth } from "../AuthContext";

function timeAgo(iso) {
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  const secs = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [ingestRunning, setIngestRunning] = useState(false);
  const [toast, setToast] = useState(null);
  const wsRef = useRef(null);

  async function refresh() {
    const [cams, al] = await Promise.all([getCameras(), getAlerts(30)]);
    setCameras(cams);
    setAlerts(al);
  }

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 8000);

    const token = localStorage.getItem("sentinel_token");
    const ws = new WebSocket(`${WS_BASE}/ws/alerts`);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      const alert = JSON.parse(evt.data);
      setToast(alert);
      setTimeout(() => setToast((cur) => (cur === alert ? null : cur)), 6000);
      refresh();
    };

    return () => {
      clearInterval(poll);
      ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRunDemo() {
    setIngestRunning(true);
    await runDemoIngestion();
    const poll = setInterval(async () => {
      const status = await getIngestionStatus();
      if (!status.running) {
        clearInterval(poll);
        setIngestRunning(false);
        refresh();
      }
    }, 2000);
  }

  const online = cameras.filter((c) => c.status === "online").length;

  return (
    <div>
      {toast && (
        <div className="toast">
          <strong>WATCHLIST MATCH</strong><br />
          Plate {toast.plate_text} · {toast.camera_id}<br />
          <span style={{ fontSize: 12, opacity: 0.9 }}>{toast.reason}</span>
        </div>
      )}

      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Statewide Overview</h2>
          <div className="muted">Signed in as {user?.username} · {user?.department || "All Departments"}</div>
        </div>
        {user?.role === "admin" && (
          <button className="btn" onClick={handleRunDemo} disabled={ingestRunning}>
            {ingestRunning ? "Processing demo footage..." : "Run Demo Ingestion"}
          </button>
        )}
      </div>

      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="stat-label">Cameras Online</div>
          <div className="stat-value">{online} / {cameras.length}</div>
        </div>
        <div className="card">
          <div className="stat-label">Active Alerts (recent)</div>
          <div className="stat-value" style={{ color: alerts.length ? "#f87171" : undefined }}>{alerts.length}</div>
        </div>
        <div className="card">
          <div className="stat-label">Departments Federated</div>
          <div className="stat-value">{new Set(cameras.map((c) => c.department)).size}</div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="section-title">Live Alert Feed</div>
          {alerts.length === 0 && <div className="muted">No alerts yet. Run demo ingestion to generate real detections.</div>}
          {alerts.map((a) => (
            <div className="alert-row" key={a.id}>
              {a.frame_url && <img className="alert-thumb" src={frameFullUrl(a.frame_url)} alt="" />}
              <div style={{ flex: 1 }}>
                <div><strong>{a.plate_text}</strong> · {a.camera_id} · {a.department}</div>
                <div className="muted">{a.reason}</div>
              </div>
              <div className="muted" style={{ whiteSpace: "nowrap" }}>{timeAgo(a.timestamp)}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="section-title">Camera / Feed Status</div>
          <table>
            <thead><tr><th>Camera</th><th>Vendor</th><th>Source</th><th>Status</th></tr></thead>
            <tbody>
              {cameras.map((c) => {
                const isGovtGrid = c.vendor === "VendorD-GovtSandboxGrid";
                return (
                  <tr key={c.id}>
                    <td>{c.id}<div className="muted">{c.location_name}</div></td>
                    <td className="muted">{c.protocol}</td>
                    <td>
                      <span className="badge" style={isGovtGrid
                        ? { background: "rgba(239,68,68,.18)", color: "#fca5a5" }
                        : { background: "rgba(148,163,184,.15)", color: "#cbd5e1" }}>
                        {isGovtGrid ? "GOVT GRID — LIVE" : "SIMULATED"}
                      </span>
                    </td>
                    <td><span className={`badge ${c.status}`}>{c.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
