import { useState } from "react";
import { getGovtGridCatalogue, runGovtGridIngestion, getGovtGridStatus } from "../api";

export default function GovtGrid() {
  const [catalogue, setCatalogue] = useState(null);
  const [catalogueError, setCatalogueError] = useState("");
  const [loadingCat, setLoadingCat] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState("");
  const [duration, setDuration] = useState(60);

  async function handleFetchCatalogue() {
    setLoadingCat(true);
    setCatalogueError("");
    setCatalogue(null);
    try {
      const data = await getGovtGridCatalogue();
      setCatalogue(data);
    } catch (err) {
      setCatalogueError(err?.response?.data?.detail || "Could not reach government grid catalogue");
    } finally {
      setLoadingCat(false);
    }
  }

  async function handleRun() {
    setRunning(true);
    setRunError("");
    setRunResult(null);
    try {
      await runGovtGridIngestion(duration);
      const poll = setInterval(async () => {
        const status = await getGovtGridStatus();
        if (!status.running) {
          clearInterval(poll);
          setRunning(false);
          setRunResult(status);
        }
      }, 2000);
    } catch (err) {
      setRunning(false);
      setRunError(err?.response?.data?.detail || "Live capture run failed");
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h2 style={{ margin: 0 }}>Government Sandbox Grid <span style={{ color: "#f87171" }}>— LIVE</span></h2>
          <div className="muted">Demo 4: real RTSP feed(s), not simulated footage</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="section-title">1. Catalogue (source of truth)</div>
        <div className="muted" style={{ marginBottom: 12 }}>
          Fetches GET /api/ingest from the configured sandbox host. No camera IDs
          or URLs are hardcoded anywhere in this system — the catalogue response
          is the only source of camera identity.
        </div>
        <button className="btn secondary" onClick={handleFetchCatalogue} disabled={loadingCat}>
          {loadingCat ? "Fetching..." : "Fetch Live Catalogue"}
        </button>

        {catalogueError && (
          <div style={{ marginTop: 14, color: "#fca5a5" }}>
            {catalogueError}
          </div>
        )}

        {catalogue && (
          <div style={{ marginTop: 16 }}>
            <div className="muted" style={{ marginBottom: 8 }}>
              Host: {catalogue.host} · {catalogue.camera_count} camera(s) reported
            </div>
            <table>
              <thead><tr><th>ID</th><th>Location</th><th>Codec</th><th>Live</th></tr></thead>
              <tbody>
                {catalogue.cameras.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td className="muted">{c.location}</td>
                    <td className="muted">{c.codec}</td>
                    <td><span className={`badge ${c.live ? "online" : "offline"}`}>{c.live ? "live" : "offline"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="section-title">2. Bounded live capture run</div>
        <div className="muted" style={{ marginBottom: 12 }}>
          Connects over RTSP (TCP-forced), samples frames by elapsed PTS (not
          wall-clock or frame count), runs the same ANPR → bus → correlation →
          watchlist pipeline as the simulated vendors, for a bounded capture
          window (live streams have no natural end).
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 12 }}>
          <div>
            <label className="muted">Duration (seconds)</label>
            <input type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} style={{ width: 120 }} />
          </div>
          <button className="btn" onClick={handleRun} disabled={running}>
            {running ? "Capturing..." : "Run Live Capture"}
          </button>
        </div>
        {runError && <div style={{ color: "#fca5a5" }}>{runError}</div>}
        {runResult && (
          <div className="muted">
            Cameras ingested: {runResult.cameras_ingested.join(", ") || "(none)"} ·
            Detections emitted: {runResult.total_detections_emitted}
          </div>
        )}
      </div>
    </div>
  );
}
