import { createContext, useContext, useState } from "react";
import { login as apiLogin } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("sentinel_user");
    return raw ? JSON.parse(raw) : null;
  });

  async function login(username, password) {
    const data = await apiLogin(username, password);
    localStorage.setItem("sentinel_token", data.access_token);
    const userInfo = { username: data.username, role: data.role, department: data.department };
    localStorage.setItem("sentinel_user", JSON.stringify(userInfo));
    setUser(userInfo);
    return userInfo;
  }

  function logout() {
    localStorage.removeItem("sentinel_token");
    localStorage.removeItem("sentinel_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
