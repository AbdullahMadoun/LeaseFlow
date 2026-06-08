import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function TopNav({ title = "Imdad" }) {
  const { currentUser, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setIsScrolled(window.scrollY > 18);
    }

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function onLogout() {
    logout();
    navigate("/");
  }

  return (
    <header className={isScrolled ? "topnav topnav-scrolled" : "topnav"}>
      <div className="topnav-left">
        <Link to="/" className="brand">Imdad</Link>
        {isAuthenticated && (
          <nav className="topnav-links">
            {currentUser.role === "admin" ? (
              <>
                <NavLink to="/admin/dashboard" className={({ isActive }) => (isActive ? "active" : "")}>Dashboard</NavLink>
                <NavLink to="/admin/requests" className={({ isActive }) => (isActive ? "active" : "")}>Requests</NavLink>
              </>
            ) : (
              <>
                <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : "")}>Dashboard</NavLink>
                <NavLink to="/profile" className={({ isActive }) => (isActive ? "active" : "")}>Business Profile</NavLink>
              </>
            )}
          </nav>
        )}
      </div>
      <div className="topnav-right">
        <span className="title-chip">{title}</span>
        {isAuthenticated ? (
          <>
            <span className="small-meta">{currentUser.name} ({currentUser.role})</span>
            <button className="btn ghost" onClick={onLogout} type="button">Logout</button>
          </>
        ) : (
          <>
            <Link className="btn ghost" to="/login">Login</Link>
            <Link className="btn primary" to="/signup">Signup</Link>
          </>
        )}
      </div>
    </header>
  );
}
