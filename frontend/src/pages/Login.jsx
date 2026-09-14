import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="brand">SENTINEL <span>GJ</span></div>
        <div className="brand-sub">VMS Federation &amp; Middleware — Model 3</div>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label className="muted">Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label className="muted">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <div style={{ color: "#f87171", fontSize: 13 }}>{error}</div>}
          <button className="btn" type="submit" disabled={loading} style={{ marginTop: 8 }}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <div className="muted" style={{ marginTop: 18, fontSize: 12, lineHeight: 1.6 }}>
          Demo accounts:<br />
          admin / Sentinel@2026 (state-wide access)<br />
          dahod_operator / Dahod@2026 (Dahod City Police only)
        </div>
      </div>
    </div>
  );
}
