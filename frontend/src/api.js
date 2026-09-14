import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8010";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

const client = axios.create({ baseURL: API_BASE });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("sentinel_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function login(username, password) {
  const res = await client.post("/api/auth/login", { username, password });
  return res.data;
}

export async function getCameras() {
  const res = await client.get("/api/cameras");
  return res.data;
}

export async function getAlerts(limit = 50) {
  const res = await client.get("/api/alerts", { params: { limit } });
  return res.data;
}

export async function getWatchlist() {
  const res = await client.get("/api/watchlist");
  return res.data;
}

export async function traceVehicle(plate) {
  const res = await client.get(`/api/trace/${encodeURIComponent(plate)}`);
  return res.data;
}

export async function runDemoIngestion() {
  const res = await client.post("/api/ingestion/run-demo");
  return res.data;
}

export async function getIngestionStatus() {
  const res = await client.get("/api/ingestion/status");
  return res.data;
}

export async function getGovtGridCatalogue() {
  const res = await client.get("/api/ingestion/govt-grid/catalogue");
  return res.data;
}

export async function runGovtGridIngestion(durationSec = 60) {
  const res = await client.post("/api/ingestion/govt-grid/run", null, {
    params: { duration_sec: durationSec },
  });
  return res.data;
}

export async function getGovtGridStatus() {
  const res = await client.get("/api/ingestion/govt-grid/status");
  return res.data;
}

export function frameFullUrl(frameUrl) {
  if (!frameUrl) return null;
  return `${API_BASE}${frameUrl}`;
}

export default client;
