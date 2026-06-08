import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { safeJsonParse, uid } from "../utils/helpers";

const USERS_KEY = "imdad_users";
const SESSION_KEY = "imdad_session";

const defaultUsers = [
  {
    id: "admin_1",
    name: "Platform Admin",
    email: "admin@imdad.sa",
    password: "Admin@123",
    role: "admin"
  },
  {
    id: "cust_1",
    name: "Demo Customer",
    email: "user@imdad.sa",
    password: "User@123",
    role: "customer"
  }
];

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [users, setUsers] = useState(() => safeJsonParse(localStorage.getItem(USERS_KEY), defaultUsers));
  const [session, setSession] = useState(() => safeJsonParse(localStorage.getItem(SESSION_KEY), null));

  useEffect(() => {
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
  }, [users]);

  useEffect(() => {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  }, [session]);

  const currentUser = useMemo(() => users.find((u) => u.id === session?.userId) || null, [users, session]);

  function login({ email, password }) {
    const normalized = email.trim().toLowerCase();
    const found = users.find((u) => u.email.toLowerCase() === normalized && u.password === password);
    if (!found) return { ok: false, message: "Invalid credentials" };
    setSession({ userId: found.id });
    return { ok: true, user: found };
  }

  function signup(payload) {
    const email = payload.email.trim().toLowerCase();
    if (users.some((u) => u.email.toLowerCase() === email)) {
      return { ok: false, message: "Email already in use" };
    }
    const created = {
      id: uid("cust"),
      name: payload.name.trim(),
      email,
      password: payload.password,
      role: "customer"
    };
    setUsers((prev) => [...prev, created]);
    setSession({ userId: created.id });
    return { ok: true, user: created };
  }

  function logout() {
    setSession(null);
  }

  return (
    <AuthContext.Provider
      value={{
        users,
        currentUser,
        isAuthenticated: Boolean(currentUser),
        login,
        signup,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
