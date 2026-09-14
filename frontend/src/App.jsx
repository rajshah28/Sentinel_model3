import { NavLink, Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import GisMap from "./pages/GisMap";
import VehicleTrace from "./pages/VehicleTrace";
import Watchlist from "./pages/Watchlist";
import GovtGrid from "./pages/GovtGrid";

function RequireAuth({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Shell({ children }) {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="brand">SENTINEL <span>GJ</span></div>
        <div className="brand-sub">VMS Federation</div>
        <NavLink to="/" end className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>Dashboard</NavLink>
        <NavLink to="/map" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>GIS Map</NavLink>
        <NavLink to="/trace" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>Vehicle Trace</NavLink>
        {user?.role === "admin" && (
          <NavLink to="/govt-grid" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>Govt Grid (Live)</NavLink>
        )}
        {user?.role === "admin" && (
          <NavLink to="/watchlist" className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>Watchlist (Admin)</NavLink>
        )}
        <div style={{ marginTop: "auto", paddingTop: 20 }}>
          <div className={`pill ${user?.role}`}>{user?.role}</div>
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>{user?.username}</div>
          <button className="nav-link" style={{ marginTop: 10 }} onClick={logout}>Sign out</button>
        </div>
      </div>
      <div className="main">{children}</div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Shell><Dashboard /></Shell></RequireAuth>} />
      <Route path="/map" element={<RequireAuth><Shell><GisMap /></Shell></RequireAuth>} />
      <Route path="/trace" element={<RequireAuth><Shell><VehicleTrace /></Shell></RequireAuth>} />
      <Route path="/watchlist" element={<RequireAuth><Shell><Watchlist /></Shell></RequireAuth>} />
      <Route path="/govt-grid" element={<RequireAuth><Shell><GovtGrid /></Shell></RequireAuth>} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
